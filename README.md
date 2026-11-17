# RetroPie Library Manager

Applicazione locale per Windows 11 che organizza una libreria personale destinata a RetroPie su Raspberry Pi 3 Model B+. Backend Python/FastAPI, React/TypeScript/Vite, SQLite/SQLAlchemy e migrazioni Alembic. L'interfaccia e i font funzionano offline dopo l'installazione.

## Avvio su Windows

Richiede Git, Python 3.10+ e Node.js 22.12+ LTS nel PATH.

1. Clonare il repository e aprire la cartella del progetto.
2. Eseguire `Setup.cmd` per creare l'ambiente Python, installare le dipendenze bloccate e compilare il frontend.
3. Eseguire `Start.cmd` e aprire [l'app locale](http://127.0.0.1:8000).
4. In **Impostazioni**, aggiungere le cartelle delle ROM e una cartella esistente per le esportazioni.
5. In **Importazione**, scansionare una cartella, esaminare candidati e segnalazioni, indicare provenienza e licenza, confermare la selezione.

La console avviata da Start.cmd resta aperta. `Ctrl+C` arresta il server e attende la conclusione dell'operazione corrente. L'app ascolta esclusivamente sull'interfaccia loopback. Gli endpoint sono documentati in [OpenAPI locale](http://127.0.0.1:8000/docs). Per le chiamate di modifica inviare `X-RLM-Request: 1`.

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
| Game Boy | `gb` | GB |
| Game Boy Color | `gbc` | GBC |
| Game Boy Advance | `gba` | GBA |
| Neo Geo | `neogeo` | ZIP, 7Z con console indicata o cartella nominata `neogeo` |
| Arcade | `arcade` | ZIP, 7Z con console indicata o cartella nominata `arcade` |
| PlayStation | `psx` | CUE e tracce collegate, M3U, CHD, PBP, ISO |

Per gli archivi ZIP/7Z la console viene dedotta dal percorso o scelta nell'importazione. Il contenuto degli archivi resta intatto. Un BIN PS1 richiede il relativo CUE. I riferimenti CUE/M3U devono essere relativi alla cartella del descrittore, esistere e rimanere nella sorgente autorizzata. Le playlist M3U accettano dischi CUE/CHD/PBP/ISO. File con estensioni sconosciute vengono ignorati. I formati ambigui vengono segnalati.

Il riconoscimento iniziale usa estensione e nome del file. Metadati e copertine possono essere completati nel dettaglio. Il supporto dell'emulatore, la versione del romset Arcade e gli eventuali requisiti BIOS vanno verificati sulla propria installazione RetroPie. Il progetto gestisce i file e prepara l'esportazione, mentre la verifica di avvio sul Raspberry Pi appartiene agli incrementi successivi.

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
