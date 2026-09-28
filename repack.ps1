# 검증된 기존 PBO의 바이너리 모델은 그대로 두고, 텍스트 파일(config.cpp, scripts, stringtable.csv)만 source에서 덮어써 다시 패킹·서명한다.
# Binarize 재실행 시 모델이 소수점 단위로 달라지는 것을 피하기 위한 방식이다. 모델을 바꾼 업데이트는 build-full.ps1을 쓴다.
param(
    [Parameter(Mandatory=$true)][string]$BasePboDir,     # 기준 PBO가 있는 Addons 폴더 (예: ..\KoreanFood-v0.4.7-full\@KoreanFood\Addons)
    [Parameter(Mandatory=$true)][string]$PrivateKey,
    [string[]]$Modules = @('KF_Food','KF_Pantry'),
    [string]$DayZTools = 'C:\Program Files (x86)\Steam\steamapps\common\DayZ Tools'
)
$ErrorActionPreference = 'Stop'
$bin = Join-Path $DayZTools 'Bin'
$work = Join-Path ([IO.Path]::GetTempPath()) ('KF-repack-' + [Guid]::NewGuid().ToString('N'))
$addons = Join-Path $PSScriptRoot '@KoreanFood\Addons'
$report = @()
foreach ($m in $Modules) {
    $base = Join-Path $BasePboDir "$m.pbo"
    $old = Join-Path $work "old"; $stage = Join-Path $work "stage"; $packed = Join-Path $work "packed-$m"; $verify = Join-Path $work "verify"
    New-Item -ItemType Directory $old, $stage, $packed -Force | Out-Null
    & (Join-Path $bin 'PboUtils\BankRev.exe') -f $old $base | Out-Null
    if (-not (Test-Path (Join-Path $old $m))) { throw "기준 PBO 풀기 실패: $base" }
    Copy-Item (Join-Path $old $m) $stage -Recurse -Force
    $src = Join-Path $PSScriptRoot "source\$m"
    $dst = Join-Path $stage $m
    Copy-Item (Join-Path $src 'config.cpp') $dst -Force
    if (Test-Path (Join-Path $dst 'scripts')) { Remove-Item (Join-Path $dst 'scripts') -Recurse -Force }
    Copy-Item (Join-Path $src 'scripts') $dst -Recurse -Force
    if (Test-Path (Join-Path $src 'stringtable.csv')) { Copy-Item (Join-Path $src 'stringtable.csv') $dst -Force }
    & (Join-Path $bin 'PboUtils\FileBank.exe') -property "prefix=$m" -dst $packed $dst | Out-Null
    if ($LASTEXITCODE) { throw "패킹 실패: $m" }
    $pbo = Join-Path $addons "$m.pbo"
    Copy-Item (Join-Path $packed "$m.pbo") $pbo -Force
    & (Join-Path $bin 'DsUtils\DSSignFile.exe') $PrivateKey $pbo
    if ($LASTEXITCODE) { throw "서명 실패: $m" }
    # 패킹 결과를 다시 풀어 기준 PBO와 비교한다 (FileBank는 실패해도 조용히 넘어갈 수 있음).
    & (Join-Path $bin 'PboUtils\BankRev.exe') -f $verify $pbo | Out-Null
    $rn = Join-Path $verify $m; $ro = Join-Path $old $m
    $changes = foreach ($f in Get-ChildItem $rn -Recurse -File) {
        $rel = $f.FullName.Substring($rn.Length)
        $o = Join-Path $ro $rel
        if (-not (Test-Path $o)) { "NEW  $rel" } elseif ((Get-FileHash $o).Hash -ne (Get-FileHash $f.FullName).Hash) { "DIFF $rel" }
    }
    $removed = foreach ($f in Get-ChildItem $ro -Recurse -File) { $rel = $f.FullName.Substring($ro.Length); if (-not (Test-Path (Join-Path $rn $rel))) { "GONE $rel" } }
    $binaryChanged = @($changes | Where-Object { $_ -match '\.(p3d|paa|ogg|anm|rtm)$' })
    if ($binaryChanged) { throw "바이너리 자산이 바뀜: $($binaryChanged -join ', ')" }
    $report += [pscustomobject]@{ module = $m; sha256 = (Get-FileHash $pbo).Hash; changes = @($changes) + @($removed) }
    Remove-Item $old, $stage, $verify -Recurse -Force
}
$sig = & (Join-Path $bin 'DsUtils\DSCheckSignatures.exe') (Resolve-Path $addons).Path (Resolve-Path (Join-Path $PSScriptRoot '@KoreanFood\Keys')).Path
$sig | Set-Content (Join-Path $PSScriptRoot 'validation\signatures.txt') -Encoding utf8
if (($sig -join "`n") -match 'is not OK|failed|error') { throw "서명 검사 실패" }
@{ method = 'repack.ps1: base PBO binaries kept, text files from source'; base = $BasePboDir; modules = $report } |
    ConvertTo-Json -Depth 5 | Set-Content (Join-Path $PSScriptRoot 'validation\build.json') -Encoding utf8
$report | ForEach-Object { "== $($_.module) $($_.sha256)"; $_.changes }
$sig
