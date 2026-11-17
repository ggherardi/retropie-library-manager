# Diagnostica Raspberry Pi

In Dispositivi selezionare il Raspberry ed eseguire Test SSH e diagnostica. L'aggiornamento è manuale: non vengono interrogati continuamente i dispositivi né modificati sistema operativo, kernel, firmware, emulatori o servizi.

Il report raccoglie modello da /proc/device-tree/model, hostname/IP, os-release, versione RetroPie dai file disponibili, versione EmulationStation dal log, uptime, temperatura, RAM e spazio tramite statvfs. Controlla presenza e permessi delle directory ROM/BIOS, stato del servizio SSH, SFTP, configurazione dei sistemi e core PS1. I valori non disponibili restano «Non rilevato».

Lo stato Online indica il successo dell'ultimo controllo SSH/SFTP, non un monitoraggio continuo. Un errore successivo viene mostrato senza cancellare il precedente report. L'indirizzo può essere modificato quando il DHCP cambia; la host key deve essere riconfermata per il nuovo indirizzo.

## RetroPie 4.8

L'installazione collaudata usa Raspbian Buster, Raspberry Pi 3 B+ e EmulationStation 2.10.1RP. La configurazione utente EmulationStation può essere un symlink verso /opt/retropie/configs/all/emulationstation. La versione e la configurazione dei core possono differire fra installazioni della stessa release RetroPie: il supporto CHD e i romset Arcade richiedono verifica specifica.

La presenza di un file e di un XML valido non dimostra che il core possa avviare il gioco o che i BIOS necessari siano disponibili. I test di lancio e compatibilità vanno eseguiti sull'hardware con contenuti autorizzati. Non vengono installati BIOS o aggiornamenti come parte della diagnostica.
