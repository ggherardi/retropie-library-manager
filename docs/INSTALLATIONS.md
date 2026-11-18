# Installazione unificata — Incremento 7

## Uso quotidiano

Dalla versione 0.7.1 è possibile selezionare direttamente ZIP/7z: [preparazione automatica degli archivi](ARCHIVES.md), senza estrazione manuale. I job già caricati possono essere rianalizzati.

Aprire `Start.cmd` e http://127.0.0.1:8000. **Aggiungi giochi** è la pagina iniziale.

1. Selezionare file, più file o una cartella. Per PS1 selezionare insieme CUE e BIN, oppure la cartella completa. Il drag & drop delle cartelle usa le API del browser quando disponibili; resta disponibile il selettore cartella.
2. Controllare l'anteprima. **Importa e installa sul Raspberry** è la modalità predefinita. La modalità **solo PC** è esplicita.
3. Confermare una volta i diritti d'uso e avviare. La pipeline importa, cerca metadati e immagini consentite, prepara il dry-run, trasferisce e verifica. Non occorre aprire Sincronizzazione.
4. Seguire **Installazioni**. Gli elementi da verificare non fermano gli altri. Una scelta manuale non rende valido un hash sbagliato, una traccia mancante o un BIOS assente.

Il browser non restituisce percorsi Windows arbitrari: i file selezionati sono copiati in `data/inbox/<batch-id>`, con percorsi relativi conservati. Per dischi grandi già presenti sul PC, aprire **Usa le cartelle autorizzate**: il backend legge direttamente le sorgenti configurate e la propria cartella download, senza una seconda copia. Non cerca altrove nel computer. La ricorsione si decide prima della selezione; nell'upload la selezione già filtrata viene conservata integralmente.

Un upload interrotto si riprende selezionando il batch e gli stessi file: nome e dimensione non bastano, ogni blocco precedente viene confrontato via SHA-256. Massimi: 20.000 file, 16 GiB per file, 32 GiB per upload; i percorsi backend non hanno il limite di copia dell'upload. I file importati nell'inbox restano sorgenti della libreria: non cancellare quella cartella. Nessuna pulizia automatica elimina ROM o originali.

## Stati e significato

| Stato elemento | Significato e passaggio successivo |
| --- | --- |
| `ready` / `queued` | Anteprima valida; l'importazione richiede l'unica conferma del batch. |
| `awaiting_decision` | Ambiguità o componenti mancanti; scegliere una variante verificabile o saltare. Nessuna installazione automatica. |
| `validating` → `importing` | Nuovo controllo SHA-256 di tutti i file; creazione o riuso della riga Game nella stessa transazione. |
| `enriching` | Riutilizzo dei servizi Discovery, Media e Collections. Un'immagine non disponibile produce una nota, non un errore di installazione. |
| `preparing_sync` | Preflight core/BIOS, spazio e manifest. Un solo piano attivo per dispositivo, comprese le anteprime della pipeline. |
| `transferring` → `verifying` | Staging SFTP, verifica completa e pubblicazione atomica del gruppo. Il trasferimento non comporta avvio del gioco. |
| `installed` | Il servizio di sincronizzazione ha restituito il rapporto verificato, inclusi i metadati applicabili. Visibilità e avvio restano separati. |
| `pending_refresh` | ROM verificate, metadati rinviati perché EmulationStation è aperta. |
| `waiting_device` | Importazione locale conservata se autorizzata; ripresa automatica quando il dispositivo torna disponibile. |
| `imported_local` | Operazione solo PC: nessuna sincronizzazione, anche dopo pausa e ripresa. |
| `failed` | Fase, file, causa, operazione e rimedio persistenti. Riprova rigenera il piano quando necessario. |
| `paused` / `cancelled` / `ignored` | Nessuna nuova fase; i gruppi già pubblicati e i file importati restano conservati. |

Il batch ha inoltre un controllo persistente `run/pause/cancel`, distinto dal riepilogo degli elementi. Pausa e cancellazione sono cooperative: durante un'operazione locale si fermano al prossimo punto sicuro. Lo staging verificato di una pausa è riutilizzato; una cancellazione conserva quanto già pubblicato. La coda non può scrivere uno stato `installed` tramite le API di controllo o di identificazione: questo stato proviene esclusivamente da un SyncRun completato.

**Presente sul PC, file installati, visibile e avviato sono evidenze diverse.** La conferma «Lo vedo nel menu» registra soltanto la visibilità dichiarata dall'operatore. L'avvio usa l'evidenza GameInsight già esistente, legata a SHA-256 e dispositivo. Non viene dedotto da formato, core, XML o trasferimento riuscito. I contatori della dashboard contano operazioni, quindi includono tentativi ripetuti; il catalogo conta giochi unici.

## EmulationStation

Non viene mai avviata, chiusa, riavviata o ricaricata via SSH. Nessun riavvio del Raspberry.

Se è aperta, ROM e immagini possono essere trasferite; gamelist, raccolte e impostazioni restano in coda. Chiuderla **dal menu locale** e lasciarla chiusa. La pipeline controlla lo stato e genera un nuovo piano dai metadati salvati all'uscita, invece di riusare XML obsoleti. Quando non ci sono più metadati in attesa, riaprirla dalla console locale. I file precedenti hanno backup e controlli dell'hash prima della sostituzione; un conflitto resta un errore esplicito.

Le raccolte parziali aggiornano solo i giochi del batch, conservando membri estranei e ordine esistente. Non richiedono di trasferire tutti i classici né l'intera libreria. Il flusso avanzato di sincronizzazione completa della raccolta resta disponibile.

## Identificazione, dischi e BIOS

- Header iNES, Game Boy/GBC, GBA, SEGA/SMS e SNES dove verificabili; hash della libreria, Discovery e DAT attivi; nessuna percentuale inventata. File Markdown, documenti, configurazioni, salvataggi e accessori sono esclusi.
- Formati grezzi senza firma affidabile restano da verificare. Per PCE, Atari 2600, SG-1000 e NGP/NGPC è ammessa una dichiarazione manuale della piattaforma con limiti strutturali/dimensionali, senza affermare compatibilità o identità del titolo.
- CUE: riferimenti relativi sicuri, tutte le tracce presenti, settori allineati, indici validi, descrittore ISO9660 PlayStation e dimensione dichiarata. Dischi multipli e M3U raggruppati; i BIN non diventano giochi separati. Aggiungere una playlist agli stessi dischi/CUE non crea un duplicato logico.
- ISO richiede un descrittore PlayStation valido. CHD richiede identità PS1 verificata o dichiarata, `chdman verify` disponibile nel PATH, BIOS e supporto CHD già confermato nel dispositivo. Non si modifica il core. Un contenitore CHD da solo non identifica la console. PBP senza hash di una fonte conosciuta resta da verificare.
- ZIP/7z sono letti con i limiti e le protezioni del servizio arcade esistente. I componenti BIOS condivisi non sono una prova di identità di giochi diversi. Varianti plausibili derivano da dimensioni e hash dei componenti di gioco; completezza, parent/clone e dipendenze sono verificati separatamente nelle modalità split, merged, non-merged e full-non-merged.
- L'arcade usa la generazione DAT attiva e la corrispondenza documentata con il core reale. Set incompleti, CHD/software-list non verificabili e cloni merged non avviabili automaticamente restano bloccati. Non vengono convertiti o ricomposti archivi.
- Il validatore arcade rimane conservativo: richiede tutte le voci non opzionali del DAT, incluse le alternative BIOS se il DAT non le descrive come opzionali. Un inventario incompleto rispetto al DAT non prova che il programma di gioco sia corrotto né che non possa funzionare con un profilo BIOS diverso. Non vengono ignorate dipendenze senza evidenza.
- PS1: controllo del core configurato, inclusi override per gioco, e digest dei BIOS locali riconosciuti per PCSX ReARMed. È sufficiente un BIOS compatibile verificato; gli altri sono alternative. Gli hash documentati sono metadati, non firmware. [Documentazione primaria PCSX ReARMed](https://docs.libretro.com/library/pcsx_rearmed/).

Gli identificativi RLM restano nomi interni dei gruppi. Titoli verificati da fonti/hash hanno precedenza; un nome tecnico senza metadati richiede un titolo confermato dall'operatore. Le immagini provengono soltanto dal matching e dalle autorizzazioni già implementate; nessuna ricerca approssimativa associa copertine a titoli simili.

## Recupero e API

La migrazione additiva `0006` crea InstallationBatch, InstallationItem e InstallationUpload. Non modifica le tabelle della libreria esistente. Le sorgenti, le decisioni, i consensi, gli ID dei servizi sottostanti, gli errori e i rapporti sono persistenti. Un solo processo backend deve usare la directory dati; avviare con gli script forniti, senza worker Uvicorn multipli.

All'avvio una scansione interrotta riparte senza duplicare le righe; i candidati già salvati sono riusati. L'importazione è idempotente per SHA-256 e, per PS1, per lo stesso insieme di dischi/CUE quando differisce soltanto la playlist. Un trasferimento autorizzato interrotto riusa ID del manifest e staging, verificando i parziali; rete e timeout hanno tentativi limitati. Conflitti o metadati cambiati richiedono un nuovo dry-run. Nessuna autorizzazione viene dedotta dal semplice tempo trascorso.

Endpoint principali (schema completo in `/docs`):

| Endpoint | Scopo |
| --- | --- |
| `GET /api/installations` | Riepiloghi e dispositivi, senza payload pesanti dei candidati. |
| `GET /api/installations/sources` | Navigazione entro le sorgenti autorizzate. |
| `POST /api/installations/local` | Analisi di file/cartelle del backend; chiave di idempotenza. |
| `POST /api/installations/uploads` | Manifest di upload con percorsi relativi verificati. |
| `PUT /api/installations/{id}/uploads/{file}?offset=…` | Blocchi fino a 8 MiB, header `X-Chunk-SHA256`; ricevute persistenti e ripresa. |
| `POST /api/installations/{id}/analyze` | Analisi soltanto dopo upload completi. |
| `GET /api/installations/{id}` | Dettaglio paginato, risultati, errori e progresso. |
| `POST /api/installations/{id}/confirm` | Unica conferma, con modalità offline e arricchimento. |
| `POST /api/installations/{id}/control` | Pausa, ripresa, retry e cancellazione. |
| `POST /api/installations/items/{id}/decision` | Variante/piattaforma/titolo verificabile oppure esclusione. |
| `POST /api/installations/items/{id}/retry` | Nuovo tentativo di un singolo elemento. |
| `POST /api/installations/items/{id}/visible` | Conferma locale della visibilità, distinta dall'avvio. |

Tutte le mutazioni richiedono il controllo locale CSRF già esistente. Nessun percorso client diventa un comando shell. Upload: traversal, ADS, nomi riservati Windows, collisioni case-insensitive e symlink fuori dall'inbox sono rifiutati; memoria limitata ai blocchi, hash finale fuori dall'event loop e recupero della finestra fra rename e commit della ricevuta.

## Verifiche

`Check.cmd` / `scripts/check.ps1` esegue lint, mypy, pytest, frontend lint/typecheck/test/build e Playwright. I test browser si possono eseguire separatamente con `npm run test:e2e` dalla cartella frontend e usano server e dispositivo sintetici isolati. Nessuna fixture commerciale è inclusa. Il rapporto del collaudo effettivo è in [VALIDATION-INCREMENT7.md](VALIDATION-INCREMENT7.md).
