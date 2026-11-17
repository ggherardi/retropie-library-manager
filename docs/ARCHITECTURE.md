# Architettura

## Componenti

La SPA React utilizza API JSON sullo stesso host. La build viene servita da FastAPI e include i font. Lo sviluppo Vite usa un proxy locale. Il client presenta stati di attesa, risultati ed errori, con polling dei lavori persistenti. Il catalogo usa paginazione lato server per mantenere limitato il numero di elementi renderizzati.

`backend/main.py` compone le route, la session factory, il ciclo di vita e la coda seriale dei lavori. `db.py` definisce Game, Setting e Job tramite SQLAlchemy 2. Alembic conserva la storia dello schema. SQLite usa WAL, timeout e transazioni. L'unicità dell'hash a livello di database protegge l'identità dei giochi. Le modifiche passano attraverso un lock di processo. L'installazione prevista usa un solo worker Uvicorn.

`scanner.py` enumera i percorsi, interpreta CUE/M3U, raggruppa i dischi e calcola gli hash a blocchi. Il candidato contiene tutti i file necessari con percorso assoluto, relativo, dimensione e SHA-256. L'identità dei file singoli è il loro hash. Per i gruppi è l'hash della lista ordinata di coppie percorso relativo/hash. Due gruppi con nomi interni differenti possono avere identità diverse anche a contenuti equivalenti. L'anteprima è un risultato Job persistente. Il commit ricontrolla ogni file selezionato in una transazione e salta gli hash già catalogati.

`exports.py` verifica gli originali e costruisce un manifest indipendente dal trasporto. `LocalTransport` calcola lo spazio, esegue la copia in staging, verifica gli hash delle copie e pubblica con una rinomina. Ogni esecuzione ha una destinazione univoca. Le playlist multidisco generate sono incluse nel calcolo dello spazio e nel manifest. `ExportTransport` descrive l'interfaccia prevista per un futuro trasporto SFTP.

`providers.py` definisce il protocollo Provider e ManifestProvider. Le voci vengono validate tramite Pydantic, salvate nelle impostazioni SQLite e mostrate nell'interfaccia. Il downloader usa file parziali univoci, dimensione limite, hash richiesto e rinomina finale. Il download verificato viene importato automaticamente. I retry riutilizzano un download presente soltanto dopo averne verificato nuovamente dimensione e hash.

## Sicurezza locale

- Binding loopback e verifica dell'header Host.
- Header personalizzato obbligatorio sulle mutazioni, verifica Origin e CORS limitato alle porte locali di sviluppo.
- Validazione Pydantic, limiti su stringhe, selezioni e paginazione, query SQLAlchemy parametrizzate.
- Sorgenti configurate esplicitamente, percorsi assoluti canonicalizzati, controllo dei riferimenti interni, esclusione dei link simbolici durante l'enumerazione e verifica del contenimento dopo la risoluzione.
- Copertine locali limitate a PNG/JPG/WebP, servite dal backend. CSP e protezione dal MIME sniffing sulle risposte.
- Download HTTPS su indirizzi pubblici, senza credenziali, redirect o proxy impliciti. File destinazione generati dal server e hash/dimensione verificati prima dell'importazione.
- Il manifest dei provider è una dichiarazione di fiducia configurata dall'operatore. L'autorizzazione legale del distributore deve essere accertata dall'operatore.

Il confine di fiducia è il computer locale. Un processo locale con accesso diretto al database o ai file può modificarli. Il servizio è progettato per uso personale con un singolo processo. Un'esposizione LAN richiederebbe autenticazione, TLS e un modello di autorizzazione dedicato.

## Errori, persistenza e recupero

Le scansioni tollerano file non leggibili o descrittori incompleti e producono segnalazioni nell'anteprima. Le importazioni falliscono atomicamente quando un originale cambia tra scansione e commit. Le esportazioni ricontrollano gli hash prima e dopo la copia. I fallimenti dei lavori vengono salvati e registrati in log con rotazione. Al riavvio i lavori queued/running diventano failed per consentire un retry esplicito. Una terminazione forzata durante una copia può lasciare staging parziale, come documentato nel README.

## Verifica

Pytest copre API, transazioni, deduplica, filtri e paginazione, multidisco e playlist, traversal, controllo degli origin, download e migrazioni. Vitest verifica il contratto del client HTTP e la propagazione degli errori. Playwright attraversa impostazioni, scansione, importazione, modifica, preferiti, viste, dry-run ed esportazione tramite il browser e verifica il layout mobile. Ruff, mypy, ESLint e TypeScript completano i controlli statici.
