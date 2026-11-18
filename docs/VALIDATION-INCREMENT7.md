# Incremento 7 — implementazione e collaudo

Data: 18 novembre 2026. Versione applicativa: **0.7.0**.

## Risultato

Il percorso predefinito **Aggiungi giochi** esegue analisi, importazione, arricchimento e installazione verificata con una sola conferma iniziale. Non richiede una seconda sincronizzazione manuale. Il collaudo reale ha aggiunto **Crash Bandicoot (USA)** al Raspberry, conservando Vagrant Story e gli altri giochi. F-FF, già presente, è stato riconosciuto senza duplicarlo. Metal Slug 5 è rimasto da verificare senza impedire le altre installazioni.

La presenza dei file, la visibilità nel menu e l'avvio sono evidenze separate. Dopo la verifica tecnica, l'utente ha confermato dalla console locale: **«Crash è visibile e si avvia»**. La visibilità è registrata negli elementi di installazione e l'avvio riuscito in GameInsight come testimonianza dell'operatore, legata al dispositivo e allo SHA-256 del gioco. Il collaudo end-to-end è concluso; non si deducono durata della partita, progressione o completamento del gioco. Vagrant Story era già stato avviato con esito positivo dall'utente nell'Incremento 6.1; non è stata eseguita una nuova partita durante questo collaudo.

## Architettura implementata

- **Orchestratore persistente:** tre tabelle additive per batch, elementi e upload; checkpoint, consensi, decisioni, errori e riferimenti ai job esistenti. Riavvio del backend, retry, pausa e cancellazione non ricreano giochi o dichiarano validi trasferimenti incompleti.
- **Servizi riutilizzati:** importazione idempotente condivisa con il flusso precedente, Discovery e Media per metadati autorizzati, CatalogRun per arricchimento, SyncRun per dry-run e trasferimento SFTP. Un solo piano della pipeline attivo per dispositivo e un solo worker SFTP evitano scritture concorrenti sugli stessi metadati.
- **Input:** selezione singola, multipla, cartella e drag & drop; ricorsione opzionale; upload a blocchi con SHA-256 e ripresa oppure lettura diretta delle sole cartelle autorizzate. Nessun accesso arbitrario ai percorsi del PC dal browser.
- **Identificazione:** header, struttura, hash locali/Discovery/DAT e componenti degli archivi. Documenti, configurazioni e accessori sono esclusi; i BIOS riconosciuti sono separati. Le ambiguità hanno motivazione, candidati e decisione indipendente dal resto del batch.
- **PS1:** gruppi CUE/BIN, ISO PlayStation, multidisco e M3U con riferimenti relativi controllati; completezza e integrità prima del trasferimento. Una playlist aggiunta agli stessi dischi non crea un altro gioco. Nessuna modifica automatica alla configurazione PS1.
- **Arcade:** validatori DAT e core esistenti, parent/clone, ZIP/7z e dipendenze; i BIOS condivisi non identificano da soli un titolo. Nessuna conversione o ricomposizione automatica dei set.
- **BIOS e core:** controllo preventivo del core effettivamente configurato e delle dipendenze. Per PCSX ReARMed è sufficiente un BIOS alternativo riconosciuto e verificato. Nessun download di firmware protetto.
- **Sincronizzazione:** riserva di spazio, staging riprendibile, pubblicazione atomica dei gruppi, hash SHA-256 e rilevamento dei conflitti. Le raccolte parziali preservano gli altri membri e il loro ordine.
- **EmulationStation:** ROM trasferibili mentre è aperta; gamelist e raccolte restano in coda persistente. Dopo la chiusura locale viene creato un piano aggiornato sui metadati finali. Nessun avvio, arresto o riavvio via SSH e nessun reboot del Raspberry.
- **Interfaccia:** Aggiungi giochi, La mia libreria, Grandi Classici, Da Recuperare e Installazioni nella navigazione principale; strumenti precedenti disponibili in Avanzate. Dashboard con stati per elemento, spazio, errori e rimedi; visibilità e avvio distinti dall'installazione. Layout verificato anche a 390 px.

Dettagli operativi e API: [INSTALLATIONS.md](INSTALLATIONS.md). Architettura generale: [ARCHITECTURE.md](ARCHITECTURE.md).

## Test automatici eseguiti

| Controllo | Risultato |
| --- | --- |
| Backend `pytest -q` | **181 superati**, nessun fallimento |
| Backend Ruff | Superato |
| Backend mypy | Superato |
| Frontend Vitest | **11 superati**, nessun fallimento |
| Frontend ESLint | Superato |
| Frontend TypeScript | Superato |
| Frontend build Vite | Superata |
| Browser Playwright, suite completa | **7 superati**, nessun fallimento |
| Nuovo scenario browser dopo miglioramento dell'isolamento della fixture | Superato nuovamente; non contato due volte |

Totale della suite: **199 test**. I dati dei test sono sintetici; il dispositivo dei test browser è simulato e isolato dal Raspberry reale. Nessuna ROM commerciale è una fixture del repository.

La nuova copertura comprende importazione singola e massiva, modalità solo PC, installazione automatica, duplicati, file non-ROM, BIOS, arcade/Neo Geo, CUE/BIN e multidisco, file mancanti o modificati, metadati/immagini indisponibili, dispositivo offline, riserva di spazio, interruzione e ripresa, crash del backend, retry, idempotenza, conflitti, salvataggi, EmulationStation aperta e coda metadati. Sono verificati anche upload interrotti, ricevute dei blocchi, traversal/collisioni, la finestra fra rename e commit dell'upload, titoli tecnici da correggere e pausa/ripresa della modalità esclusivamente locale.

Le prove di guasto, di pausa durante il trasferimento e di recupero dopo crash sono automatiche. Il collaudo fisico non ha simulato un'interruzione di corrente o di rete del Raspberry.

## Collaudo sul Raspberry reale

Dispositivo: Raspberry Pi 3 B+, RetroPie 4.8, connessione SSH/SFTP e host key già configurate. Database salvato prima della migrazione; la migrazione `0006` è stata applicata senza ricreare la libreria.

I file locali utilizzati erano già presenti nelle sorgenti autorizzate. Nessun nuovo download commerciale o di BIOS è stato eseguito.

| Misura | Risultato osservato |
| --- | --- |
| Giochi nella libreria PC prima e dopo | **99 → 99** |
| Giochi sul Raspberry prima e dopo | **98 → 99** |
| Nuove righe Game create dal collaudo | **0**: Crash e F-FF erano già importati |
| Giochi selezionati validi | **2**: Crash Bandicoot (USA), F-FF |
| Nuovi giochi effettivamente trasferiti | **1**: Crash Bandicoot (USA) |
| Nuovo titolo visibile e avviato, confermato dall'utente | **1**: Crash Bandicoot (USA) |
| Nuovi file ROM | **2**: CUE e BIN di Crash |
| Dimensione dei nuovi file ROM | **632.083.623 byte** |
| Trasferimento iniziale Crash, metadati inclusi | **632.084.170 byte** |
| Trasferimento F-FF già presente | **0 byte** |
| Seconda esecuzione completa, Crash + F-FF | **0 byte trasferiti per entrambi** |
| File preesistenti confrontati e invariati | **264**, inclusi **3 salvataggi** |
| Gamelist XML validi dopo l'installazione | **12** |
| Gamelist modificati | **1**, PS1, con backup verificato |
| Membri Grandi Classici conservati e presenti | **7** |
| Spazio libero rilevato | **25.607.294.976 byte**, circa **23,85 GiB** |
| Riserva minima | **4 GiB**, rispettata |
| Dimensione dei file inventariati nella libreria remota gestita | **1.422.798.497 byte**, circa **1,33 GiB**, inclusi file accessori inventariati |
| Nuove immagini aggiunte dal collaudo | **0**; assenza di una fonte autorizzata non bloccante |

Il primo batch è passato attraverso il nuovo orchestratore, senza conferme separate per importazione, arricchimento e sincronizzazione. Le ambiguità di Metal Slug 5 non hanno fermato i due elementi validi. Il secondo batch ha ripetuto lo stesso flusso e verificato i file esistenti, senza riscriverli.

Tutti i file presenti nell'inventario precedente sono rimasti allo stesso percorso con lo stesso SHA-256. Sono stati preservati i salvataggi di 2048, Tobu e Vagrant Story. Sono rimasti invariati il core `lr-pcsx-rearmed`, il BIOS PS1 verificato, `emulators.cfg`, le configurazioni EmulationStation e la raccolta Grandi Classici. Il record XML di Vagrant Story è invariato. Il nuovo record di Crash ha un titolo leggibile e riferimenti risolti.

La verifica dei file e degli XML non prova che un titolo sia giocabile. Per Crash, visibilità e avvio sono confermati separatamente dall'utente sulla console locale; per F-FF questo collaudo attesta la presenza e l'integrità dei file, non una nuova sessione di gioco. I conteggi e i confronti dei file riportati sopra sono quelli rilevati prima della successiva prova locale.

### Distribuzione dei 99 titoli remoti

| Piattaforma RetroPie | Titoli |
| --- | ---: |
| Atari 2600 | 1 |
| FBA | 1 |
| Game Boy | 28 |
| Game Boy Advance | 12 |
| Game Boy Color | 6 |
| MAME libretro | 14 |
| Master System | 3 |
| Mega Drive | 7 |
| NES | 23 |
| PC Engine | 1 |
| PlayStation | 2 |
| SNES | 1 |

## Caso reale Metal Slug 5

L'archivio originale è rimasto invariato. Il confronto dei contenuti individua **Metal Slug 5 (NGM-2680)** come candidato coerente con **13 componenti di gioco** corrispondenti al DAT FBNeo associato al core installato. I componenti BIOS condivisi sono esclusi dalla selezione dell'identità: non producono più decine di candidati estranei.

Il set non supera la validazione completa del profilo DAT/BIOS disponibile. Le **12 voci BIOS distinte mancanti o con hash non corrispondente** sono:

```
neo-epo.bin
neo-po.bin
neodebug.bin
neopen.sp1
sp-j3.sp1
sp-s3.sp1
sp1-j3.bin
sp1-u2
sp1-u3.bin
sp1-u4.bin
uni-bios_3_3.rom
uni-bios_4_0.rom
```

Il DAT descrive queste alternative come voci non opzionali e il validatore conservativo le richiede. Questo risultato **non dimostra che il programma di gioco sia corrotto o che ogni BIOS elencato sia necessario contemporaneamente all'emulatore**. Serve un profilo BIOS verificabile o un inventario che soddisfi il DAT, senza ignorare dipendenze sulla base del nome dell'archivio. L'interfaccia espone candidato, voci mancanti e motivo del blocco. Nessun trasferimento di Metal Slug 5 e nessun recupero automatico di BIOS protetti.

## Limiti e verifiche ancora distinte

- Il backend deve essere eseguito con un solo processo per directory dati; non usare più worker Uvicorn sulla stessa coda.
- CHD richiede `chdman verify` disponibile, identità PS1 confermata e supporto dichiarato nel dispositivo. Non sono stati trasferiti CHD reali in questo collaudo.
- I formati senza una firma affidabile richiedono una scelta manuale motivata. Il riconoscimento di una piattaforma non equivale a una prova d'avvio.
- Il controllo arcade rimane conservativo sulle alternative BIOS descritte dai DAT. Metal Slug 5 resta da verificare.
- La verifica SHA-256 remota legge i file via SFTP: sui dischi PS1 grandi anche una ripetizione a zero trasferimenti può richiedere alcuni minuti.
- La conferma dell'operatore attesta visibilità e avvio di Crash; non comprende una verifica estesa della partita. EmulationStation è stata riaperta dalla console locale, senza avvii via SSH.

ROM, BIOS, salvataggi, database, report runtime e credenziali restano esclusi dal repository. Le evidenze dettagliate del collaudo sono conservate localmente nella directory runtime ignorata da Git.
