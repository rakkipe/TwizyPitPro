param([Parameter(Mandatory=$true)][string]$Serial,[string]$SigningDirectory)
$ErrorActionPreference='Stop'
$pitRoot=Split-Path -Parent $PSScriptRoot
$pitSigning=if($SigningDirectory){(Resolve-Path -LiteralPath $SigningDirectory).ProviderPath}else{Join-Path $pitRoot 'android-signing'}
$pitSecure=(Get-Content -LiteralPath (Join-Path $pitSigning 'password.dpapi') -Raw).Trim() | ConvertTo-SecureString
$pitPtr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($pitSecure)
$pitPreviousSigning=$env:PIT_ANDROID_SIGNING
try {
    $env:PIT_ANDROID_SIGNING=$pitSigning
    $env:PIT_SIGNING_PASSWORD=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pitPtr)
    & (Join-Path $pitRoot '.venv\Scripts\python.exe') (Join-Path $pitRoot 'scripts\test_android_storage.py') --serial $Serial
    $pitExit=$LASTEXITCODE
} finally {
    Remove-Item Env:PIT_SIGNING_PASSWORD -ErrorAction SilentlyContinue
    if($null -eq $pitPreviousSigning){Remove-Item Env:PIT_ANDROID_SIGNING -ErrorAction SilentlyContinue}else{$env:PIT_ANDROID_SIGNING=$pitPreviousSigning}
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pitPtr)
}
exit $pitExit
