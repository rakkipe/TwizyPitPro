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
    $pitArgs = @('"' + (Join-Path $pitRoot 'app.py') + '"')
    if (-not $LocalOnly) { $pitArgs += '--lan' }
    Start-Process -FilePath $pitPython -ArgumentList $pitArgs -WorkingDirectory $pitRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $pitRoot 'data\server.log') -RedirectStandardError (Join-Path $pitRoot 'data\server-error.log') | Out-Null
    for ($pitTry=0; $pitTry -lt 30; $pitTry++) {
        Start-Sleep -Milliseconds 200
        try { $pitStatus = Invoke-RestMethod -Uri "$pitUrl/api/bootstrap" -TimeoutSec 1; $pitActive = [bool]$pitStatus.version; if ($pitActive) { break } } catch {}
    }
}
if (-not $pitActive) { throw 'Twizy Pit Pro startte niet. Bekijk data\server-error.log.' }
if (-not $NoBrowser) { Start-Process $pitUrl }
