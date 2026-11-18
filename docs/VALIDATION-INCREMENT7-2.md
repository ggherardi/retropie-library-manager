# Incremento 7.2 — ZIP, RAR e 7z

Data: 18 novembre 2026. Versione applicazione: **0.7.2**.

## Risultato

**Aggiungi giochi** accetta ZIP, RAR4/RAR5 e 7z e continua nella pipeline predefinita di installazione sul Raspberry: preparazione sicura, identificazione, importazione, metadati disponibili, preflight, dry-run, trasferimento incrementale, SHA-256 e metadati EmulationStation. Non richiede estrazione o rinomina manuale dei membri. I job precedenti si rianalizzano senza un nuovo caricamento.

Sono gestiti cartelle interne, più giochi, BIN/CUE multitraccia e multidisco, annidamento e famiglie di volumi RAR partN/rar+r00, ZIP z01+zip, ZIP/7z .001. Originali, percorsi della libreria e salvataggi restano preservati. I set arcade RAR/7z sono preparati in ZIP soltanto dopo un DAT completo e vengono rivalidati; i set già presenti conservano lo ZIP e i percorsi esistenti anche cambiando compressione. La corrispondenza DAT/versione del core rimane obbligatoria per la sincronizzazione.

La vecchia installazione locale di 7-Zip 16.04 è stata aggiornata tramite il pacchetto ufficiale WinGet a **26.06**, con verifica dell'hash dell'installer da parte di WinGet. Il repository non distribuisce il motore. Disponibilità, versione, condizioni di licenza, installazione Windows e limiti sono descritti in [ARCHIVES.md](ARCHIVES.md).

## Test eseguiti

| Verifica | Esito finale |
| --- | --- |
| Backend pytest completo | **258 superati**, nessun fallimento |
| Regressioni aggiuntive sui nomi CLI (`@` e `-`) | **2 superate** |
| Ruff backend/test/migrazioni | Superato |
| mypy backend | Superato, 46 moduli |
| Frontend Vitest | **11 superati** |
| ESLint e typecheck TypeScript | Superati |
| Build di produzione | Superata |
| Browser Playwright completo | **9 superati** |
| Parsing dello script PowerShell di setup | Superato |

Totale: **280 test superati** (260 casi backend, 11 frontend, 9 browser). Aggiunti 41 casi backend e un caso browser RAR; rimosso il caso ormai obsoleto che classificava ogni RAR come formato non supportato.

RAR4 e RAR5 vengono **realmente decodificati da 7-Zip**, non simulati. I test includono contenitori stored sintetici con cartucce e PS1, fixture testuali compresse/solid e volumi RAR di entrambe le generazioni, nomi legacy, ZIP e 7z suddivisi, ZIP con dischi, password, CRC errato, traversal, dati modificati in un volume, assenza del motore, più giochi, BIOS sintetici, conversione arcade verificata, deduplica tra formati, ripresa dei job e installazione incrementale. La suite precedente conserva i controlli su risorse, decompression bomb, interruzioni, cleanup, crash recovery e sicurezza della sincronizzazione.

Le fixture RAR compresse provengono da [rarfile](https://github.com/markokr/rarfile), revisione `d2f7df6fc843dae356fd6b0a85971dc36fd6e757`, con licenza ISC, origine e hash conservati nel file JSON dei test. Contengono testo di prova, nessuna ROM o BIOS. Il browser trascina un vero RAR sintetico, osserva la preparazione e completa l'installazione verificata sul dispositivo simulato. I trasferimenti di giochi nuovi sono verificati nei test backend/browser; il collaudo fisico seguente riguarda copie già installate.

## Collaudo reale

| Archivio | Riconoscimento/preparazione | Esito sul Raspberry |
| --- | --- | --- |
| F-FF ZIP | Header NES, hash identico alla libreria, estrazione automatica | Record esistente riutilizzato, installazione verificata, **0 byte** |
| F-FF RAR4 | Contenitore stored costruito dalla copia homebrew autorizzata; decoder 7-Zip reale, hash e header verificati | Stesso gioco riutilizzato, **0 byte** |
| F-FF RAR5 | Contenitore stored costruito dalla stessa copia autorizzata; decoder 7-Zip reale | Stesso gioco riutilizzato, **0 byte** |
| F-FF 7z | Preparazione automatica e SHA-256 identico alla ROM originale | Stesso gioco riutilizzato, **0 byte** |
| Crash Bandicoot (USA) ZIP | CUE/BIN validati e raggruppati; core lr-pcsx-rearmed e BIOS esistente verificati | Record e percorsi esistenti riutilizzati, **0 byte** |
| Gridlee 7z | Hash dei membri e DAT attivo; riconosciuto lo stesso set già catalogato | ZIP esistente riutilizzato; controlli DAT/core e file remoti superati, **0 byte** |

Il batch comprende **6 elementi installati/verificati e 5 contenitori preparati**, senza errori. Corrispondono a **3 giochi distinti**, tutti già presenti. Non sono stati aggiunti sei giochi e non sono stati effettuati nuovi avvii. La scelta di riutilizzare i file già presenti evita riscritture e conserva i percorsi dei salvataggi. Le conversioni effettive di nuovi set RAR/7z in ZIP sono state verificate con i test sintetici e con BIOS sintetici, prima e dopo la disponibilità della dipendenza richiesta.

## Conservazione e verifiche finali

| Misura | Risultato |
| --- | --- |
| Giochi sul PC | **99**, invariati |
| Giochi sul Raspberry | **99**, invariati |
| Nuovi giochi aggiunti dal collaudo | **0** |
| Byte trasferiti | **0** |
| File remoti confrontati | **267**, stessi percorsi, dimensioni e SHA-256 |
| Salvataggi confrontati | **4**, invariati, inclusi Crash e Vagrant Story |
| Gamelist validi | **12**, hash invariati |
| Spazio libero finale osservato | **25.606.057.984 byte**, circa **23,85 GiB** |
| Riserva minima sul Raspberry | **4 GiB**, rispettata in ogni piano |
| Core PS1, BIOS, configurazione e Grandi Classici | Hash invariati |
| Archivi sorgenti e staging | Originali verificati; staging vuoto |
| Nuove prove di avvio | **0** |

EmulationStation risultava già chiusa prima e dopo l'operazione. Non è stata chiusa, avviata o riavviata via SSH. Il Raspberry non è stato riavviato. I gamelist erano già corretti e non sono stati riscritti, quindi non sono serviti nuovi backup XML. Il database locale è stato salvato prima dell'aggiornamento. Nessun download di ROM o BIOS.

## Tekken 3: diagnosi reale confermata

Sono stati rianalizzati entrambi i job esistenti, senza ricaricare i file:

- Il RAR `Tekken 3 (E) [SCES-01237].rar` contiene una cartella con il 7z della prima traccia e due file APE. Il RAR è stato aperto, verificato e preparato automaticamente, compreso il 7z annidato.
- Il 7z `Tekken 3 (E) (Track 1) [SCES-01237].7z` contiene **un solo `.bin.ecm`**, non un BIN direttamente utilizzabile. Firma ECM `45434d00` rilevata sul contenuto decompresso.
- Nessuno dei due contenitori fornisce il **CUE/M3U** necessario a descrivere il disco. Il nome Tekken non viene usato come prova di un'immagine PS1 completa.
- Il RAR mostra ora un'unica diagnosi del contenitore: **ECM/APE non convertibili automaticamente e descrittore assente**. Le tracce audio non diventano giochi separati.

**Tekken non è stato importato o trasferito e non viene dichiarato installabile.** Il supporto ai contenitori RAR/7z non aggiunge una conversione ECM/APE né inventa ordine e indici delle tracce. L'azione necessaria è fornire una copia completa e legittima in BIN/CUE, ISO o CHD supportato; può rimanere compressa.

SHA-256 del RAR originale e della copia nell'inbox: `5a265c562e6ffa1bda3e604d42e37bc81916df5c7e36cf4d13de3991ba8b32ea`.
SHA-256 del 7z conservato nell'inbox: `80da6669a3b9de96247ad1e3bbd8e6525b8dd05ba2a652e17d780e6cb1fe7a18`.

## Limiti dichiarati

Archivi cifrati, autoestraenti, convenzioni di volume non documentate, metodi non riconosciuti dal motore e risorse oltre i limiti vengono bloccati con diagnosi. Non sono ricostruite parti mancanti. CHD continua a richiedere chdman e le verifiche del dispositivo; nessun CHD reale è stato collaudato in questo incremento. Non è stata ripetuta la prova di avvio di Crash o Vagrant Story: le precedenti conferme dell'utente restano separate dal nuovo collaudo dei contenitori.

Manifest, inventari, risultati API e log dei test restano in `.runtime/increment7-2`, ignorata da Git. Gli archivi di prova con giochi restano in `data`, anch'essa ignorata. Il repository contiene codice, documentazione e sole fixture sintetiche/testuali autorizzate.
