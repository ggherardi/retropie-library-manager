# Incremento 7.1 — collaudo importazione archivi

Data: 18 novembre 2026. Versione: **0.7.1**.

## Risultato implementato

**Aggiungi giochi** accetta direttamente ZIP e 7z, anche tramite drag & drop. La pipeline prepara i file console, riconosce e raggruppa i dischi PS1, mostra una riga per gioco e continua con importazione, metadati, controllo core/BIOS e sincronizzazione verificata. Non occorre estrazione manuale o una sincronizzazione separata.

I set arcade identificati tramite DAT mantengono il formato compresso. Le famiglie di varianti vengono considerate tali soltanto quando documentate dal DAT: si riusa una preferenza configurata o si propone una decisione. Documenti, BIOS e file accessori non diventano giochi. Un membro non supportato o un archivio annidato corrotto non blocca gli altri giochi validi del contenitore.

Il nuovo endpoint di rianalisi riutilizza gli archivi dei job già presenti. Un batch autorizzato riprende automaticamente per gli elementi validi; non vengono inventati nuovi consensi. Nessuna migrazione o ricreazione del database: la nuova fase usa gli elementi e i campi JSON persistenti dell'Incremento 7.

L'apertura dei contenitori e l'estrazione avvengono in un worker isolato. Su Windows, un Job Object applica il limite complessivo di 1 GiB, il limite CPU e la terminazione dei decoder alla chiusura del processo principale. Si applicano inoltre budget di dimensione, membri, profondità e tempo; anche le estrazioni fallite consumano il budget cumulativo. Le copie preparate sono pubblicate atomicamente e verificate tramite hash prima del riuso. Gli originali restano invariati.

Guida, API e limiti: [ARCHIVES.md](ARCHIVES.md). Dettagli architetturali: [ARCHITECTURE.md](ARCHITECTURE.md).

## Test automatici

| Verifica finale | Esito |
| --- | --- |
| Backend `pytest` | **220 superati**, nessun fallimento |
| Backend Ruff e mypy | Superati |
| Frontend Vitest | **11 superati**, nessun fallimento |
| Frontend ESLint e typecheck TypeScript | Superati |
| Build frontend di produzione | Superata |
| Browser Playwright | **8 superati**, nessun fallimento |

Totale: **239 test superati**. L'incremento aggiunge 39 casi backend e un test browser al percorso già esistente.

Il nuovo modulo backend copre ZIP NES, 7z Mega Drive, ZIP Game Boy, 7z CUE/BIN, multitraccia, multidisco/M3U, arcade/Neo Geo con BIOS sintetico, cartucce multiple, varianti, archivi annidati, componenti mancanti, ECM/APE non supportati, ZIP corrotti/CRC errato, zip bomb, traversal, nomi Windows riservati, link, collisioni, limiti, retry, job già autorizzati, cleanup, cache modificata e ripresa dopo interruzione. Un test verifica che membri problematici nello stesso contenitore non fermino i giochi validi.

Il nuovo test browser trascina un vero ZIP sintetico nell'interfaccia, osserva la preparazione, conferma una sola volta e attende l'installazione verificata sul dispositivo simulato. Controlla anche il layout mobile e che il trasferimento non sia presentato come prova d'avvio. Nessuna ROM commerciale è inclusa nelle fixture.

Gli errori inizialmente emersi nel writer 7z, nel limite dei processi del launcher Python Windows e nei test sono stati corretti prima della verifica finale. È stata corretta anche una condizione di concorrenza fra riepilogo e retry: un riepilogo obsoleto poteva segnare come concluso un batch appena ripreso. Un test deterministico riproduce e verifica il coordinamento dei due aggiornamenti.

## Collaudo reale: tre tipi di archivio

Gli archivi NES e PS1 del collaudo sono stati creati localmente da copie già presenti e autorizzate. Gridlee usa l'archivio della fonte autorizzata già acquisito negli incrementi precedenti. Tutti i dati restano in directory ignorate da Git.

| Caso | Riconoscimento e preparazione | Importazione e sincronizzazione reale | Stato finale |
| --- | --- | --- | --- |
| **F-FF — ZIP NES** | Estratto automaticamente; header iNES e SHA-256 corrispondenti alla libreria. Documentazione esclusa dalla classificazione come gioco quando presente. | Riutilizzata la riga esistente, verificati core e file remoti; **0 byte trasferiti**. | Installazione verificata; nessun nuovo avvio in questo collaudo. |
| **Crash Bandicoot (USA) — ZIP PS1** | Estratti CUE e BIN, raggruppati come un solo gioco; riferimenti, settori e descrittore ISO9660 PlayStation validati; hash identici alla copia già importata. | Riutilizzata la riga esistente; core `lr-pcsx-rearmed` e BIOS verificati; **0 byte trasferiti**. | Installazione verificata. Avvio già confermato dall'utente nell'Incremento 7, non ripetuto qui. |
| **Gridlee — ZIP arcade** | Membri confrontati con il DAT pertinente e con la configurazione/core già verificati. ZIP conservato, senza estrazione in cartucce o tracce. | Riutilizzata la riga esistente; set e file remoti verificati; **0 byte trasferiti**. | Installazione verificata; nessuna nuova prova di gioco. |

Il batch reale contiene **3 giochi installati/verificati e 2 contenitori preparati**, senza errori. I tre giochi erano già sul Raspberry: il collaudo dimostra la preparazione degli archivi, la deduplica e la verifica incrementale reale, non l'aggiunta di tre titoli nuovi. La creazione di nuovi record e il trasferimento effettivo da un archivio sono verificati con le fixture sintetiche nei test backend e browser.

## Conservazione dei dati

| Misura dopo il collaudo | Esito |
| --- | --- |
| Giochi nella libreria PC | **99**, invariati |
| Giochi sul Raspberry | **99**, invariati |
| Nuovi titoli aggiunti dal collaudo | **0** |
| File remoti confrontati prima/dopo | **267**, tutti invariati per percorso, dimensione e SHA-256 |
| Salvataggi confrontati | **4**, tutti invariati, inclusi Vagrant Story e Crash |
| Gamelist XML validi e invariati | **12** |
| ROM/metadati trasferiti | **0 byte** |
| Spazio libero osservato | **25.606.090.752 byte**, circa **23,85 GiB** |
| Margine minimo di sicurezza | **4 GiB**, rispettato |
| Core, BIOS e configurazione PS1 | Hash invariati rispetto alla verifica precedente |
| Raccolta Grandi Classici | File invariato |

EmulationStation risultava già chiusa prima del collaudo e lo era anche dopo. Non è stata chiusa, avviata o riavviata dall'applicazione o via SSH. Poiché gamelist e raccolte erano già corretti, non sono stati riscritti né sono stati necessari nuovi backup XML. La gestione della coda metadati con EmulationStation aperta continua a essere coperta dalla suite precedente.

## Caso reale Tekken 3

Il job esistente **Da verificare** è stato rianalizzato tramite l'API, senza chiedere un nuovo caricamento o un'estrazione manuale. L'archivio originale è stato aperto e il membro decompresso automaticamente in una copia preparata verificata.

Risultati osservati:

- Archivio `Tekken 3 (E) (Track 1) [SCES-01237].7z`: **401.871.468 byte**.
- Contiene **un solo membro**, `Tekken 3 (E) (Track 1) [SCES-01237].bin.ecm`: **593.637.235 byte**.
- Firma del membro: **ECM**, non un BIN pronto per l'emulatore. Lo SHA-256 coincide con il file ECM già presente accanto all'archivio e con la copia caricata nell'app.
- Nella cartella autorizzata sono presenti anche due file `.ape` nominati Track 2 e Track 3, rispettivamente **18.760.908** e **1.756 byte**. I nomi non dimostrano ordine, indici o completezza del disco.
- Non è presente un **CUE/M3U** che descriva il gruppo di tracce. ECM/APE non sono convertiti da questo incremento.
- Non è stato possibile validare un'immagine PS1 completa né verificare l'eseguibilità di questa copia. Il core e il BIOS PS1 funzionanti non rendono automaticamente valido il contenuto dell'archivio.

**Tekken 3 non è stato importato come gioco né trasferito.** Il job mostra membri, file associati e una diagnosi precisa: formato ECM/APE non supportato e descrittore del disco assente. Non è più indicato soltanto come un set arcade ambiguo. Non sono stati inventati un CUE, indici audio o un'identificazione certa basata sul nome.

L'originale 7z e il membro ECM sono stati verificati contro le copie locali autorizzate dopo l'operazione; nessuna modifica. La rianalisi è stata ripetuta dopo il riavvio del backend aggiornato: la cache verificata produce la stessa diagnosi e lo staging temporaneo risulta vuoto. Non sono stati scaricati ROM o BIOS.

## Limiti residui

- ZIP/7z supportati entro i limiti documentati; archivi cifrati e altri contenitori non supportati producono un errore esplicito.
- ECM/APE e ricostruzione di CUE mancanti non sono implementati. Per Tekken serve una copia completa in un formato supportato, ottenuta legittimamente; può essere fornita ancora compressa.
- CHD rimane subordinato a `chdman`, identità verificabile e supporto del dispositivo. Non sono stati collaudati CHD reali in questo incremento.
- Le varianti non vengono dedotte da nomi simili: senza una famiglia affidabile i file restano elementi distinti da verificare.
- Le copie preparate sono sorgenti persistenti, non file temporanei da eliminare dopo l'importazione. Il cleanup riguarda lo staging, senza cancellare ROM della libreria.
- Nessun nuovo gioco è stato avviato durante il collaudo 7.1. Le precedenti conferme di Crash e Vagrant Story restano associate ai loro hash e al dispositivo.

Il database è stato salvato prima dell'aggiornamento. Inventari, manifest, log e rapporti delle API sono conservati localmente nella directory runtime ignorata da Git. Il repository contiene solo codice, test sintetici e documentazione.
