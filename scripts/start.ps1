$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path '.venv/Scripts/python.exe') -or -not (Test-Path 'frontend/dist/index.html')) { throw 'Eseguire prima Setup.cmd.' }
Write-Host 'Avvio con le preferenze locali/LAN salvate. Premere Ctrl+C per arrestare.'
& ./.venv/Scripts/python.exe -m backend.launch @args
exit $LASTEXITCODE
