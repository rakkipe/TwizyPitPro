$ErrorActionPreference = 'Stop'
$pitRoot = $PSScriptRoot
$pitPython = Join-Path $pitRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pitPython)) {
    $pitRuntime = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $pitRuntime) { & $pitRuntime -m venv (Join-Path $pitRoot '.venv') }
    elseif (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv (Join-Path $pitRoot '.venv') }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { python -m venv (Join-Path $pitRoot '.venv') }
    else { throw 'Installeer Python 3.12 of nieuwer en start Install.ps1 opnieuw.' }
    if ($LASTEXITCODE -ne 0) { throw 'Python-omgeving maken is mislukt.' }
}
& $pitPython -m pip install --disable-pip-version-check -r (Join-Path $pitRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Installatie pyserial is mislukt.' }
New-Item -ItemType Directory -Force -Path (Join-Path $pitRoot 'data') | Out-Null
$pitShell = New-Object -ComObject WScript.Shell
$pitShortcut = $pitShell.CreateShortcut((Join-Path $pitRoot 'Twizy Pit Pro.lnk'))
$pitShortcut.TargetPath = Join-Path $env:WINDIR 'System32\wscript.exe'
$pitShortcut.Arguments = '"' + (Join-Path $pitRoot 'Start.vbs') + '"'
$pitShortcut.WorkingDirectory = $pitRoot
$pitShortcut.IconLocation = (Join-Path $pitRoot 'web\icon.ico') + ',0'
$pitShortcut.Description = 'Twizy Pit Pro - diagnose en circuit tuning studio'
$pitShortcut.Save()
Write-Host 'Twizy Pit Pro is klaar. Open Twizy Pit Pro.lnk of Start.vbs.'
