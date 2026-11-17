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

Il secondo dry-run ha rilevato la ROM come già presente e richiesto solo i 219 byte dei metadati. Con EmulationStation ancora attiva, la prima scrittura del gamelist è stata correttamente rinviata e non sono stati modificati XML preesistenti.

### Completamento dopo autorizzazione dell'utente

Ricevuta l'autorizzazione esplicita alla chiusura e al riavvio, EmulationStation è stata chiusa con SIGTERM gestito, senza terminazione forzata. Non risultavano emulatori o giochi attivi. È stata chiusa anche un'istanza aggiuntiva avviata durante il precedente controllo manuale con `--version`: questa opzione non termina il programma su tale installazione. La diagnostica dell'app legge la versione dal log e non esegue il frontend.

Un nuovo dry-run e la normale API di conferma hanno trasferito esclusivamente **219 byte di XML**, saltando la ROM identica. Il gamelist è nuovo: non è stato sostituito alcun XML preesistente e non era necessario un backup in questa prova. Destinazione effettiva:

`/opt/retropie/configs/all/emulationstation/gamelists/gb/gamelist.xml`

Verificati parsing XML, titolo `2048gb`, riferimento relativo `./rlm-3ea2376b15b34bd26b10e6b3/2048.gb`, presenza della ROM e suo SHA-256. Hash del gamelist da 219 byte:

`7a21991fa8cfe9921b5a6b066f11e531b154893d361a9a94d0bb12ae35bccb7f`

La ripetizione completa, con nuova anteprima e conferma, ha richiesto e trasferito **0 byte**: ROM e gamelist risultano già presenti, senza metadati rinviati.

**Correzione emersa prima dell'Incremento 4:** l'avvio via SSH con riferimento a `/dev/tty1` non aveva un terminale di controllo valido (`TTY_NR=0`). La finestra e il processo non costituivano una verifica sufficiente: l'utente ha riscontrato errori `/dev/tty` e mancato avvio dei giochi. Ha ripristinato la sessione con reboot completo e avviato correttamente 2048GB con EasySMX USB. L'Incremento 4 registra questo esito come dichiarazione dell'operatore e verifica la sessione esclusivamente in lettura. Non ripetere quel metodo SSH. Nessun test di gioco era stato eseguito dall'assistente durante l'Incremento 3.

## Limiti delle verifiche

- Scrittura di un nuovo gamelist e ripetizione senza modifiche: verificate sul Raspberry. Merge e backup di gamelist preesistenti: verificati nei test automatici; non era presente un gamelist Game Boy da sostituire nel collaudo reale.
- Lancio del gioco nell'emulatore: non eseguito e non dichiarato verificato.
- BIN/CUE, multidisco, CHD e copertine: coperti dai test sintetici; nessuna immagine PS1 o BIOS commerciale è stata trasferita per il collaudo.
- MicroSD 128 GB e prestazioni con grandi librerie remote: non provate su hardware; la capacità viene comunque letta dal filesystem effettivo.
- Nessun aggiornamento di sistema operativo, kernel, firmware, RetroPie o core fa parte del collaudo.
