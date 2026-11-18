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
$sevenZip = if ($env:RLM_7ZIP) { $env:RLM_7ZIP } else { Join-Path $env:ProgramFiles '7-Zip/7z.exe' }
$engineReady = $false
if (Test-Path -LiteralPath $sevenZip) {
    $versionText = & $sevenZip i | Out-String
    if ($versionText -match '7-Zip[^\r\n]*?\b(\d+)\.(\d+)\b') {
        $engineReady = ([version]"$($Matches[1]).$($Matches[2])" -ge [version]'26.6')
    }
}
if (-not $engineReady) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw 'Serve 7-Zip 26.06+: installarlo da https://7-zip.org/download.html e ripetere Setup.cmd.' }
    Invoke-Checked { winget install --id 7zip.7zip --exact --source winget --silent --accept-source-agreements --accept-package-agreements }
}
Write-Host 'Installazione completata. Avviare Start.cmd.'
