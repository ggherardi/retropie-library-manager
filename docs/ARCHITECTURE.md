# Architettura

## Installazioni unificate (Incremento 7)

La migrazione additiva e reversibile `0006` aggiunge tre tabelle: batch, elementi e ricevute degli upload. `installations.py` è un orchestratore persistente sopra i servizi esistenti: riusa l'importazione estratta in `import_service.py`, Acquisition, MediaService, Collections e DeviceService. Non usa chiamate HTTP interne e non introduce un secondo motore SFTP. Il worker locale è seriale; i trasferimenti passano sempre dal worker seriale del servizio dispositivi, condiviso con le schermate avanzate.

`identification.py` e `content_checks.py` verificano formati, header, dipendenze CUE/M3U e hash, interrogando i DAT attivi e riusando il validatore ZIP/7z. Il confronto di varianti riutilizza soltanto inventari legati a percorso, dimensione e timestamp, senza tenere ROM decompresse in memoria. Il digest del rapporto arcade è ricontrollato contro il candidato. I chip BIOS comuni non sono evidenza di identità di giochi diversi. Formati, identità, completezza e compatibilità restano campi distinti.

`installation_preflight.py` legge core configurato, override e BIOS senza inizializzare emulatori. Il controllo arcade esistente verifica poi generazione DAT, core reale, dipendenze e BIOS remoto. `installation_routes.py` fornisce navigazione entro radici autorizzate e upload limitati a blocchi con checksum; ricevute persistenti gestiscono tail non committati e rename riusciti prima del commit. Le copie nell'inbox diventano sorgenti della libreria, non file temporanei eliminabili dopo l'importazione.

L'orchestratore conserva gli ID dei job Media/Intelligence e SyncRun. Conferma e richieste sono idempotenti; un SyncRun completato viene riconciliato senza duplicare il gioco. Tentativi di rete riusano staging e autorizzazione; conflitti producono un nuovo piano solo dopo retry. Pausa conserva staging; cancellazione conserva gruppi pubblicati e salvataggi. Aggiornamenti del progresso SFTP sono limitati a circa cinque al secondo, salvo cambi di file/fase e rapporti, per non effettuare un commit SQLite per ogni blocco. La lettura degli hash usa prefetch SFTP limitato a 16 richieste, con memoria limitata.

Un solo piano della pipeline per dispositivo può attendere la conferma interna: evita anteprime simultanee costruite sullo stesso vecchio gamelist. La sincronizzazione seleziona soltanto il gioco corrente. L'opzione `collection_partial` aggiorna i suoi riferimenti, conservando membri e ordine esterni; il flusso avanzato completo conserva il vincolo della selezione di tutti i membri.

`pending_refresh` sopravvive ai riavvii. Dopo la chiusura locale di EmulationStation il worker ricostruisce il piano dai metadati correnti e riusa i controlli di integrità, backup e pubblicazione atomica. Il controllo finale di EmulationStation rimane nel motore di sincronizzazione: la cache diagnostica dell'orchestratore non autorizza una scrittura. Nessun comando SSH avvia, ferma o riavvia EmulationStation.

`Installations.tsx` è il punto d'ingresso predefinito. Le API browser trasferiscono contenuti e percorsi relativi, senza simulare accesso a percorsi Windows. Anteprima e conferma avviano tutta la pipeline; i casi ambigui non bloccano gli altri. La dashboard distingue presenza PC, file remoti verificati, visibilità dichiarata e prova di avvio associata a hash/dispositivo. Stati, API, limiti e procedure di recupero sono descritti in [INSTALLATIONS.md](INSTALLATIONS.md).

## Collezioni e media (Incremento 6)

La migrazione additiva congelata `0005` introduce EssentialClassic, GameCuration, MediaAsset e MediaPlan. Conserva Game, i percorsi locali, GameInsight e la storia dei trasferimenti. Il catalogo statico versionato viene importato con inserimenti multipli; la revisione SHA-256 evita riscritture a ogni avvio. Gli elenchi dei classici sono paginati con count/offset/limit SQL; il filtro delle copie possedute controlla anche l'esistenza effettiva dei file. Il modulo DAT/FTS5 mantiene i flussi massivi preesistenti.

`collections.py` distingue identità, presenza, inclusione manuale, completezza e prova di gioco. Il matching automatico richiede hash corrente e piattaforma oppure un'identità DAT validata alla generazione attiva. Le corrispondenze ambigue non entrano automaticamente nella raccolta. Preferenze manuali e note di revisione sono persistenti; l'impronta dei metadati rende obsolete le verifiche dopo una modifica.

`media.py` riutilizza matching, client HTTP protetto e coda Intelligence. Un MediaPlan conserva candidati, identità e impronte della fonte; l'applicazione ricontrolla ROM, fonte e assegnazione precedente prima di aggiornare. MediaAsset conserva la cronologia. Cache PNG e ricevuta JSON sono esterne al repository. Copertine usano Game.cover_path; screenshot usano GameInsight.screenshot_path. La licenza degli asset è verificata separatamente; la whitelist delle ROM non viene ampliata dalle eccezioni per le immagini.

`es_collections.py` verifica marcatori nel binario remoto e genera il formato custom-<nome>.cfg documentato da RetroPie. Il parser di es_settings.cfg gestisce il frammento XML senza radice usato da Settings.cpp, conserva gli elementi estranei e cambia soltanto l'abilitazione della raccolta. `sync_engine.py` include screenshot, raccolta e impostazioni nel piano esistente: dimensioni, original SHA, backup, pubblicazione atomica e rinvio con EmulationStation attiva. L'impronta della libreria blocca piani diventati obsoleti. La raccolta richiede tutti i membri nel piano; le righe esterne al manifest restano intatte.

`Collections.tsx` offre le tre viste e la dashboard qualità con dettagli, anteprima immagini e correzioni. Le copie mancanti non sono visualizzate come installate. Le API `/api/collections` e `/api/media` sono documentate nell'OpenAPI locale. La [guida operativa](COLLECTIONS.md) descrive fonti, diritti, collezioni RetroPie, limiti e visualizzazione su TV.

## Cataloghi massivi e Arcade Intelligence (Incremento 4)

La migrazione congelata `0004` aggiunge CatalogSource, CatalogEntry, CatalogRun, GameInsight, ArcadeValidation, CatalogPreference, CoreBinding e SyncPresence, più FTS5 e trigger insert/delete. Game e Device esistenti restano invariati. La cronologia sync precedente viene adottata solo a parità di hash dei file.

`catalog_formats.py` espone iteratori XML sicuro, DAT ClrMamePro, JSON/ijson e CSV. La memoria contiene un record, un blocco di 250 inserimenti e l'indice compatto nome/parent per risolvere le famiglie. UID stabile per fonte/nome e hash del payload distinguono aggiunte e modifiche. Una generazione in staging viene pubblicata con un cambio atomico di active_run; errori/cancel conservano quella precedente. FTS si aggiorna nella stessa transazione. Le risposte di elenco sono paginate ed escludono i componenti.

`intelligence.py` coordina un worker seriale dedicato, importazioni, validazioni, matching e rapporti persistenti. All'avvio ripulisce lo staging interrotto. La cancellazione ha effetto fino alla pubblicazione atomica. `official_catalogs.py` usa repository/percorsi prefissati, revisioni Git e hash verificati del DAT e dei driver. La provenienza ufficiale verificata è un attributo interno, non autocertificabile dal manifest dell'utente.

`arcade_archives.py` confronta contenuti e grafo parent/clone/BIOS. Per 7z una WriterFactory restituisce sink di digest senza scrivere i membri sul filesystem. Nomi, dimensioni, hash, espansione, link e cifratura sono controllati. Il rapporto distingue completezza, esportabilità, corrispondenza col core e test dell'operatore; nessun archivio viene modificato.

`core_profiles.py` legge metadati core/configurazioni, BIOS e terminale EmulationStation mediante RPC costante. `retro_get_system_info` è isolato con timeout, senza inizializzare il core. Il game_guard viene chiamato prima del piano e prima del trasferimento; blocca set incompleti, rapporti scaduti e configurazioni incompatibili. Manifest e gamelist usano sistema e nome tecnico verificati. Nessuna configurazione remota viene scritta dall'intelligence.

`curated_sources.py` aggiunge due release con prove dei diritti per singolo file, riutilizzando PublicHTTP, DiscoveryEntry, planner con conferma e DownloadManager. `/downloads/report` restituisce hash, dimensioni, provenienza e licenza. I cataloghi DAT non entrano nelle selezioni di download.

`Intelligence.tsx` presenta piattaforme, Arcade, Neo Geo, raccolte, filtri, DAT, profili, varianti e rapporti. Gli elenchi caricano 36 record per pagina; i dettagli sono richiesti separatamente. La variante preferita non implica possesso o compatibilità. Le evidenze di test conservano dispositivo, nota, data e SHA-256 del gioco; gli esiti con hash diverso non entrano nei conteggi dei test riusciti.

Le scansioni locali espongono progresso e cancellazione cooperativa tra blocchi di hashing. L'importazione confermata mantiene la transazione atomica e rilegge gli originali; la scansione annullata non importa candidati parziali.

## Componenti della libreria

La SPA React/TypeScript usa API JSON sullo stesso host. FastAPI serve anche la build e i font; Vite usa un proxy locale durante lo sviluppo. Il catalogo è paginato lato server. SQLite usa WAL, timeout e transazioni SQLAlchemy; Alembic conserva la storia dello schema.

`backend/main.py` compone route, session factory e lifecycle. Scansione, importazione ed esportazione usano una coda seriale Job. Un lock di processo protegge le modifiche condivise della libreria, senza trattenere le richieste di rete. L'installazione usa un solo worker Uvicorn.

`scanner.py` enumera i file, interpreta CUE/M3U, raggruppa dischi e calcola hash a blocchi. L'identità di un file è SHA-256; per i gruppi è l'hash delle coppie ordinate percorso relativo/hash. Gruppi con nomi interni diversi possono quindi avere identità diverse. Il commit ricontrolla gli originali e salta gli hash già catalogati.

`exports.py` verifica gli originali e prepara un manifest indipendente dal trasporto. LocalTransport copia in staging, verifica le copie e pubblica con rinomina. Ogni destinazione è univoca. Playlist generate e manifest entrano nella stima dello spazio. ExportTransport descrive la pubblicazione locale; il servizio SFTP riutilizza prepare_games aggiungendo piano, conferma e coda persistente. Il manifest conserva autore, licenza e provenienza.

`providers.py` conserva ManifestProvider e l'API dell'Incremento 1. I manifest esplicitamente configurati dall'operatore vengono validati tramite Pydantic e sincronizzati anche nel nuovo catalogo Discovery.

## Discovery e acquisizione

`db.py` definisce Game, Setting, Job, DiscoveryEntry, ProviderState, DownloadPlan e DownloadTask. La migrazione 0002 aggiunge autore e tabelle di acquisizione conservando giochi e impostazioni. L'unicità SHA-256 nel database protegge l'identità della libreria.

`discovery_sources.py` implementa GBDev, GBADev e NESDev. Git Trees fornisce revisione, percorsi, dimensioni e hash dei blob; i metadati sono letti da URL immutabili e memorizzati per hash. L'acquisizione richiede una licenza riconosciuta, assenza di esclusioni commerciali/disabilitazioni e un file supportato identificato senza ambiguità. I campi mancanti restano null. Ogni voce conserva fonte, dichiarazione di licenza, revisione e riferimenti di integrità. La licenza degli asset è valutata separatamente. itch.io e PDRoms sono collegamenti documentati alle fonti.

`network.py` concentra HTTPS pubblico, robots.txt, timeout, intervallo minimo per host, limiti di risposta e divieto di redirect/proxy impliciti. `acquisition.py` gestisce refresh asincroni, filtri, ricerca paginata, impostazioni, capacità e arricchimento. Un refresh fallito conserva la cache precedente e segnala l'errore.

I piani persistenti contengono selezione e impronta delle impostazioni/fonti. La conferma esplicita è idempotente e ricontrolla disponibilità e capacità prima di creare task. Selezionare tutti i risultati filtrati opera sul server, oltre la pagina visibile. Salvare le regole automatiche non avvia download.

`download_manager.py` esegue uno scheduler e un pool con limite configurabile da 1 a 8. Stati: queued, running, paused, retry_wait, verifying, downloaded, imported, failed, cancelled. Rete fuori dal lock; progressi, controlli e importazione usano transazioni brevi. La ripresa usa Range/If-Range, oppure ricomincia se il server restituisce tutto il file. Dimensione, SHA-256 dichiarato o hash Git vengono verificati; SHA-256 viene sempre calcolato per deduplicare. I file e le prove di autorizzazione risiedono in cartelle interne UUID. Gli ZIP sono ispezionati senza estrazione prima dell'importazione.

L'arricchimento usa solo SHA-256 o hash Git verificati sul file locale, senza confronti per somiglianza del titolo. Le ambiguità vengono segnalate. La procedura completa campi vuoti e conserva le correzioni manuali. Copertine con autorizzazione esplicita vengono verificate, decodificate con limiti e ricodificate PNG nella cache.

La capacità target parte da 32 GB nominali, riserva di 8 GB e margine del 5%; 128 GB e valori personalizzati sono configurabili. Il calcolo include libreria, coda e selezione. La conferma verifica anche il disco locale. L'esportazione confronta la propria stima con la capacità utile.

Le API sono documentate con schemi in `/docs`: discovery, provider/refresh, piani/conferma, configurazione, coda/controlli, copertine e arricchimento. `frontend/src/Discovery.tsx` presenta questi flussi con dialogo accessibile, selezione multipla e polling della coda ogni 1,5 secondi.

## Sicurezza e confine di fiducia

- Binding loopback, header Host verificato, header personalizzato sulle mutazioni e controllo Origin/CORS.
- Validazione Pydantic, query parametrizzate, limiti su selezioni, paginazione e stringhe.
- Percorsi canonicalizzati, contenimento dopo risoluzione, esclusione di link simbolici e riferimenti esterni CUE/M3U.
- Copertine servite da radici autorizzate, CSP e protezione MIME sniffing.
- Download HTTPS pubblici senza credenziali, redirect o proxy ambientali; nomi generati/validati e integrità prima dell'importazione.
- ZIP controllati per traversal, link, cifratura, CRC, numero di file, dimensione espansa e rapporto di compressione.
- Manifest personalizzati come dichiarazione esplicita di fiducia dell'operatore, che verifica l'autorizzazione della fonte.

Il confine di fiducia è il computer locale. Un processo con accesso diretto ai dati può modificarli. L'esposizione LAN richiederebbe autenticazione, TLS e autorizzazioni dedicate.

## Persistenza e recupero

Le scansioni segnalano file non leggibili/incompleti. Le importazioni falliscono atomicamente se gli originali cambiano. Le esportazioni verificano gli hash prima e dopo la copia. Errori e stati vengono persistiti e registrati con rotazione dei log.

Al riavvio i Job locali queued/running diventano failed per un retry esplicito. I DownloadTask interrotti diventano paused; quelli già confermati ancora queued restano in coda. Gli errori transitori ritentano al massimo tre volte, con backoff e Retry-After. Annullare rimuove i file incompleti, mettere in pausa li conserva. Un arresto forzato durante un'esportazione può lasciare staging parziale, come documentato nel README.

## Verifica

Pytest copre API, transazioni, filtri, deduplica, multidisco, traversal, origin, migrazioni, parsing/licenze, corruzione, retry, Range, riavvio, concorrenza, budget, matching e copertine. Vitest verifica client HTTP e formattazione. Playwright attraversa i flussi dell'Incremento 1 e selezione manuale/automatica, conferma, pausa/ripresa, importazione e layout mobile.

Il server E2E usa file sintetici e trasporto HTTP di test in una directory separata. Ruff, mypy, ESLint e TypeScript completano i controlli statici. Le prove live sono documentate in PROVIDERS.md, distinguendo scansioni di metadati e download effettivi.


## Integrazione Raspberry Pi (Incremento 3)

La migrazione 0003 aggiunge Publisher al catalogo e le tabelle Device e SyncRun. Device conserva configurazione pubblica, fingerprint, ultimo stato e diagnostica. SyncRun conserva anteprima, conferma dei diritti, progressi, errori e report. Password e chiavi private non entrano in SQLite. Le migrazioni 0001/0002 restano compatibili.

`ssh_connection.py` gestisce chiave Ed25519 nel profilo locale Windows, ACL dell'utente, known_hosts dedicato e connessioni Paramiko con RejectPolicy. Il probe limita l'handshake a host key Ed25519 e rifiuta una chiave differente da quelle note. Una fingerprint nuova richiede conferma esplicita. `ssh_setup.py` apre una console OpenSSH separata per l'autenticazione interattiva, verifica proprietà e symlink di .ssh/authorized_keys, crea un backup e aggiunge la sola chiave pubblica. Il login con chiave viene verificato senza disabilitare le password.

`remote_fs.py` separa percorsi SFTP da comandi remoti. I comandi diagnostici sono costanti; parametri variabili passano come JSON base64 a un interprete Python 3 fisso. Le mutazioni SFTP controllano radici autorizzate e ogni componente contro symlink/traversal. La cartella ~/.emulationstation viene risolta nella diagnostica e il percorso canonico è ammesso solo sotto la home o /opt/retropie/configs.

`exports.prepare_games` è condiviso con l'esportazione locale: rilegge dimensioni/hash e genera le playlist senza modificare gli originali. La sincronizzazione usa cartelle stabili per hash di gioco, mantenendo una directory separata per ogni insieme BIN/CUE/M3U. `sync_engine.py` confronta gli SHA-256 via SFTP, prepara i gruppi, individua i gamelist secondo es_systems.cfg e il percorso utente effettivo, stima spazio e rileva conflitti.

Ogni gruppo nuovo viene caricato in una directory nascosta legata al run, verificato integralmente e rinominato nella destinazione finale. Un gruppo già completo e identico è saltato; uno differente o incompleto è bloccato. I parziali interrotti sono riutilizzati solo dopo confronto del prefisso; il risultato completo viene sempre verificato. L'annullamento pulisce lo staging noto di quel run, conservando i gruppi già pubblicati. Una disconnessione può lasciare parziali da recuperare al retry.

`gamelist.py` usa un parser XML senza DTD/entità e conserva elementi, attributi, commenti, cartelle e metadati sconosciuti. I campi locali gestiti aggiornano la voce corrispondente; valori mancanti non cancellano informazioni remote. Prima della pubblicazione si ricontrolla l'hash osservato nel dry-run e si verifica un backup. La sostituzione usa l'estensione OpenSSH posix-rename; non c'è un fallback non atomico. Se EmulationStation è attiva, i gamelist restano rinviati nel report.

Le cartelle stabili `rlm-<hash>` hanno una voce `<folder>` con titolo, descrizione e copertina, distinta dalla voce `<game>`: EmulationStation visualizza il nome della cartella prima di entrarvi. Il titolo proviene dal catalogo acquisito; in assenza di un valore leggibile si conservano i metadati remoti, poi si usa il nome originale del file senza deduzioni. Identificativi interni e nomi generici come track/disc non diventano titoli: si usa «Titolo da verificare». I titoli mancanti nel catalogo sono segnalati in `title_reviews` e negli avvisi del dry-run. Le cartelle personali estranee al formato gestito non vengono rinominate. Il merge è idempotente, conserva statistiche e metadati sconosciuti e non cambia alcun percorso ROM o salvataggio.

`devices.py` espone API /devices e /sync, usa i Job esistenti per la diagnostica e un worker dedicato seriale per anteprime/trasferimenti. Retry di rete limitati a tre tentativi con backoff. Errori di identità o autenticazione non comportano downgrade. Al riavvio le operazioni interrotte richiedono retry esplicito. Le modifiche di configurazione vengono rilevate prima di usare un piano precedente.

`Devices.tsx` aggiunge gestione connessioni, assistente SSH, diagnostica e pagina di sincronizzazione con selezione paginata, anteprima, conferma, copertine e report. I progressi sono aggiornati ogni 800 ms. I test browser iniettano esclusivamente nel server di test un doppio SFTP locale; il servizio normale usa Paramiko reale.

## Preparazione archivi (Incremento 7.1)

`ArchiveAnalyzer` precede l'identificazione della pipeline. Un inventario con evidenze DAT mantiene l'archivio arcade originale; i contenitori console sono preparati da `ArchiveStore` e producono elementi di installazione indipendenti. La riga contenitore ha stato `prepared`, distinto da `installed`. Genitore e figli sono pubblicati in un'unica transazione; chiavi dei percorsi e hash rendono la rianalisi idempotente.

L'apertura e la decompressione avvengono in `archive_worker`, prima limitato e poi autorizzato da un handshake. Su Windows il processo principale possiede un Job Object con limiti di memoria, CPU e numero di processi, e chiusura dei decoder alla morte del padre. La coppia launcher/interprete dell'ambiente virtuale Windows è consentita. Su Linux sono applicati limiti `resource` e terminazione alla morte del padre. I file dell'archivio non vengono mai eseguiti.

I dati passano dallo staging a `data/prepared-archives/v1-<SHA256>/files` tramite rename atomico; il manifest associa hash dell'originale e dei membri preparati. La normalizzazione di maiuscole e separatori dei CUE/M3U avviene solo nelle copie preparate. I file pubblicati sono sorgenti persistenti della libreria e non vengono eliminati dal cleanup dei temporanei. Un cache hit richiede una nuova verifica dei contenuti. Lo staging viene eliminato in caso di errore e recuperato dopo un arresto.

`POST /api/installations/items/{id}/reanalyze` accoda una nuova analisi senza upload, mantenendo consensi e stato del batch. Le varianti vengono raggruppate solo sulla base di famiglie DAT verificate: si applica la preferenza esistente oppure si propone una scelta, senza eliminare archivi o varianti originali. Non sono state necessarie nuove tabelle o migrazioni.
