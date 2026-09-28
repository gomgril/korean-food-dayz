# strings.tsv(key, ko, en) + tr-<lang>.tsv(key, text) -> source\KF_Food\stringtable.csv
# 키마다 두 줄을 만든다.
#   STR_KF_x    : 게임 언어별 칸. 번역 파일이 있는 언어는 그 번역, 없는 언어는 영어.
#   STR_KF_x_KO : 모든 칸 한국어. 스크립트(KF_Lang.c)가 한글 패치(LakeProject_Localization)를 감지하면 이 키를 쓴다.
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$columns = 'original','english','czech','german','russian','polish','hungarian','italian','spanish','french','chinese','japanese','portuguese','chinesesimp'
# stringtable 칸 -> 번역 파일 이름(tr-<이름>.tsv)
$sources = @{ german = 'de'; russian = 'ru'; polish = 'pl'; chinese = 'zh_hant'; japanese = 'ja'; portuguese = 'pt'; chinesesimp = 'zh_hans' }
# 다른 모드(COT·Expansion)와 같이 쉼표나 따옴표가 든 칸만 따옴표로 감싼다. 키·언어 이름에 따옴표를 붙이면 게임이 키를 찾지 못한다.
function Q($s) { if ($s -match '[",]|^\s|\s$') { '"' + $s.Replace('"', '""') + '"' } else { $s } }

$rows = [IO.File]::ReadAllLines((Join-Path $here 'strings.tsv'), [Text.Encoding]::UTF8) | Select-Object -Skip 1 | Where-Object { $_ }
$keys = foreach ($row in $rows) { ($row -split "`t", 2)[0] }

$tr = @{}
foreach ($col in $sources.Keys) {
    $file = Join-Path $here "tr-$($sources[$col]).tsv"
    if (-not (Test-Path $file)) { continue }
    $map = @{}
    foreach ($line in ([IO.File]::ReadAllLines($file, [Text.Encoding]::UTF8) | Select-Object -Skip 1 | Where-Object { $_ })) {
        $k, $v = $line -split "`t", 2
        if (-not $v) { throw "$file : 빈 번역 $k" }
        $map[$k] = $v
    }
    $missing = @($keys | Where-Object { -not $map.ContainsKey($_) })
    if ($missing) { throw "$file : 키 누락 $($missing -join ', ')" }
    foreach ($k in $keys) { if ($k -like 'STR_KF_S_*' -and -not $map[$k].StartsWith(' ')) { throw "$file : $k 는 공백으로 시작해야 함" } }
    $tr[$col] = $map
}

# DayZ는 255바이트를 넘는 칸이 있으면 그 언어 칸 전체를 읽지 않는다(0.4.8 테스트에서 확인). 250바이트로 제한한다.
$limit = 250
foreach ($row in $rows) { $k, $ko, $en = $row -split "`t", 3; foreach ($v in @($ko, $en)) { if ([Text.Encoding]::UTF8.GetByteCount($v) -gt $limit) { throw "250바이트 초과: $k" } } }
foreach ($col in $tr.Keys) { foreach ($k in $tr[$col].Keys) { if ([Text.Encoding]::UTF8.GetByteCount($tr[$col][$k]) -gt $limit) { throw "250바이트 초과 ($col): $k" } } }
$out = [Collections.Generic.List[string]]::new()
$out.Add(((@('Language') + $columns | ForEach-Object { Q $_ }) -join ',') + ',')
$seen = @{}
foreach ($row in $rows) {
    $key, $ko, $en = $row -split "`t", 3
    if (-not $en) { throw "영어 누락: $key" }
    if ($seen.ContainsKey($key)) { throw "키 중복: $key" }
    $seen[$key] = 1
    $cells = foreach ($c in $columns) { if ($tr.ContainsKey($c)) { $tr[$c][$key] } else { $en } }
    $out.Add((((@($key) + $cells) | ForEach-Object { Q $_ }) -join ',') + ',')
    $out.Add((((@("${key}_KO") + ($columns | ForEach-Object { $ko })) | ForEach-Object { Q $_ }) -join ',') + ',')
}
$target = Join-Path $here '..\source\KF_Food\stringtable.csv'
# 다른 모드 stringtable.csv 형식: BOM 없는 UTF-8, 모든 줄 끝에 쉼표
[IO.File]::WriteAllLines($target, $out, [Text.UTF8Encoding]::new($false))
"작성: $((Resolve-Path $target).Path)  (키 $($seen.Count)개, 번역 언어: $(($tr.Keys | Sort-Object) -join ', '))"
