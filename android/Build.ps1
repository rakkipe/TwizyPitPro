param([switch]$Unsigned,[switch]$QA,[string]$SigningDirectory)
$ErrorActionPreference='Stop'
$pitRoot=Split-Path -Parent $PSScriptRoot
$pitBuild=Join-Path $pitRoot 'scripts\build_android.py'
$pitPython=Join-Path $pitRoot '.venv\Scripts\python.exe'
if($Unsigned) { & $pitPython $pitBuild --unsigned; exit $LASTEXITCODE }
$pitSigning=if($SigningDirectory){(Resolve-Path -LiteralPath $SigningDirectory).ProviderPath}else{Join-Path $pitRoot 'android-signing'}
$pitSecretPath=Join-Path $pitSigning 'password.dpapi'
if(-not (Test-Path -LiteralPath $pitSecretPath)) { throw 'De eigenaarsleutel ontbreekt. Initialiseer signing eerst.' }
$pitSecure=(Get-Content -LiteralPath $pitSecretPath -Raw).Trim() | ConvertTo-SecureString
$pitPtr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($pitSecure)
$pitPreviousSigning=$env:PIT_ANDROID_SIGNING
try {
    $env:PIT_ANDROID_SIGNING=$pitSigning
    $env:PIT_SIGNING_PASSWORD=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pitPtr)
    if($QA){ & $pitPython $pitBuild --qa } else { & $pitPython $pitBuild }
    $pitExit=$LASTEXITCODE
} finally {
    Remove-Item Env:PIT_SIGNING_PASSWORD -ErrorAction SilentlyContinue
    if($null -eq $pitPreviousSigning){Remove-Item Env:PIT_ANDROID_SIGNING -ErrorAction SilentlyContinue}else{$env:PIT_ANDROID_SIGNING=$pitPreviousSigning}
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pitPtr)
}
exit $pitExit
