$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$emsPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $emsPython)) {
    throw 'Create the virtual environment and install requirements first. See README.md.'
}
& $emsPython -m uvicorn app.main:app --host 127.0.0.1 --port 8010
