# Collaudo Incremento 3

Eseguito su Windows 11 il 17 novembre 2026. Le prove automatiche usano dati sintetici; i risultati hardware sotto riportati sono verifiche separate effettuate sul Raspberry reale.

## Verifiche automatiche

- 80 test pytest superati: regressioni degli incrementi precedenti, migrazione, SSH/host key, conferma e persistenza, interruzioni/retry, annullamento, spazio, permessi, file mancanti/modificati, symlink/traversal, gruppi BIN/CUE multidisco, CHD, copertine, XML e preservazione dei metadati, backup/idempotenza authorized_keys.
- 4 test Vitest superati.
- 4 flussi Playwright superati: libreria/esportazione, Discovery manuale, Discovery automatico, Dispositivi/SSH/diagnostica/sincronizzazione/ripetizione senza trasferimenti. Include controllo responsive a 390 px.
- Ruff, mypy, ESLint, TypeScript e build Vite superati.

Le fixture SFTP sono locali e confinate al server E2E. Non simulano una connessione riuscita nell'app di produzione. Il client SSH/SFTP reale è stato verificato separatamente come segue.

## Raspberry reale

- Raspberry Pi 3 Model B Plus Rev 1.3, Raspbian GNU/Linux 10 Buster.
- RetroPie 4.8, EmulationStation 2.10.1rp rilevata dal log.
- Connessione SSH Ed25519 con host key già registrata in Windows, poi fissata nel known_hosts dedicato.
- Installazione della chiave pubblica completata dall'utente nel terminale interattivo; nessuna password ricevuta dall'app o in chat.
- Chiave privata locale con ACL dell'utente Windows senza ereditarietà; authorized_keys remoto con permessi 600. Non è stato necessario un backup remoto in questa installazione iniziale perché non è stato sostituito un authorized_keys preesistente. La procedura con file esistente è verificata nei test automatici.
- SSH e SFTP operativi; directory ROM/BIOS presenti, leggibili e scrivibili dall'utente configurato.
- Filesystem: 31.092.658.176 byte totali, circa 27.032.866.816 byte disponibili alla prima misura. Le misure cambiano durante l'uso e vengono rilette a ogni piano e trasferimento.
- Percorso EmulationStation effettivo: `/opt/retropie/configs/all/emulationstation`, alias della cartella utente. Sistemi da `/etc/emulationstation/es_systems.cfg`.

## Prove SFTP in directory temporanea

Creato un percorso dedicato nella home di pi. Trasferiti 71.680 byte sintetici con nome Unicode, spazi e `&`; SHA-256 locale/remoto coincidenti. Una seconda verifica ha riconosciuto il file identico e saltato la copia. Un trasferimento più grande è stato interrotto a 65.536 byte e ripreso dal prefisso verificato, con SHA-256 finale corretto. La directory e soltanto i suoi file sono stati rimossi al termine.

## Prova RetroPie con contenuto autorizzato

È stato riutilizzato **2048gb**, licenza Zlib, già acquisito nel collaudo dell'Incremento 2. Nessun nuovo download è stato avviato. La copia è disponibile anche nella libreria principale e conserva provenienza e prova di autorizzazione.

Il dry-run ha richiesto 32.987 byte: ROM da 32.768 byte e proposta XML da 219 byte. Trasferimento tramite la normale API di conferma e il worker SFTP, pubblicazione del gruppo e hash remoto verificati. Destinazione:

`/home/pi/RetroPie/roms/gb/rlm-3ea2376b15b34bd26b10e6b3/2048.gb`

SHA-256:

`3ea2376b15b34bd26b10e6b31d2753bf8b086098dbdb5ee84d9c0f03d66d3d7f`

Il secondo dry-run rileva la ROM come già presente e richiede solo i 219 byte dei metadati. EmulationStation è rimasta attiva: la scrittura del gamelist è stata correttamente rinviata e non sono stati modificati XML preesistenti. È richiesta l'autorizzazione dell'utente prima di chiudere/riavviare EmulationStation e completare questa parte del collaudo.

## Limiti delle verifiche

- Scrittura del gamelist nella destinazione reale: in attesa dell'autorizzazione a chiudere EmulationStation. Generazione, merge, backup e ripetizione senza modifiche sono verificati automaticamente.
- Lancio del gioco nell'emulatore: non eseguito e non dichiarato verificato.
- BIN/CUE, multidisco, CHD e copertine: coperti dai test sintetici; nessuna immagine PS1 o BIOS commerciale è stata trasferita per il collaudo.
- MicroSD 128 GB e prestazioni con grandi librerie remote: non provate su hardware; la capacità viene comunque letta dal filesystem effettivo.
- Nessun aggiornamento di sistema operativo, kernel, firmware, RetroPie o core fa parte del collaudo.
