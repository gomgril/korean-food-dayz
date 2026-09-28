# KoreanFood 서버 스폰 표(types) 생성기.
# 입력: types-KF_Pantry.xml (기존 108개 원본), 아래 목록.  출력: types_koreanfood.xml
# 원본 = 월드에서 스폰. 파생 상태(개봉·조리·컵 등) = nominal 0 / crafted=1 로 등록해 CE 정리 수명을 명시한다.
param([int]$SpawnScale = 5)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot

# KF_Food 원본 9종: 조리 조건이 '가득 찬 포장'이라 quantmin/max 100 필수.
$foodOriginals = 'KF_RamenPacket','KF_JinHotPacket','KF_JinMildPacket','KF_AnsungPacket','KF_ChapagettiPacket',
                 'KF_CupRamenDry','KF_JinHotCup','KF_JinMildCup','KF_ShrimpCup'

# 액션·레시피로만 생기는 상태. KF_PaperCup(루팅 스폰 겸용)과 KF_Chopsticks(아래 별도)는 제외.
$derived = @'
KF_RamenCooked KF_JinHotPpogeuli KF_JinMildPpogeuli KF_AnsungPpogeuli KF_ChapagettiPpogeuli
KF_CupRamenCooked KF_JinHotCupReady KF_JinMildCupReady KF_ShrimpCupReady
KF_NurungjiReady KF_ChiliTunaOpen KF_FriedKimchiOpen KF_CookedRiceOpen KF_DriedSquidOpen KF_SeasonedGimOpen
KF_MisutgaruCup KF_MisutgaruReady KF_JangjorimOpen KF_PerillaOpen KF_MackerelOpen KF_CurryPouch KF_JjajangPouch
KF_YanggaengOpen KF_ChocoPieOpen KF_HardtackOpen KF_CoffeeMixCup KF_CoffeeMixReady KF_YukgaejangBowlReady
KF_KimchiBowlReady KF_DosirakReady KF_KimchiDosirakReady KF_AnchovyRiceNoodlesReady KF_LuncheonMeatOpen
KF_BeondegiCanOpen KF_WhelkOpen KF_CockleOpen KF_SamgyetangOpen KF_YukgaejangSoupOpen KF_BeefSeaweedSoupOpen
KF_AbalonePorridgeOpen KF_PumpkinPorridgeOpen KF_RedBeanPorridgeOpen KF_BeefVegPorridgeOpen
KF_DoenjangBlockCup KF_DoenjangBlockReady KF_EggSoupBlockCup KF_EggSoupBlockReady KF_BibimWet
KF_PaldoBibimDrained KF_PaldoBibimReady KF_NeoguriReady KF_SesameRamenReady KF_TempuraUdonReady KF_JwipoOpen
KF_RoastedBlackSoyOpen KF_PineNutsOpen KF_YugwaOpen KF_PeanutGangjeongOpen KF_DalgonaOpen KF_SaewookkangOpen
KF_OjingeoPeanutOpen KF_GosomiOpen KF_DigestiveOpen KF_GhanaChocolateOpen KF_PeperoOpen KF_HomeRunBallOpen
KF_MatdongsanOpen KF_NutEnergyBarOpen KF_BarleyTeaCup KF_BarleyTeaReady KF_KkokkalcornOpen KF_SolomonSealTeaCup
KF_SolomonSealTeaReady KF_CornTeaCup KF_CornTeaReady KF_CassiaSeedTeaCup KF_CassiaSeedTeaReady KF_OdongtongReady
KF_SpicySaewookkangOpen KF_PeperoAlmondOpen KF_PeperoChocoFilledOpen KF_PeperoCrunkyOpen KF_PeperoWhiteCookieOpen
KF_PeperoChocoCookieOpen KF_HomeRunBallClassicOpen KF_HomeRunBallSaltMilkOpen KF_KkokkalcornRoastedOpen
KF_KkokkalcornSweetSpicyOpen KF_KkokkalcornWaxyCornOpen KF_WhiteGoldCoffeeCup KF_WhiteGoldCoffeeReady
KF_ChestnutYanggaengOpen KF_SeaweedSoupBlockCup KF_SeaweedSoupBlockReady KF_YukgaejangBlockCup
KF_YukgaejangBlockReady KF_CurryOpen KF_JjajangOpen KF_CombatRationOpen KF_RationKimchiRice KF_RationWhiteRice
KF_RationMeatballs KF_RationTofu KF_RationAnchovy KF_RationKimchiRiceOpen KF_RationWhiteRiceOpen
KF_RationMeatballsOpen KF_RationTofuOpen KF_RationAnchovyOpen
'@ -split '\s+' | Where-Object { $_ }

function Flags($crafted) { "<flags count_in_cargo=`"0`" count_in_hoarder=`"0`" count_in_map=`"1`" count_in_player=`"0`" crafted=`"$crafted`" deloot=`"0`" />" }

[xml]$base = Get-Content (Join-Path $here 'types-KF_Pantry.xml') -Raw -Encoding utf8
$lines = [Collections.Generic.List[string]]::new()
$lines.Add('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>')
$lines.Add('<types>')
$lines.Add('    <!-- 월드 스폰 원본 (KF_Pantry 107 + 종이컵) -->')
foreach ($t in $base.types.type) { $lines.Add('    ' + $t.OuterXml) }
$lines.Add('    <!-- 월드 스폰 원본 (KF_Food 라면 9) -->')
foreach ($n in $foodOriginals) {
    $lines.Add("    <type name=`"$n`"><nominal>2</nominal><lifetime>7200</lifetime><restock>1800</restock><min>1</min><quantmin>100</quantmin><quantmax>100</quantmax><cost>100</cost>$(Flags 0)<category name=`"food`" /><usage name=`"Town`" /><usage name=`"Village`" /></type>")
}
$lines.Add('    <!-- 젓가락: 조리 라면을 먹는 데 필요하므로 소량 스폰 -->')
$lines.Add("    <type name=`"KF_Chopsticks`"><nominal>4</nominal><lifetime>14400</lifetime><restock>1800</restock><min>2</min><quantmin>-1</quantmin><quantmax>-1</quantmax><cost>100</cost>$(Flags 0)<category name=`"tools`" /><usage name=`"Town`" /><usage name=`"Village`" /></type>")
$lines.Add('    <!-- 파생 상태: 스폰하지 않음. 바닥에 둔 개봉·조리품의 정리 수명 (바닐라 _Opened 와 같은 방식) -->')
foreach ($n in $derived) {
    $lines.Add("    <type name=`"$n`"><nominal>0</nominal><lifetime>14400</lifetime><restock>0</restock><min>0</min><quantmin>-1</quantmin><quantmax>-1</quantmax><cost>100</cost>$(Flags 1)<category name=`"food`" /></type>")
}
$lines.Add('</types>')

$names = $lines | Select-String -Pattern 'type name="([^"]+)"' | ForEach-Object { $_.Matches[0].Groups[1].Value }
$dupes = $names | Group-Object | Where-Object Count -gt 1
if ($dupes) { throw "중복: $($dupes.Name -join ', ')" }
$out = Join-Path $here 'types_koreanfood.xml'
[xml]$doc = $lines -join "`n"

# 스폰 원본의 수명·장소·티어를 바닐라의 비슷한 음식에 맞춘다. 스폰 개수(nominal/min/restock)는 바꾸지 않는다.
$profiles = @{
    # 과자·스낵: 바닐라 Chips/Crackers (티어는 1만 쓰면 해안에만 몰려서 1·2)
    snack  = @{ life=7200;  shelves=$true;  usage='Town','Village','School','Lunapark'; tier=1,2 }
    # 초콜릿·양갱·건어물·견과: 바닐라 Zagorky
    sweet  = @{ life=14400; shelves=$true;  usage='Village','Hunting','Office','School','Lunapark'; tier=1,2,3 }
    # 라면·컵라면
    noodle = @{ life=14400; shelves=$true;  usage='Town','Village','Office','School'; tier=1,2,3 }
    # 통조림·레토르트·즉석밥·죽·국: 바닐라 SpaghettiCan/TunaCan/PorkCan
    meal   = @{ life=14400; shelves=$true;  usage='Town','Village','Office','School'; tier=1,2,3 }
    # 차·커피 상자·미숫가루: 바닐라 PowderedMilk
    pantry = @{ life=28800; shelves=$true;  usage='Town','Village','Office'; tier=1,2,3 }
    # 캔·병·팩 음료와 우유: 바닐라 SodaCan
    drink  = @{ life=14400; shelves=$false; usage='Town','Village','Office','School','Lunapark'; tier=1,2,3 }
    # 건빵: 군용 보급품 성격
    ration = @{ life=14400; shelves=$true;  usage='Village','Hunting','Military'; tier=1,2,3 }
    # 전투식량 상자: 바닐라 TacticalBaconCan
    combat = @{ life=28800; shelves=$true;  usage='Military'; tier=@() }
    # 젓가락·종이컵
    tool   = @{ life=14400; shelves=$false; usage='Town','Village','Office','School'; tier=1,2,3 }
}
$groups = @{
    snack  = 'KF_Kkokkalcorn KF_KkokkalcornRoasted KF_KkokkalcornSweetSpicy KF_KkokkalcornWaxyCorn KF_Saewookkang KF_SpicySaewookkang KF_Pepero KF_PeperoAlmond KF_PeperoChocoCookie KF_PeperoChocoFilled KF_PeperoCrunky KF_PeperoWhiteCookie KF_HomeRunBall KF_HomeRunBallClassic KF_HomeRunBallSaltMilk KF_ChocoPie KF_Digestive KF_Gosomi KF_Matdongsan KF_OjingeoPeanut KF_Dalgona KF_Yugwa KF_PeanutGangjeong'
    sweet  = 'KF_GhanaChocolate KF_NutEnergyBar KF_Yanggaeng KF_ChestnutYanggaeng KF_DriedSquid KF_Jwipo KF_PineNuts KF_RoastedBlackSoy'
    noodle = 'KF_RamenPacket KF_JinHotPacket KF_JinMildPacket KF_AnsungPacket KF_ChapagettiPacket KF_CupRamenDry KF_JinHotCup KF_JinMildCup KF_ShrimpCup KF_AnchovyRiceNoodles KF_Dosirak KF_KimchiBowl KF_KimchiDosirak KF_Neoguri KF_Odongtong KF_PaldoBibim KF_SesameRamen KF_TempuraUdon KF_YukgaejangBowl'
    meal   = 'KF_AbalonePorridge KF_BeefVegPorridge KF_PumpkinPorridge KF_RedBeanPorridge KF_BeefSeaweedSoup KF_YukgaejangSoup KF_Samgyetang KF_Curry KF_Jjajang KF_CookedRice KF_Nurungji KF_SeasonedGim KF_BeondegiCan KF_ChiliTuna KF_Cockle KF_FriedKimchi KF_Jangjorim KF_LuncheonMeat KF_Mackerel KF_Perilla KF_Whelk KF_DoenjangBlock KF_EggSoupBlock KF_SeaweedSoupBlock KF_YukgaejangBlock'
    pantry = 'KF_BarleyTea KF_CornTea KF_CassiaSeedTea KF_SolomonSealTea KF_CoffeeMix KF_WhiteGoldCoffee KF_Misutgaru'
    drink  = 'KF_Bacchus KF_BacchusF KF_BananaMilk KF_MelonaMilk KF_StrawberryMilk KF_ChilsungCider KF_Gatorade KF_GatoradeBlue KF_GatoradeZero KF_IonTheFit KF_PearDrinkBottle KF_Pocari KF_Powerade KF_Toreta KF_JuicyCool KF_JuicyCoolSmallGreenGrape KF_JuicyCoolSmallPeach KF_JuicyCoolSmallPineapple KF_JuicyCoolLargeGreenGrape KF_JuicyCoolLargePeach KF_JuicyCoolLargePineapple KF_JuicyCoolLargePlum KF_CeylonTea KF_GrapeBongbong KF_McCol KF_OranC KF_OranCCalamansi KF_OranCOrange KF_PearDrink KF_Sikhye KF_Ssaksak KF_Sujeonggwa'
    ration = 'KF_Hardtack'
    combat = 'KF_CombatRation'
    tool   = 'KF_Chopsticks KF_PaperCup'
}
$groupOf = @{}
foreach ($g in $groups.Keys) { foreach ($n in ($groups[$g] -split '\s+')) { if ($groupOf.ContainsKey($n)) { throw "그룹 중복: $n" }; $groupOf[$n] = $g } }
foreach ($t in $doc.types.type) {
    $spawns = [int]$t.nominal -gt 0
    if ($spawns -ne $groupOf.ContainsKey($t.name)) { throw "그룹 지정 누락 또는 파생 상태에 지정: $($t.name)" }
    if (-not $spawns) { continue }
    $p = $profiles[$groupOf[$t.name]]
    $t.lifetime = [string]$p.life
    # 바닐라 음식과 같이 restock 0: 부족하면 바로 다시 채운다 (1800이면 새 서버에서 30분 동안 스폰되지 않음)
    $t.restock = '0'
    # 스폰 빈도 배율 (0.4.8: 기존 설계값의 5배)
    $t.nominal = [string]([int]$t.nominal * $SpawnScale)
    $t.min = [string]([int]$t.min * $SpawnScale)
    foreach ($old in @($t.SelectNodes('tag|usage|value'))) { [void]$t.RemoveChild($old) }
    $add = { param($kind, $name) $e = $doc.CreateElement($kind); $e.SetAttribute('name', $name); [void]$t.AppendChild($e) }
    if ($p.shelves) { & $add 'tag' 'shelves' }
    foreach ($u in $p.usage) { & $add 'usage' $u }
    foreach ($v in $p.tier) { & $add 'value' "Tier$v" }
}

# 바닐라 types.xml 처럼 태그마다 줄을 나누고 4칸 들여쓰기로 저장한다.
$settings = [Xml.XmlWriterSettings]::new()
$settings.Indent = $true
$settings.IndentChars = '    '
$settings.NewLineChars = "`r`n"
$settings.Encoding = [Text.UTF8Encoding]::new($false)
$writer = [Xml.XmlWriter]::Create($out, $settings)
try { $doc.Save($writer) } finally { $writer.Close() }
[xml](Get-Content $out -Raw -Encoding utf8) | Out-Null
"작성: $out  (항목 $($names.Count)개)"
