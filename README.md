# RetroPie Library Manager

Applicazione locale per Windows 11 che organizza una libreria personale destinata a RetroPie su Raspberry Pi 3 Model B+. Backend Python/FastAPI, React/TypeScript/Vite, SQLite/SQLAlchemy e migrazioni Alembic. L'interfaccia e i font funzionano offline dopo l'installazione.

## Avvio su Windows

Richiede Git, Python 3.10+ e Node.js 22.12+ LTS nel PATH.

1. Clonare il repository e aprire la cartella del progetto.
2. Eseguire `Setup.cmd` per creare l'ambiente Python, installare le dipendenze bloccate e compilare il frontend.
3. Eseguire `Start.cmd` e aprire [l'app locale](http://127.0.0.1:8000).
4. Aprire **Aggiungi giochi**, selezionare file o cartelle e controllare l'anteprima. Il Raspberry si configura in **Avanzate → Dispositivi**.
5. Confermare **Installa automaticamente**: importazione, metadati, dry-run, trasferimento e verifica proseguono nella stessa coda. È disponibile anche la modalità **solo PC**. Per leggere direttamente cartelle grandi senza upload, aggiungerle in **Avanzate → Impostazioni**.

La console avviata da Start.cmd resta aperta. `Ctrl+C` arresta il server e attende la conclusione dell'operazione corrente. L'app ascolta esclusivamente sull'interfaccia loopback. Gli endpoint sono documentati in [OpenAPI locale](http://127.0.0.1:8000/docs). Per le chiamate di modifica inviare `X-RLM-Request: 1`.

## Incremento 7.3 — Installazioni chiare e compatte

**Aggiungi giochi** mostra schede espandibili, sezioni **In corso**, **Serve intervento**, **Completati**, **Tutti** e una barra persistente con dati reali. Il backend distingue file verificati, aggiornamenti sulla console, problemi risolvibili ed errori strutturali. Copie uniche e operazioni ripetute sono conteggiate separatamente; le percentuali non vengono inventate per fasi non misurabili. La cronologia e tutti i dettagli tecnici restano consultabili.

Un gioco installato non richiede una prova d’avvio per essere completato. Per titoli o immagini errati, espandere la scheda, aprire la libreria e usare l’aggiornamento metadati verificato. EmulationStation si chiude e riapre solo dalla console locale.

[Guida agli stati e alle azioni](docs/INSTALLATION-EXPERIENCE.md) · [Collaudo 7.3](docs/VALIDATION-INCREMENT7-3.md).

## Incremento 7.2 — ZIP, RAR e 7z

**Aggiungi giochi** prepara e installa automaticamente ZIP, RAR4/RAR5 e 7z, anche annidati o suddivisi nei volumi supportati. Selezionare tutti i volumi insieme: non occorre estrarli o rinominarli. `Setup.cmd` gestisce il motore 7-Zip richiesto per RAR. I set arcade RAR/7z vengono preparati in ZIP soltanto dopo la verifica DAT; i giochi già catalogati mantengono i percorsi esistenti.

I job precedenti possono essere rianalizzati senza ricaricare i file. Archivi cifrati, volumi mancanti, corruzione e formati non convertibili hanno diagnosi esplicite. Aprire un RAR o 7z non rende automaticamente installabile un disco ECM/APE privo di CUE.

[Formati, motore, limiti e volumi](docs/ARCHIVES.md) · [Collaudo 7.2](docs/VALIDATION-INCREMENT7-2.md).

## Incremento 7.1 — Archivi ZIP e 7z senza estrazione manuale

Trascinare direttamente ZIP o 7z in **Aggiungi giochi**. L'app prepara i giochi console, raggruppa BIN/CUE e multidisco, analizza archivi annidati e conserva gli ZIP arcade identificati tramite DAT. Documenti e BIOS non diventano giochi; gli originali rimangono intatti. **Rianalizza** aggiorna i job già caricati e la pipeline autorizzata riprende automaticamente.

Il decoder è isolato con limiti di risorse; le sorgenti preparate e i relativi hash persistono per ripresa e deduplica. Un archivio incompleto o un formato non supportato mostra il motivo e i componenti coinvolti, senza chiedere estrazioni manuali. ECM/APE non sono convertiti: serve una copia completa in un formato supportato e il CUE originale quando necessario.

Guida e limiti: [importazione archivi](docs/ARCHIVES.md). Evidenze reali, incluso il caso Tekken 3: [collaudo Incremento 7.1](docs/VALIDATION-INCREMENT7-1.md).

## Incremento 7 — Aggiungi giochi e installazioni automatiche

Un unico flusso persistente collega selezione browser o sorgenti locali, riconoscimento del contenuto, DAT, importazione idempotente, metadati/media e sincronizzazione incrementale verificata. Ambiguità e BIOS sono separati dai giochi pronti; dischi PS1 restano gruppi completi. Pausa, ripresa, retry, errori per elemento e recupero dopo riavvio sono disponibili in **Installazioni**.

Con EmulationStation aperta le ROM possono essere trasferite e i metadati rimangono in coda. L'app li applica automaticamente quando l'utente la chiude dalla console locale; non la riavvia via SSH. File installati, visibilità e avvio verificato sono stati distinti. Le funzioni precedenti sono conservate nella sezione **Avanzate**.

Leggere la [guida all'installazione unificata](docs/INSTALLATIONS.md) e il [rapporto del collaudo reale](docs/VALIDATION-INCREMENT7.md), inclusi limiti CHD, DAT e BIOS.

## Incremento 6 — Grandi Classici, raccolte e media

**Grandi Classici**, **Collezione Completa**, **Da Recuperare** e **Qualità e media** separano copie possedute, selezione personale e catalogo di 914 classici. Il catalogo contiene solo metadati e riferimenti verificabili: nessuna ROM commerciale, classifica o licenza presunta.

- Riconoscimento conservativo tramite hash e DAT, associazioni manuali, preferiti, ordine e filtri per presenza, compatibilità, sincronizzazione e test riferiti dall'operatore.
- Copertine e screenshot distinti, fonti autorizzate, anteprima massiva, cache verificata e correzioni locali con cronologia; placeholder e dati sconosciuti espliciti.
- Raccolta personalizzata EmulationStation nel formato effettivamente supportato, dry-run, backup e verifica SHA-256. Restano invariati ROM, salvataggi e percorsi; sono preservati i titoli leggibili dell'Incremento 5.1.
- Dashboard di completezza e revisione dei metadati. Nessuna compatibilità o prova di gioco viene dedotta dal semplice trasferimento.

Aprire **Grandi Classici → Riconosci classici** dopo un'importazione, oppure usare le correzioni nel dettaglio. Per le immagini: **Qualità e media → Trova media autorizzati**. Prima di sincronizzare le raccolte, chiudere EmulationStation dalla console locale; l'app non la riavvia da SSH.

Guide: [raccolte, media e televisore 16:9](docs/COLLECTIONS.md), [collaudo reale](docs/VALIDATION-INCREMENT6.md), [architettura](docs/ARCHITECTURE.md).

## Incremento 4 — Cataloghi massivi e Arcade Intelligence

**Piattaforme**, **Arcade**, **Neo Geo**, **Cataloghi DAT** e **Raccolte** distinguono metadati, famiglie parent/clone, file presenti, download autorizzati, set verificati e test di gioco riferiti dall'operatore. Il collaudo include oltre 10.000 record reali e 3.000 file sintetici; i numeri effettivi e i limiti sono nel [rapporto di verifica](docs/VALIDATION-INCREMENT4.md).

- Importazione DAT ClrMamePro, XML MAME, JSON e CSV in streaming, aggiornamenti per ID, deduplica, staging atomico, attività annullabili e ricerca SQLite FTS5 paginata.
- Acquisizione **solo metadati** dei DAT ufficiali MAME 0.78 e FBNeo della revisione installata; classificazione CPS-1/2/3 e Neo Geo dai driver originali, senza confronti approssimativi dei titoli.
- Verifica ZIP/7z per nome, dimensione e hash dei componenti; parent, clone, BIOS, dipendenze e organizzazioni split/merged/non-merged/full-non-merged. Gli archivi restano intatti.
- Rilevamento in lettura di versione/hash core, configurazioni per sistema/gioco, BIOS e sessione locale EmulationStation. Un DAT recente non sostituisce automaticamente quello del core installato.
- Dry-run/export bloccati per set incompleti o non validati. Prima di sincronizzare: corrispondenza DAT/core, configurazione effettiva, hash delle dipendenze e BIOS richiesti.
- Raccolte, variante preferita, arricchimento massivo con anteprima, screenshot locali autorizzati ed evidenze di test legate all'hash del file.
- Nuovo provider con **due singoli homebrew verificati** per SNES e Mega Drive. Download multipli con conferma, filtri, budget, ripresa e report JSON riutilizzano il Download Manager.
- Scansioni locali con avanzamento e annullamento; preservazione della libreria e della cronologia di sincronizzazione degli incrementi precedenti.

Per iniziare: **Cataloghi DAT → Importa DAT MAME 0.78**, oppure selezionare il Raspberry e **Importa DAT FBNeo installato**. Poi importare i propri archivi, selezionarli in **File e raccolte**, scegliere DAT e organizzazione del set, validare e preparare la sincronizzazione. La consultazione del catalogo non concede diritti sulle ROM. Nessun BIOS proprietario viene scaricato o copiato automaticamente.

Guide: [catalogazione massiva](docs/CATALOGS.md), [Arcade/Neo Geo e compatibilità](docs/ARCADE.md), [fonti](docs/PROVIDERS.md), [architettura](docs/ARCHITECTURE.md), [collaudo](docs/VALIDATION-INCREMENT4.md).

## Incremento 3 — Raspberry Pi e sincronizzazione

In **Dispositivi**, registra hostname/IP, porta, utente e directory RetroPie. Verifica la fingerprint SSH, apri l'assistente Ed25519 e inserisci la password soltanto nel terminale OpenSSH di Windows. Il test successivo verifica accesso con chiave, SFTP, hardware, versioni disponibili, temperatura, RAM, permessi e spazio reale.

Seleziona giochi dal Catalogo oppure dalla pagina **Sincronizzazione**, scegli il Raspberry e prepara il dry-run. L'anteprima mostra file nuovi, identici e differenti, copertine e gamelist, spazio richiesto e margine libero minimo. Conferma i diritti sui contenuti e avvia. I file differenti sono bloccati; i giochi completi vengono pubblicati atomicamente dopo SHA-256. Sono disponibili avanzamento, annullamento, retry e report persistenti.

Il margine iniziale è 1 GB sullo spazio effettivo del Raspberry. La capacità nominale 32/128 GB dell'Incremento 2 resta una stima per esportazioni; la sincronizzazione legge il filesystem remoto. I BIOS non vengono trasferiti.

EmulationStation attiva comporta il rinvio della scrittura dei gamelist. L'app non interrompe o riavvia il frontend: dopo averlo chiuso, ripetere il dry-run completa soltanto i metadati mancanti. I file esistenti vengono uniti conservando campi non gestiti e creando un backup verificato. Le versioni CHD richiedono conferma della compatibilità del core PS1 oltre al controllo delle estensioni configurate.

Guide: [SSH](docs/SSH.md), [sincronizzazione](docs/SYNC.md), [diagnostica](docs/RASPBERRY.md), [risoluzione problemi](docs/TROUBLESHOOTING.md), [collaudo](docs/VALIDATION-INCREMENT3.md).

## Incremento 2 — Game Discovery e acquisizione

Aprire **Game Discovery** e aggiornare GBDev, GBADev o NESDev dal pannello provider. I cataloghi sono disponibili offline dopo l'aggiornamento. Il primo aggiornamento legge solo metadati e può richiedere alcuni minuti. Selezionare giochi o tutti i risultati filtrati, preparare il riepilogo e confermare l'acquisizione. **Download Manager** mostra avanzamento, pausa, ripresa, retry e importazione finale.

La modalità manuale è predefinita. La modalità automatica applica piattaforme, fonti, licenze, budget e deduplica configurati, quindi presenta un riepilogo da confermare. Ogni esecuzione richiede conferma. La coda già autorizzata viene conservata tra i riavvii. Un trasferimento interrotto durante il riavvio viene messo in pausa.

La configurazione parte da 32 GB nominali, 8 GB riservati al sistema e 5% di margine filesystem. Capacità, riserva, margine e concorrenza sono modificabili, anche per una microSD da 128 GB. La capacità nominale viene inserita in GB decimali; i byte effettivi sono mostrati in KiB/MiB/GiB. Il riepilogo confronta la selezione con capacità utile, libreria, coda e spazio libero locale.

L'arricchimento massivo confronta SHA-256 o l'identificatore Git del contenuto dei file singoli. Presenta corrispondenze certe e ambiguità, quindi completa i campi vuoti e le copertine autorizzate. Titoli, metadati e copertine possono essere corretti nel dettaglio del catalogo.

Consultare la [guida ai provider](docs/PROVIDERS.md), la [guida ai download](docs/DOWNLOADS.md) e le [istruzioni Windows](docs/WINDOWS.md).

## Funzionalità della libreria

- Dashboard con conteggi, spazio, console e attività recenti.
- Catalogo paginato a griglia e lista, ricerca, filtri console/regione/genere e preferiti.
- Dettaglio modificabile con titolo, regione, anno, genere, descrizione, copertina locale, provenienza e licenza. Dimensione, formato, percorso e SHA-256 derivano dalla scansione.
- Scansione ricorsiva in background, anteprime persistenti, selezione dei candidati e duplicati identificati tramite SHA-256. Le copie identiche vengono saltate anche nelle importazioni ripetute.
- PS1 BIN/CUE, più tracce, playlist M3U e raggruppamento di dischi con nomi `(Disc 1)`, `(Disk 2)` o `(CD 3)` e corrispondenti varianti tra parentesi quadre. L'esportazione genera un M3U per i gruppi riconosciuti automaticamente.
- Provider modulari con manifest JSON locale, download HTTPS esplicitamente autorizzati, verifica di dimensione e SHA-256, importazione del risultato nel catalogo.
- Selezione di giochi nel catalogo, calcolo dello spazio, dry-run ed esportazione verificata in cartelle RetroPie, con manifest JSON. Esportazione locale e sincronizzazione SFTP condividono la preparazione del manifest verificato.

## Console e formati

| Console | Cartella RetroPie | Formati riconosciuti |
| --- | --- | --- |
| NES / Famicom | `nes` | NES, FDS |
| SNES | `snes` | SFC, SMC |
| Master System | `mastersystem` | SMS |
| Mega Drive / Genesis | `megadrive` | MD, GEN, SMD, BIN con console indicata |
| SG-1000 | `sg-1000` | SG |
| PC Engine / TurboGrafx-16 | `pcengine` | PCE |
| Atari 2600 / 7800 | `atari2600`, `atari7800` | A26, A78 |
| Game Gear | `gamegear` | GG |
| Neo Geo Pocket / Color | `ngp`, `ngpc` | NGP, NGC |
| Game Boy | `gb` | GB |
| Game Boy Color | `gbc` | GBC |
| Game Boy Advance | `gba` | GBA |
| Neo Geo | `neogeo` | ZIP, 7Z con console indicata o cartella nominata `neogeo` |
| Arcade | `arcade` | ZIP, 7Z con console indicata o cartella nominata `arcade` |
| MAME 2003 / FinalBurn Neo | `mame-libretro`, `fba` | ZIP (MAME 0.78), ZIP/7Z (FBNeo) |
| PlayStation | `psx` | CUE e tracce collegate, M3U, CHD, PBP, ISO |

Per gli archivi ZIP/7Z la console viene dedotta dal percorso o scelta nell'importazione. Il contenuto degli archivi resta intatto. Un BIN PS1 richiede il relativo CUE. I riferimenti CUE/M3U devono essere relativi alla cartella del descrittore, esistere e rimanere nella sorgente autorizzata. Le playlist M3U accettano dischi CUE/CHD/PBP/ISO. File con estensioni sconosciute vengono ignorati. I formati ambigui vengono segnalati.

Il riconoscimento iniziale usa estensione e nome del file; la verifica arcade successiva usa il DAT e gli hash interni. Metadati e copertine possono essere completati nel dettaglio. I test di avvio restano distinti dalla validazione: registrare dispositivo ed evidenze dopo una prova reale. CPS-3 e PS1 richiedono attenzione alle prestazioni del Raspberry Pi 3 B+; nessun emulatore viene installato automaticamente.

## Esportazione

Selezionare i giochi nel catalogo e aprire **Esportazione**. Il dry-run rilegge e verifica i file, calcola i byte necessari compreso il manifest e confronta lo spazio libero. L'esportazione crea una cartella univoca `retropie-<uuid>` con sottocartelle `<console>/game-<id>` e mantiene i percorsi relativi dei file collegati. Il manifest riporta percorsi, hash, dimensioni, titoli, licenze e file di avvio.

La copia avviene in una cartella `.partial-<uuid>`, con verifica SHA-256 delle destinazioni, seguita da rinomina finale. Un errore gestito elimina la cartella parziale. Dopo un'interruzione forzata del processo può restare una cartella `.partial-*`, eliminabile dall'utente dopo aver verificato che il server sia fermo. Le operazioni interrotte risultano fallite al riavvio e possono essere ripetute. Le cartelle finali esistenti restano disponibili.

## Sorgenti e download

Tre provider inclusi leggono i metadati pubblici dei database GBDev, GBADev e NESDev. Il primo aggiornamento viene avviato dall’interfaccia. Il provider a manifest dell’Incremento 1 rimane disponibile per fonti configurate dall’utente. Per aggiungere una fonte usare **Sorgenti e download** e incollare un documento JSON conforme al seguente schema descrittivo.

```json
{
  "id": "autore",
  "name": "Catalogo ufficiale dell'autore",
  "entries": [{
    "id": "titolo",
    "title": "Titolo homebrew",
    "platform": "nes",
    "url": "https://dominio-autore.example/titolo.nes",
    "filename": "titolo.nes",
    "sha256": "HASH_SHA256_REALE_DI_64_CARATTERI_ESADDECIMALI",
    "size": 12345,
    "license": "Licenza dichiarata dall'autore",
    "rights_url": "https://dominio-autore.example/licenza",
    "distribution": "homebrew",
    "redistribution_allowed": true
  }]
}
```

Sostituire i dati descrittivi con quelli verificati presso l'autore. `distribution` ammette `homebrew`, `freeware` e `public-domain`. Il manifest costituisce la dichiarazione dell'operatore sull'autorizzazione della fonte. L'app valida struttura, destinazione pubblica HTTPS, formato, dimensione e integrità. L'indicazione freeware da sola richiede comunque la verifica dei diritti di redistribuzione. Sono accettati URL diretti che rispondono HTTP 200, senza redirect, autenticazione o proxy ambientali. I download supportano file singoli riconosciuti e ZIP Arcade/Neo Geo, fino a 4 GiB ciascuno.

Il repository contiene esclusivamente codice, documentazione e test con dati sintetici. ROM, BIOS e credenziali devono rimanere esterni al controllo versione.

## Dati e manutenzione

`data/` contiene SQLite, log con rotazione e download verificati. `RLM_DATA_DIR` permette di scegliere un'altra cartella dati. Arrestare l'app prima di copiare il database per un backup completo. Le ROM importate e le copertine rimangono nei percorsi originali e vanno incluse separatamente nel proprio backup. I percorsi dei file sono locali e vanno aggiornati con una nuova importazione se la libreria viene spostata.

Le migrazioni si applicano all'avvio. Per applicarle manualmente dalla radice del progetto usare `.venv\Scripts\python.exe -m alembic upgrade head`. Avviare una sola istanza del server sul database. Scansioni e importazioni usano un worker dedicato. La coda di acquisizione usa da 1 a 8 trasferimenti concorrenti, con transazioni e un lock sulle modifiche condivise.

## Verifiche e sviluppo

`Check.cmd` esegue Ruff, mypy, pytest, ESLint, TypeScript, Vitest, build e Playwright. Prima della prima prova browser installare Chromium con `cd frontend` e `npx playwright install chromium`. I test usano esclusivamente file sintetici temporanei. Le prove E2E usano un database separato in `.runtime/e2e-data`, la porta 18001 e un trasporto HTTPS sintetico definito esclusivamente in `tests/e2e_app.py`. L’app avviata con Start.cmd usa il trasporto di rete reale.

Per lo sviluppo avviare il backend con `.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`. In una seconda console, nella cartella `frontend`, eseguire `npm run dev`. Vite inoltra le chiamate API al backend.

Consultare [architettura](docs/ARCHITECTURE.md) e [roadmap](ROADMAP.md).
