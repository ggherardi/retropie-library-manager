$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
function Invoke-Checked { param([scriptblock]$Command) & $Command; if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE" } }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Installare Python 3.10+ e aggiungerlo al PATH.' }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Installare Node.js 22.12+ LTS.' }
if (-not (Test-Path '.venv/Scripts/python.exe')) { Invoke-Checked { python -m venv .venv } }
Invoke-Checked { & ./.venv/Scripts/python.exe -m pip install --upgrade pip }
Invoke-Checked { & ./.venv/Scripts/python.exe -m pip install -r requirements-lock.txt }
Invoke-Checked { & ./.venv/Scripts/python.exe -m pip install --no-deps -e . }
Push-Location frontend
try { Invoke-Checked { npm.cmd ci }; Invoke-Checked { npm.cmd run build } } finally { Pop-Location }
Write-Host 'Installazione completata. Avviare Start.cmd.'
