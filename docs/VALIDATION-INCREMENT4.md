# Collaudo Incremento 4 — 17 novembre 2026

## Ambito e preservazione

Windows 11, Python 3.10, Node 26, repository in `C:\Projects\retropie-library-manager`, branch `main`. Applicazione locale 0.4.0 su loopback porta 8000. Prima della migrazione è stato creato un backup SQLite consistente tramite `sqlite3.backup`, sotto `.runtime` esclusa da Git.

Preservati **1 gioco**, **1 dispositivo**, **4 SyncRun**, le impostazioni e **1.191 voci Discovery** precedenti. Nessun task di download era in coda nel database principale. Dopo il refresh del nuovo provider Discovery contiene 1.193 voci. La migrazione 0004 mantiene le tabelle precedenti e recupera la sincronizzazione verificata di 2048gb solo dopo confronto degli hash.

## Dati reali, conteggi distinti

| Misura nella libreria principale | Risultato |
| --- | ---: |
| Record DAT totali | 11.655 |
| Voci gioco DAT | 11.626 |
| Famiglie parent/clone per catalogo | 5.008 |
| Cloni/varianti | 6.618 |
| Record BIOS, soltanto metadati | 29 |
| Voci Neo Geo di tipo gioco | 599 |
| Voci CPS-3 | 48 |
| File di gioco fisicamente presenti | 1 |
| Voci Discovery consultabili | 1.193 |
| Download autorizzati/idonei | 51 |
| Set arcade locali validati | 0 |
| Giochi con test riuscito riferito dall'operatore | 1 |

Le 5.008 famiglie sono distinte **all'interno di ciascuna fonte**; la stessa opera può figurare in MAME e FBNeo. Non rappresentano 5.008 opere globalmente deduplicate né file posseduti. Il file locale è **2048gb**, 32.768 byte, licenza Zlib, già acquisito nell'Incremento 2. Nessuna nuova ROM o BIOS è stata scaricata nel collaudo dell'Incremento 4. I 29 record BIOS sono metadati nel DAT.

Cataloghi reali importati:

- **MAME 0.78:** 4.727 record, revisione `07f262e5d6714fc689e0c634010137d09379b462`, SHA-256 DAT `dacf9d5739ddf386705bc703f7f70239ac61b8ab44c438f76f6658c7156da147`.
- **FBNeo installato:** 6.928 record, revisione `af50579270a610eda8ac580648d9c12acc7bb565`, SHA-256 DAT `85f9a7988545ea22de01d1d2814df5d8a19b1153ebbbb385df6fe5471c3e016e`.

I metadati CPS/Neo Geo provengono anche dai driver della stessa revisione FBNeo, collegati per nome tecnico esatto e verificati con hash Git. I DAT e la cache dei driver rimangono fuori dal repository.

## Prestazioni misurate

| Prova | Esito osservato |
| --- | --- |
| 10.000 record JSON sintetici | Prima importazione 2,641 s; 5.000 famiglie, pagina da 30 record corretta. |
| Ricerca indicizzata su 10.000 record sintetici | 6,8 ms tramite TestClient, risultato esatto. |
| Aggiornamento sintetico | File identico saltato; poi 1 record modificato, 1 nuovo e 9.999 invariati. Ciclo completo 6,19 s. |
| 3.000 file Game Gear sintetici | Scansione e seconda scansione con deduplica: 15,99 s. |
| 3.000 file, importazione effettiva SQLite | Scansione + commit + verifica dei conteggi: 21,08 s. |
| DAT reali | Prima importazione MAME 4,39 s, FBNeo 5,798 s; aggiornamento con metadati aggiuntivi 5,178 / 6,709 s. Tempi del parser/DB, esclusi download e SSH. |
| Ricerca HTTP sui cataloghi reali | Metal Slug: 34 risultati in 52 ms; CPS-3: 48 in 113 ms; Neo Geo: 599 in 118 ms; parent: 5.008 in 108 ms. |

Sono misure di questo computer, non soglie prestazionali garantite. Le fixture di 3.000 file sono piccoli contenuti sintetici, non un trasferimento remoto di migliaia di ROM. DAT reali e fixture sono stati provati anche su database già popolato.

## Raspberry reale — esclusivamente lettura

Raspberry Pi 3 B+, RetroPie 4.8, SanDisk 32 GB. Stessa identità SSH già verificata; nessun aggiornamento, installazione, copia BIOS, cambio di configurazione, riavvio di servizio o reboot durante questo incremento.

| Core | Versione letta dal binario | SHA-256 |
| --- | --- | --- |
| lr-mame2003 | `0.78 3eb27d5` | `94311d9959850707846a05e1e16b5ce9c11819a05ee90e064b087e399f8dac69` |
| lr-fbneo | `v1.0.0.03 af50579` | `37dc6340f459a5f50d30c5ab9bcf5974926de4245a5ead2d07046868ade57643` |

Rilevati 24 core già installati. Neo Geo/fba hanno default lr-fbneo; mame-libretro usa lr-mame2003. Arcade dispone dei due core ma non dichiara un default, quindi non si assume una scelta automatica. Cartelle e permessi controllati in lettura. Filesystem: 31.092.658.176 byte totali e circa 27,03 miliardi liberi al rilevamento.

Nessun BIOS Neo Geo è stato trovato nelle posizioni controllate. Non è stata eseguita una ricerca indiscriminata del filesystem o copiato contenuto BIOS. Il blocco per BIOS mancanti è verificato dalle fixture; non esistono set arcade posseduti con cui effettuare un test reale completo.

EmulationStation: PID **621**, **TTY_NR=1025**, stdin `/dev/tty1`, sessione locale valida, invariata fra i controlli. Non è stata riavviata. Il precedente problema TTY_NR=0 è documentato e corretto nel rapporto dell'Incremento 3.

**2048GB:** l'utente ha comunicato l'avvio corretto dopo reboot completo e l'uso di EasySMX USB. È stato registrato `operator_report`, con dispositivo, nota e SHA-256. L'assistente non ha eseguito un nuovo lancio e non attribuisce questo risultato a una validazione arcade.

## Test automatici e browser

La suite comprende parsing DAT/XML/CSV/JSON, entità XML, traversal, hash/dimensioni, ZIP/7z senza estrazione, parent/clone e BIOS, quattro organizzazioni dei set, revisioni core e override moderni/legacy, staging interrotto/annullato, deduplica e FTS, guardia export/sync, aggiornamento DAT, evidenze legate all'hash, licenze/cache alterate, conservazione dei dati, download e regressioni degli incrementi precedenti.

La verifica finale comprende **103 test backend** superati (73,59 s), **6 test frontend** e **5 test browser** superati (28,7 s), insieme a Ruff, mypy, ESLint, TypeScript e build Vite. Il lettore BIOS remoto è provato con contenuto sintetico, hash errato e nomi duplicati. Nessun test funzionale rimane fallito. Gli errori intermedi di implementazione e dei selettori browser sono stati corretti e i controlli interessati rieseguiti.

I test browser sintetici usano HTTP e SSH/SFTP di test isolati, porta 18001; nessun contatto con il Raspberry. Separatamente, Playwright ha controllato la build reale su porta 8000: piattaforme, ricerca Metal Slug, core/BIOS, prova 2048gb e Neo Geo a 390 px. Nessun errore JavaScript o overflow orizzontale. Screenshot e rapporti rimangono in `.runtime` esclusa da Git.

## Dipendenze e sicurezza dei file

`pip check` non rileva dipendenze incompatibili. Installazione editable 0.4.0 con il normale backend isolato riuscita. Il tentativo opzionale senza build isolation non disponeva del build hook e non è usato dallo script Setup.

`npm audit --omit=dev`: **0 vulnerabilità**. L'audit completo segnala **12 voci high** derivate da un'unica vulnerabilità transitiva di picomatch nelle dipendenze di sviluppo (Vite/Vitest/ESLint). Il 17 novembre 2026 l'[advisory GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf) indica versioni vulnerabili fino a 4.0.7 e **nessuna versione corretta**. L'aggiornamento compatibile non ha rimosso la segnalazione; non è stato eseguito audit fix --force né un downgrade arbitrario. Rimane un punto aperto della toolchain: gli strumenti di sviluppo non devono elaborare glob non fidati. L'app pubblicata serve una build statica locale.

Controllati file tracked/untracked non ignorati, estensioni ROM/BIOS/archivi, chiavi SSH, token, credenziali, binari inattesi e codifica UTF-8. Il repository contiene codice, documentazione e fixture generate dai test; nessuna ROM, BIOS, chiave, database o cache di collaudo viene pubblicata.

## Limiti espliciti

- Nessun set arcade realmente posseduto: validazioni complete e trasferimenti arcade coperti da fixture; nessun test reale di prestazioni CPS-3, Neo Geo o PS1.
- Clone merged completo ma non selezionabile automaticamente: export bloccato. Arcade CHD e software-list avanzate non sono validati dal verificatore ZIP/7z.
- BIOS richiesti conservativamente secondo il DAT; nessuna ricostruzione, riparazione o distribuzione automatica.
- Preferenze core/MVS/AES locali: nessuna modifica implicita della configurazione Raspberry.
- Famiglie distinte per fonte, senza deduplica arbitraria tra cataloghi.
- Vulnerabilità transitiva della sola toolchain di sviluppo ancora senza patch upstream.
