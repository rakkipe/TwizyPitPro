$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Testfout.' }
} finally { Pop-Location }
