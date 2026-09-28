param(
    [string]$DayZTools = 'C:\Program Files (x86)\Steam\steamapps\common\DayZ Tools',
    [Parameter(Mandatory=$true)][string]$PrivateKey,
    [string[]]$Modules = @('KF_Food','KF_Pantry'),
    [string]$BuildDirectory = ''
)
$ErrorActionPreference='Stop'
$DayZTools=(Resolve-Path -LiteralPath $DayZTools).Path
$PrivateKey=(Resolve-Path -LiteralPath $PrivateKey).Path
$publicKey=[IO.Path]::ChangeExtension($PrivateKey,'.bikey')
if(!(Test-Path -LiteralPath $publicKey)){throw 'Matching public key is missing'}
if(!$BuildDirectory){$BuildDirectory=Join-Path ([IO.Path]::GetTempPath()) ('KF-build-'+[Guid]::NewGuid().ToString('N'))}
$buildRoot=[IO.Path]::GetFullPath($BuildDirectory)
if(Test-Path -LiteralPath $buildRoot){throw 'Use a new build directory'}
New-Item -ItemType Directory -Path $buildRoot | Out-Null
$destination=Join-Path $PSScriptRoot '@KoreanFood\Addons'
$keyDestination=Join-Path $PSScriptRoot '@KoreanFood\Keys'
$validation=Join-Path $PSScriptRoot 'validation'
New-Item -ItemType Directory -Path $destination,$keyDestination,$validation -Force | Out-Null
$reports=@()
foreach($moduleName in $Modules){
    if($moduleName -notin @('KF_Food','KF_Pantry')){throw 'Unknown module'}
    $module=Join-Path $PSScriptRoot ('source\'+$moduleName)
    & (Join-Path $DayZTools 'Bin\CfgConvert\CfgConvert.exe') -bin -dst (Join-Path $validation ($moduleName+'.config.bin')) (Join-Path $module 'config.cpp')
    if($LASTEXITCODE -ne 0){throw "Config conversion failed: $moduleName"}
    Copy-Item -LiteralPath $module -Destination $buildRoot -Recurse
    $staged=Join-Path $buildRoot $moduleName
    $sourceModels=Join-Path $module 'models';$builtModels=Join-Path $staged 'models'
    $arguments=@('-silent','-always',('"'+$sourceModels+'"'),('"'+$builtModels+'"'),'"*.p3d"')
    $conversion=Start-Process -FilePath (Join-Path $DayZTools 'Bin\Binarize\Binarize.exe') -ArgumentList $arguments -PassThru -Wait -WindowStyle Hidden
    if($conversion.ExitCode -ne 0){throw "Model conversion failed: $moduleName"}
    $models=Get-ChildItem -LiteralPath $builtModels -Filter '*.p3d'
    foreach($model in $models){
        if([Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($model.FullName),0,4) -ne 'ODOL'){throw "Non-ODOL model: $($model.Name)"}
    }
    $packed=Join-Path $buildRoot ('packed-'+$moduleName)
    New-Item -ItemType Directory -Path $packed | Out-Null
    & (Join-Path $DayZTools 'Bin\PboUtils\FileBank.exe') -property ('prefix='+$moduleName) -dst $packed $staged
    if($LASTEXITCODE -ne 0){throw "Packing failed: $moduleName"}
    $pbo=Join-Path $destination ($moduleName+'.pbo')
    Copy-Item -LiteralPath (Join-Path $packed ($moduleName+'.pbo')) -Destination $pbo -Force
    & (Join-Path $DayZTools 'Bin\DsUtils\DSSignFile.exe') $PrivateKey $pbo
    if($LASTEXITCODE -ne 0){throw "Signing failed: $moduleName"}
    $reports+=@{module=$moduleName;models=$models.Count;sha256=(Get-FileHash -LiteralPath $pbo).Hash}
}
Copy-Item -LiteralPath $publicKey -Destination $keyDestination -Force
# The official checker needs normalized Windows paths; slash paths can crash it.
$signatureOutput=& (Join-Path $DayZTools 'Bin\DsUtils\DSCheckSignatures.exe') (Resolve-Path -LiteralPath $destination).Path (Resolve-Path -LiteralPath $keyDestination).Path
$signatureCode=$LASTEXITCODE
$signatureOutput | Set-Content -LiteralPath (Join-Path $validation 'signatures.txt') -Encoding utf8
if($signatureCode -ne 0 -or ($signatureOutput -join "`n") -match 'is not OK|failed|error'){throw 'Signature verification failed'}
foreach($moduleName in $Modules){if(($signatureOutput -join "`n") -notmatch ([regex]::Escape($moduleName+'.pbo.')+'.* is OK')){throw "No positive signature result: $moduleName"}}
@{modules=$reports;buildDirectory=$buildRoot} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $validation 'build.json') -Encoding utf8
$reports | ConvertTo-Json
