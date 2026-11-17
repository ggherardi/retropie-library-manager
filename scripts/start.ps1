$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path '.venv/Scripts/python.exe') -or -not (Test-Path 'frontend/dist/index.html')) { throw 'Eseguire prima Setup.cmd.' }
Write-Host 'Aprire http://127.0.0.1:8000. Premere Ctrl+C per arrestare.'
& ./.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
exit $LASTEXITCODE
