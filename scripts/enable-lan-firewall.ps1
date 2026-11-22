[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param(
    [Parameter(Mandatory=$true)][string]$InterfaceAlias,
    [ValidateRange(1024,65535)][int]$Port=8000,
    [switch]$SetPrivate
)
$ErrorActionPreference='Stop'
$simulation = $WhatIfPreference
$WhatIfPreference = $false
Import-Module NetTCPIP,NetSecurity
$WhatIfPreference = $simulation
Set-Location (Split-Path $PSScriptRoot -Parent)
$interface = Get-NetIPConfiguration -InterfaceAlias $InterfaceAlias
if (-not $interface.IPv4DefaultGateway) { throw 'Selezionare la connessione domestica con gateway, non una scheda virtuale.' }
$address = @($interface.IPv4Address)[0]
if (-not $address) { throw 'Nessun IPv4 disponibile.' }
$network = & ./.venv/Scripts/python.exe -c 'import ipaddress,sys; a=ipaddress.ip_address(sys.argv[1]); assert a.is_private and not a.is_link_local; print(ipaddress.ip_network(sys.argv[1]+chr(47)+sys.argv[2],strict=False))' $address.IPAddress $address.PrefixLength
if ($LASTEXITCODE -ne 0) { throw 'Indirizzo locale non valido.' }
$pythonPath = & ./.venv/Scripts/python.exe -c 'import sys; print(sys._base_executable)'
$profile = Get-NetConnectionProfile -InterfaceIndex $interface.InterfaceIndex
Write-Host "Interfaccia: $InterfaceAlias; IPv4: $($address.IPAddress); subnet: $network; TCP: $Port; programma: $pythonPath"
if ([int]$profile.NetworkCategory -ne 1) {
    if (-not $SetPrivate) { throw 'Il profilo non è Privato. Il passaggio richiede consenso esplicito e -SetPrivate.' }
    if ($PSCmdlet.ShouldProcess($InterfaceAlias, 'Impostare soltanto questa connessione come rete Privata')) {
        Set-NetConnectionProfile -InterfaceIndex $interface.InterfaceIndex -NetworkCategory Private
    }
}
$ruleName = "RetroPieLibraryManager-LAN-$Port"
if (Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue) { throw "La regola $ruleName esiste già: verificarla prima di modificarla. Nessuna regola sostituita." }
if ($PSCmdlet.ShouldProcess($ruleName, "Consentire TCP $Port soltanto da $network, profilo Privato, interfaccia $InterfaceAlias e Python dell'app")) {
    New-NetFirewallRule -Name $ruleName -DisplayName "RetroPie Library Manager LAN $Port" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -RemoteAddress $network -LocalAddress $address.IPAddress -Profile Private -InterfaceAlias $InterfaceAlias -Program $pythonPath | Out-Null
}
Write-Host 'Nessuna modifica al router, nessun port forwarding, nessuna altra regola modificata. Se cambia subnet/IP, verificare la regola prima di aggiornarla.'
