param([switch]$LocalOnly, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$pitRoot = $PSScriptRoot
$pitPython = Join-Path $pitRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pitPython)) {
    & (Join-Path $pitRoot 'Install.ps1')
}
$pitUrl = 'http://127.0.0.1:8765'
$pitActive = $false
try {
    $pitStatus = Invoke-RestMethod -Uri "$pitUrl/api/bootstrap" -TimeoutSec 2
    $pitActive = [bool]$pitStatus.version
} catch {}
if (-not $pitActive) {
    New-Item -ItemType Directory -Force -Path (Join-Path $pitRoot 'data') | Out-Null
    $pitArgs = @('"' + (Join-Path $pitRoot 'app.py') + '"')
    if (-not $LocalOnly) { $pitArgs += '--lan' }
    Start-Process -FilePath $pitPython -ArgumentList $pitArgs -WorkingDirectory $pitRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $pitRoot 'data\server.log') -RedirectStandardError (Join-Path $pitRoot 'data\server-error.log') | Out-Null
    for ($pitTry=0; $pitTry -lt 30; $pitTry++) {
        Start-Sleep -Milliseconds 200
        try { $pitStatus = Invoke-RestMethod -Uri "$pitUrl/api/bootstrap" -TimeoutSec 1; $pitActive = [bool]$pitStatus.version; if ($pitActive) { break } } catch {}
    }
}
if (-not $pitActive) { throw 'Twizy Pit Pro startte niet. Bekijk data\server-error.log.' }
if ($pitStatus.lan -isnot [bool] -or $pitStatus.lan -ne (-not $LocalOnly)) {
    $pitRequestedMode = if ($LocalOnly) { 'alleen lokaal' } else { 'met LAN-viewer' }
    throw "De actieve server draait niet in de gevraagde modus ($pitRequestedMode). Sluit de bestaande server eerst af en start opnieuw; een lopende voertuigactie wordt niet automatisch onderbroken."
}
if (-not $NoBrowser) { Start-Process $pitUrl }
