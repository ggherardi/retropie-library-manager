# Archivi ZIP e 7z — Incremento 7.1

## Aggiungere giochi

1. Trascinare ZIP/7z in **Aggiungi giochi**, oppure usare il selettore file/cartelle. È possibile leggere direttamente le cartelle autorizzate del PC.
2. Controllare l'anteprima: ogni gioco riconosciuto ha una propria riga. Un contenitore preparato non viene contato come gioco installato.
3. Confermare una volta **Installa automaticamente**. Preparazione, importazione, metadati, preflight, trasferimento incrementale e verifica remota proseguono nella stessa pipeline.

Non occorre aprire o estrarre manualmente un archivio supportato, né scegliere un emulatore per un gioco identificato. Gli emulatori e i BIOS configurati vengono verificati; non vengono modificati. La modalità alternativa **solo PC** resta disponibile.

I giochi già presenti sono riconosciuti tramite hash e non duplicati. File installati, visibilità nel menu e avvio confermato rimangono evidenze separate.

## Contenuti gestiti

- **Cartucce:** estrazione e riconoscimento tramite struttura, header, hash della libreria/Discovery e DAT. NES, SNES, Mega Drive, Master System, GB/GBC/GBA, Game Gear e Atari 7800 hanno controlli di header quando disponibili. Formati grezzi PCE, Atari 2600 e altre piattaforme esistenti richiedono una corrispondenza affidabile o la decisione prevista dal validatore: l'estensione da sola non dimostra l'identità.
- **PS1:** CUE/BIN multitraccia, ISO PlayStation, multidisco e M3U. Tutti i componenti del gruppo devono essere presenti e validi. I BIN associati non diventano giochi separati. Nelle copie preparate vengono normalizzati i riferimenti CUE/M3U con separatori Windows o maiuscole differenti, solo quando esiste un membro corrispondente univoco. I descrittori originali restano intatti.
- **CHD/PBP:** valgono i controlli conservativi dell'Incremento 7; CHD richiede `chdman verify`, identità PS1 affidabile o confermata e supporto del dispositivo. Un contenitore CHD non dimostra da solo la piattaforma. Nessuna conversione automatica non verificabile.
- **Arcade/Neo Geo:** confronto dei membri con DAT attivi, parent/clone e BIOS. Gli archivi identificati restano compressi per il core; il controllo della corrispondenza DAT/core resta obbligatorio prima della sincronizzazione. Non si converte un set per adattarlo a una versione diversa.
- **Archivi annidati:** analisi ricorsiva entro i limiti indicati sotto; ciascun archivio preparato mantiene la propria provenienza. Più giochi validi possono essere installati indipendentemente.
- **Varianti:** solo una famiglia DAT verificata permette di considerare due giochi varianti. Si applica una preferenza già configurata; in assenza di una scelta univoca viene proposta una decisione comprensibile. File e varianti originali non vengono eliminati.
- **BIOS, documenti, immagini e salvataggi:** esclusi dall'importazione come giochi. I metadati e le immagini dei giochi seguono i servizi e le autorizzazioni già esistenti.

## Job già caricati

Aprire il job in **Installazioni**, consultare **Mostra dettagli archivio** e usare **Rianalizza**. L'app riutilizza il file originale conservato nell'inbox o nella sorgente autorizzata: non richiede un nuovo upload. Se il batch era già autorizzato, gli elementi diventati validi proseguono automaticamente. Un batch non autorizzato mantiene la conferma iniziale obbligatoria.

**Riprova** riprende un'operazione fallita; per un elemento non ancora preparato ripete anche l'analisi. La ripresa del batch in pausa usa i controlli esistenti. **Salta questo elemento** lascia proseguire gli altri giochi. Un conflitto remoto o una dipendenza mancante non vengono ignorati da una scelta manuale.

## Limiti e protezioni

| Risorsa | Limite |
| --- | --- |
| Archivio o singolo membro | 8 GiB |
| Espansione cumulativa, inclusi annidati | 16 GiB per albero di archivi |
| Membri cumulativi | 20.000 |
| Profondità | archivio iniziale più 3 livelli annidati |
| Rapporto di compressione | 1.000:1 |
| Dizionario LZMA/LZMA2/PPMd | 64 MiB |
| Memoria del decoder | 1 GiB; su Windows limite complessivo del Job Object |
| CPU del decoder / tempo di preparazione | 900 secondi; controllo del tempo cumulativo dell'albero |
| Margine libero sul PC | almeno 1 GiB prima dell'estrazione |
| Descrittore CUE/M3U | 1 MiB |

ZIP cifrati, 7z protetti da password, link, file speciali, percorsi assoluti, traversal, ADS, nomi riservati Windows, collisioni di nomi e conflitti file/cartella sono rifiutati. Il contenuto estratto non può superare le dimensioni dichiarate. CRC e hash verificano la decompressione e la conservazione dei file; l'originale viene nuovamente verificato prima della pubblicazione.

Il decoder è un processo dell'applicazione, non un programma trovato nell'archivio. La pausa, l'annullamento o l'arresto del backend terminano il decoder al punto di controllo del processo principale; una morte improvvisa del padre chiude il Job Object Windows. I file incompleti restano nello staging e non sono mai installazioni valide.

Lo staging viene ripulito dopo gli errori e all'avvio. I file già pubblicati in `data/prepared-archives` sono sorgenti persistenti e vengono mantenuti per libreria, ripresa e deduplica: non cancellare manualmente questa cartella. Una copia preparata modificata viene segnalata, senza sovrascriverla automaticamente.

API e limiti della libreria di decompressione: [py7zr](https://py7zr.readthedocs.io/en/latest/api.html). Limiti Windows: [Job Objects](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information).

## Formati non supportati e caso Tekken

ECM e Monkey's Audio (APE) non vengono convertiti. Un `.bin.ecm` non è un BIN direttamente utilizzabile dal core. L'assenza del CUE impedisce inoltre di verificare ordine, tipo, pregap e indici delle tracce: non vengono ricostruiti dal nome dei file.

La rianalisi mostra i membri, le firme rilevate e i file associati nella cartella autorizzata. Una copia completa ottenuta legittimamente in BIN/CUE, ISO o CHD supportato può essere aggiunta ancora compressa: l'app si occupa della preparazione. Non viene chiesto all'utente di estrarre o rinominare i membri dell'archivio problematico.

EmulationStation non viene mai riavviata via SSH. La coda metadati mantiene il comportamento descritto in [INSTALLATIONS.md](INSTALLATIONS.md). Evidenze e limiti del collaudo reale: [VALIDATION-INCREMENT7-1.md](VALIDATION-INCREMENT7-1.md).
