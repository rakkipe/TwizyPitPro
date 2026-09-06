param([switch]$Unsigned,[switch]$QA)
$ErrorActionPreference='Stop'
$pitRoot=Split-Path -Parent $PSScriptRoot
$pitBuild=Join-Path $pitRoot 'scripts\build_android.py'
$pitPython=Join-Path $pitRoot '.venv\Scripts\python.exe'
if($Unsigned) { & $pitPython $pitBuild --unsigned; exit $LASTEXITCODE }
$pitSecretPath=Join-Path $pitRoot 'android-signing\password.dpapi'
if(-not (Test-Path -LiteralPath $pitSecretPath)) { throw 'De eigenaarsleutel ontbreekt. Initialiseer signing eerst.' }
$pitSecure=(Get-Content -LiteralPath $pitSecretPath -Raw).Trim() | ConvertTo-SecureString
$pitPtr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($pitSecure)
try {
    $env:PIT_SIGNING_PASSWORD=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pitPtr)
    if($QA){ & $pitPython $pitBuild --qa } else { & $pitPython $pitBuild }
    $pitExit=$LASTEXITCODE
} finally {
    Remove-Item Env:PIT_SIGNING_PASSWORD -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pitPtr)
}
exit $pitExit
