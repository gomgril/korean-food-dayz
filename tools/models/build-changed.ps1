# Partial build: binarize ONLY the listed models, overlay them (plus listed .paa/.rvmat and the
# text files config.cpp / scripts / stringtable.csv from source, like repack.ps1) onto the contents
# of a base PBO, repack with FileBank, sign, verify the signature, unpack the result and diff it
# against the base. Fails if any file other than the intended ones changed.
#
# Example (pilot):
#   powershell -ExecutionPolicy Bypass -File tools\models\build-changed.ps1 -Addon KF_Pantry `
#       -Models pepero_open,yanggaeng_open -PrivateKey <path\to\key.biprivatekey>   (or set $env:KF_SIGN_KEY)
# Output (default): tools\models\out\Addons\<Addon>.pbo (+ .bisign), tools\models\out\Keys\*.bikey,
#                   tools\models\out\build-changed-<Addon>.json
# The repo's @KoreanFood\Addons is never written. Copy the output there yourself once reviewed.
param(
    [ValidateSet('KF_Pantry','KF_Food')][string]$Addon = 'KF_Pantry',
    # model names (pepero_open), file names (pepero_open.p3d) or paths under source\<Addon>\models
    [Parameter(Mandatory=$true)][string[]]$Models,
    # other changed files, relative to source\<Addon> (e.g. data\foo_co.paa, data\foo.rvmat)
    [string[]]$Files = @(),
    [string]$BasePbo = '',
    [string]$OutDir = '',
    # signing key: pass -PrivateKey or set the KF_SIGN_KEY environment variable (never commit the key)
    [string]$PrivateKey = $env:KF_SIGN_KEY,
    [string]$DayZTools = 'C:\Program Files (x86)\Steam\steamapps\common\DayZ Tools',
    # config.cpp / scripts / stringtable.csv are always overlaid from source; if they differ from the base
    # the build fails unless this switch is given (then they are reported as intended TEXT changes).
    [switch]$AllowTextChanges,
    [switch]$KeepWork
)
$ErrorActionPreference = 'Stop'
$tools = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $tools '..\..')).Path
$bin = Join-Path $DayZTools 'Bin'
$src = Join-Path $repo "source\$Addon"
if (-not $OutDir) { $OutDir = Join-Path $tools 'out' }
$OutDir = [IO.Path]::GetFullPath($OutDir)
$repoAddons = [IO.Path]::GetFullPath((Join-Path $repo '@KoreanFood\Addons'))
if ($OutDir.TrimEnd('\') -ieq $repoAddons.TrimEnd('\')) { throw 'OutDir must not be the repo @KoreanFood\Addons' }

# ---- base PBO: default is a backup copy of the repo's current (0.4.8) PBO in tools\models\base
$baseDir = Join-Path $tools 'base'
if (-not $BasePbo) {
    $BasePbo = Join-Path $baseDir "$Addon.pbo"
    if (-not (Test-Path $BasePbo)) {
        New-Item -ItemType Directory -Force $baseDir | Out-Null
        Copy-Item (Join-Path $repoAddons "$Addon.pbo") $BasePbo
        Get-ChildItem $repoAddons -Filter "$Addon.pbo.*.bisign" | Copy-Item -Destination $baseDir
        Write-Host "Backed up base: $BasePbo"
    }
}
$BasePbo = (Resolve-Path $BasePbo).Path
if (-not $PrivateKey) { throw 'No signing key: pass -PrivateKey <path to .biprivatekey> or set $env:KF_SIGN_KEY' }
$PrivateKey = (Resolve-Path $PrivateKey).Path
$publicKey = [IO.Path]::ChangeExtension($PrivateKey, '.bikey')
if (-not (Test-Path $publicKey)) { throw "Public key missing: $publicKey" }

# ---- normalise the model list
$modelNames = @($Models | ForEach-Object { $_ -split ',' } | Where-Object { $_ } | ForEach-Object {
    $n = [IO.Path]::GetFileNameWithoutExtension($_.Trim())
    if (-not (Test-Path (Join-Path $src "models\$n.p3d"))) { throw "Model not found: source\$Addon\models\$n.p3d" }
    $n } | Select-Object -Unique)
foreach ($f in $Files) { if (-not (Test-Path (Join-Path $src $f))) { throw "File not found: source\$Addon\$f" } }

# ---- work dir (short path: BankRev fails on very long paths)
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$work = Join-Path $tools "work\$Addon-$stamp"
$wBase = Join-Path $work 'base'; $wBin = Join-Path $work 'bin'; $wPacked = Join-Path $work 'packed'; $wVerify = Join-Path $work 'verify'
New-Item -ItemType Directory -Force $wBase, $wBin, $wPacked, $wVerify | Out-Null

# ---- 1. extract base
& (Join-Path $bin 'PboUtils\BankRev.exe') -f $wBase $BasePbo | Out-Null
$baseRoot = Join-Path $wBase $Addon
if (-not (Test-Path $baseRoot)) { throw "Base extraction failed: $BasePbo" }
$baseProps = Join-Path $wBase "$Addon.txt"
$stage = Join-Path $work 'stage'
New-Item -ItemType Directory -Force $stage | Out-Null
Copy-Item $baseRoot $stage -Recurse
$stageRoot = Join-Path $stage $Addon

# ---- 2. binarize only the listed models (same Binarize arguments as build-full.ps1).
# The listed MLODs + model.cfg are staged into their own folder and binarized in ONE run with mask *.p3d:
# pointing Binarize at the full source folder makes it scan every model (~1.5 min per run) and its
# file mask is fuzzy (mask "yanggaeng_open.p3d" also matched chestnutyanggaeng_open.p3d).
$binarizeExe = Join-Path $bin 'Binarize\Binarize.exe'
$srcModels = Join-Path $src 'models'
$bSrc = Join-Path $work "bsrc\$Addon\models"
New-Item -ItemType Directory -Force $bSrc | Out-Null
foreach ($n in $modelNames) { Copy-Item (Join-Path $srcModels "$n.p3d") $bSrc }
if (Test-Path (Join-Path $srcModels 'model.cfg')) { Copy-Item (Join-Path $srcModels 'model.cfg') $bSrc }
$bargs = @('-silent', '-always', ('"' + $bSrc + '"'), ('"' + $wBin + '"'), '"*.p3d"')
$p = Start-Process -FilePath $binarizeExe -ArgumentList $bargs -PassThru -Wait -WindowStyle Hidden
if ($p.ExitCode -ne 0) { throw "Binarize failed ($($p.ExitCode))" }
foreach ($n in $modelNames) {
    $out = Join-Path $wBin "$n.p3d"
    if (-not (Test-Path $out)) { throw "Binarize produced no output: $n" }
    $magic = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($out), 0, 4)
    if ($magic -ne 'ODOL') { throw "Non-ODOL output ($magic): $n" }
}
$produced = @(Get-ChildItem $wBin -Recurse -File -Filter *.p3d | ForEach-Object { $_.BaseName })
$unexpected = @($produced | Where-Object { $_ -notin $modelNames })
if ($unexpected) { throw "Binarize produced unexpected models: $($unexpected -join ', ')" }

# ---- 3. overlay: models, extra files, text files from source (as repack.ps1)
$intended = New-Object System.Collections.Generic.List[string]
foreach ($n in $modelNames) {
    Copy-Item (Join-Path $wBin "$n.p3d") (Join-Path $stageRoot "models\$n.p3d") -Force
    $intended.Add("\models\$n.p3d")
}
foreach ($f in $Files) {
    $dst = Join-Path $stageRoot $f
    New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
    Copy-Item (Join-Path $src $f) $dst -Force
    $intended.Add('\' + $f.TrimStart('\'))
}
Copy-Item (Join-Path $src 'config.cpp') $stageRoot -Force
if (Test-Path (Join-Path $stageRoot 'scripts')) { Remove-Item (Join-Path $stageRoot 'scripts') -Recurse -Force }
Copy-Item (Join-Path $src 'scripts') $stageRoot -Recurse -Force
if (Test-Path (Join-Path $src 'stringtable.csv')) { Copy-Item (Join-Path $src 'stringtable.csv') $stageRoot -Force }

# ---- 4. pack, sign
& (Join-Path $bin 'PboUtils\FileBank.exe') -property "prefix=$Addon" -dst $wPacked $stageRoot | Out-Null
if ($LASTEXITCODE) { throw "FileBank failed: $Addon" }
$addonsOut = Join-Path $OutDir 'Addons'; $keysOut = Join-Path $OutDir 'Keys'
New-Item -ItemType Directory -Force $addonsOut, $keysOut | Out-Null
$pbo = Join-Path $addonsOut "$Addon.pbo"
Get-ChildItem $addonsOut -Filter "$Addon.pbo*" | Remove-Item -Force
Copy-Item (Join-Path $wPacked "$Addon.pbo") $pbo -Force
& (Join-Path $bin 'DsUtils\DSSignFile.exe') $PrivateKey $pbo
if ($LASTEXITCODE) { throw "DSSignFile failed: $Addon" }
Copy-Item $publicKey $keysOut -Force

# ---- 5. verify signature (only this addon in $addonsOut is checked)
$sig = & (Join-Path $bin 'DsUtils\DSCheckSignatures.exe') (Resolve-Path $addonsOut).Path (Resolve-Path $keysOut).Path
$sigText = $sig -join "`n"
if ($LASTEXITCODE -or $sigText -match 'is not OK|failed|error') { throw "Signature check failed:`n$sigText" }
if ($sigText -notmatch ([regex]::Escape("$Addon.pbo.") + '.* is OK')) { throw "No positive signature result for $Addon`n$sigText" }

# ---- 6. unpack result and diff against base
& (Join-Path $bin 'PboUtils\BankRev.exe') -f $wVerify $pbo | Out-Null
$newRoot = Join-Path $wVerify $Addon
if (-not (Test-Path $newRoot)) { throw 'Unpacking the new PBO failed' }
$changes = @()
foreach ($f in Get-ChildItem $newRoot -Recurse -File) {
    $rel = $f.FullName.Substring($newRoot.Length)
    $o = Join-Path $baseRoot $rel
    if (-not (Test-Path $o)) { $changes += [pscustomobject]@{ kind = 'NEW'; path = $rel } }
    elseif ((Get-FileHash $o).Hash -ne (Get-FileHash $f.FullName).Hash) { $changes += [pscustomobject]@{ kind = 'DIFF'; path = $rel } }
}
foreach ($f in Get-ChildItem $baseRoot -Recurse -File) {
    $rel = $f.FullName.Substring($baseRoot.Length)
    if (-not (Test-Path (Join-Path $newRoot $rel))) { $changes += [pscustomobject]@{ kind = 'GONE'; path = $rel } }
}
$newProps = Join-Path $wVerify "$Addon.txt"
$propsSame = (Test-Path $baseProps) -and (Test-Path $newProps) -and ((Get-Content $baseProps -Raw) -eq (Get-Content $newProps -Raw))
$isText = { param($p) $p -ieq '\config.cpp' -or $p -ieq '\stringtable.csv' -or $p -like '\scripts\*' }
$bad = @(); $textChanged = @()
foreach ($c in $changes) {
    if ($intended -contains $c.path -and $c.kind -ne 'GONE') { continue }
    if (& $isText $c.path) { $textChanged += $c; if ($AllowTextChanges) { continue } }
    $bad += $c
}
$missing = @($intended | Where-Object { $p = $_; -not ($changes | Where-Object { $_.path -eq $p }) })
# report paths repo-relative (no personal absolute paths in reports)
$rel = { param($p) $s = [string]$p; if ($s.StartsWith($repo, [StringComparison]::OrdinalIgnoreCase)) { '.' + $s.Substring($repo.Length) } else { [IO.Path]::GetFileName($s) } }
$sigText = ($sig | ForEach-Object { $_ -replace [regex]::Escape($repo), '.' }) -join "`n"
$report = [ordered]@{
    addon = $Addon; time = (Get-Date).ToString('s'); base = (& $rel $BasePbo); base_sha256 = (Get-FileHash $BasePbo).Hash
    output = (& $rel $pbo); output_sha256 = (Get-FileHash $pbo).Hash
    models = $modelNames; files = $Files; intended = @($intended)
    changes = @($changes | ForEach-Object { "$($_.kind) $($_.path)" })
    unexpected = @($bad | ForEach-Object { "$($_.kind) $($_.path)" })
    text_changes = @($textChanged | ForEach-Object { "$($_.kind) $($_.path)" })
    intended_but_unchanged = $missing
    pbo_properties_same_as_base = $propsSame
    files_in_base = (Get-ChildItem $baseRoot -Recurse -File).Count; files_in_output = (Get-ChildItem $newRoot -Recurse -File).Count
    signature = $sigText; work = (& $rel $work)
}
$reportPath = Join-Path $OutDir "build-changed-$Addon.json"
$report | ConvertTo-Json -Depth 5 | Set-Content $reportPath -Encoding utf8
"== $Addon  $($report.output_sha256)"
$report.changes
"signature: " + (($sig | Select-String 'is OK|not OK') -join ' / ')
"report: $reportPath"
if (-not $KeepWork -and -not $bad -and -not $missing) { Remove-Item $work -Recurse -Force }
if (-not $propsSame) { throw 'PBO properties (prefix) differ from base - see report' }
if ($missing) { throw "Intended files did not change: $($missing -join ', ')" }
if ($bad) { throw "Unexpected changes: $(($bad | ForEach-Object { "$($_.kind) $($_.path)" }) -join ', ')" }
"OK: only intended files changed ($($changes.Count))"

