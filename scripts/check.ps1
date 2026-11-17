$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
function Invoke-Checked { param([scriptblock]$Command) & $Command; if ($LASTEXITCODE -ne 0) { throw "Check failed with exit code $LASTEXITCODE" } }
Invoke-Checked { & ./.venv/Scripts/python.exe -m ruff check backend tests migrations }
Invoke-Checked { & ./.venv/Scripts/python.exe -m mypy backend }
Invoke-Checked { & ./.venv/Scripts/python.exe -m pytest -q }
Push-Location frontend
try {
    Invoke-Checked { npm.cmd run lint }
    Invoke-Checked { npm.cmd run typecheck }
    Invoke-Checked { npm.cmd test }
    Invoke-Checked { npm.cmd run build }
    Invoke-Checked { npm.cmd run test:e2e }
} finally { Pop-Location }
