$ErrorActionPreference='Stop'
$pitRoot=Split-Path -Parent $PSScriptRoot
$pitSigning=Join-Path $pitRoot 'android-signing'
$pitStore=Join-Path $pitSigning 'owner-release.p12'
if(Test-Path -LiteralPath $pitStore){throw 'Bestaande eigenaarsleutel blijft behouden.'}
New-Item -ItemType Directory -Path $pitSigning -Force | Out-Null
$pitIdentity=[Security.Principal.WindowsIdentity]::GetCurrent().User
$pitAcl=New-Object Security.AccessControl.DirectorySecurity
$pitAcl.SetOwner($pitIdentity)
$pitAcl.SetAccessRuleProtection($true,$false)
$pitAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($pitIdentity,'FullControl','ContainerInherit,ObjectInherit','None','Allow')))
Set-Acl -LiteralPath $pitSigning -AclObject $pitAcl
$pitBytes=New-Object byte[] 36
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($pitBytes)
$pitPassword=[Convert]::ToBase64String($pitBytes)
$pitPassword | ConvertTo-SecureString -AsPlainText -Force | ConvertFrom-SecureString | Set-Content -LiteralPath (Join-Path $pitSigning 'password.dpapi')
$pitKeytool=(Get-ChildItem -LiteralPath (Join-Path $pitRoot 'android-tools\jdk') -Directory | Select-Object -First 1).FullName+'\bin\keytool.exe'
try {
    $env:PIT_SIGNING_PASSWORD=$pitPassword
    & $pitKeytool -genkeypair -keystore $pitStore -storetype PKCS12 -alias twizypit-owner -keyalg RSA -keysize 3072 -validity 10000 -dname 'CN=Peter Twizy Pit Pro Owner, OU=Private Circuit Tools' -storepass:env PIT_SIGNING_PASSWORD -keypass:env PIT_SIGNING_PASSWORD
    if($LASTEXITCODE -ne 0){throw 'Signing-key generatie mislukt.'}
} finally {Remove-Item Env:PIT_SIGNING_PASSWORD -ErrorAction SilentlyContinue;$pitPassword=$null}
Write-Output 'Persoonlijke APK-signingsleutel aangemaakt; geheim beschermd met Windows DPAPI en gebruikersrechten.'
