# Archivi ZIP, RAR e 7z — Incremento 7.2

## Aggiungere giochi

1. Trascinare ZIP/RAR/7z in **Aggiungi giochi**, oppure usare il selettore file/cartelle. È possibile leggere direttamente le cartelle autorizzate del PC.
2. Controllare l'anteprima: ogni gioco riconosciuto ha una propria riga. Un contenitore preparato non viene contato come gioco installato.
3. Confermare una volta **Installa automaticamente**. Preparazione, importazione, metadati, preflight, trasferimento incrementale e verifica remota proseguono nella stessa pipeline.

Non occorre aprire o estrarre manualmente un archivio supportato, né scegliere un emulatore per un gioco identificato. Gli emulatori e i BIOS configurati vengono verificati; non vengono modificati. La modalità alternativa **solo PC** resta disponibile.

I giochi già presenti sono riconosciuti tramite hash e non duplicati. File installati, visibilità nel menu e avvio confermato rimangono evidenze separate.

## Contenuti gestiti

- **Cartucce:** estrazione e riconoscimento tramite struttura, header, hash della libreria/Discovery e DAT. NES, SNES, Mega Drive, Master System, GB/GBC/GBA, Game Gear e Atari 7800 hanno controlli di header quando disponibili. Formati grezzi PCE, Atari 2600 e altre piattaforme esistenti richiedono una corrispondenza affidabile o la decisione prevista dal validatore: l'estensione da sola non dimostra l'identità.
- **PS1:** CUE/BIN multitraccia, ISO PlayStation, multidisco e M3U. Tutti i componenti del gruppo devono essere presenti e validi. I BIN associati non diventano giochi separati. Nelle copie preparate vengono normalizzati i riferimenti CUE/M3U con separatori Windows o maiuscole differenti, solo quando esiste un membro corrispondente univoco. I descrittori originali restano intatti.
- **CHD/PBP:** valgono i controlli conservativi dell'Incremento 7; CHD richiede `chdman verify`, identità PS1 affidabile o confermata e supporto del dispositivo. Un contenitore CHD non dimostra da solo la piattaforma. Nessuna conversione automatica non verificabile.
- **Arcade/Neo Geo:** confronto dei membri con DAT attivi, parent/clone e BIOS. Gli ZIP compatibili restano intatti. RAR e 7z vengono preparati in ZIP soltanto dopo un riscontro DAT completo, incluse le dipendenze disponibili, e il risultato viene nuovamente validato. Un set già catalogato con lo stesso DAT e file verificati riusa i percorsi esistenti, anche se il nuovo contenitore usa una compressione diversa; il controllo della corrispondenza DAT/core resta obbligatorio prima della sincronizzazione. Non si converte un set per adattarlo a una versione diversa.
- **Archivi annidati:** analisi ricorsiva entro i limiti indicati sotto; ciascun archivio preparato mantiene la propria provenienza. Più giochi validi possono essere installati indipendentemente.
- **Varianti:** solo una famiglia DAT verificata permette di considerare due giochi varianti. Si applica una preferenza già configurata; in assenza di una scelta univoca viene proposta una decisione comprensibile. File e varianti originali non vengono eliminati.
- **BIOS, documenti, immagini e salvataggi:** esclusi dall'importazione come giochi. I metadati e le immagini dei giochi seguono i servizi e le autorizzazioni già esistenti.

## Motore RAR su Windows

RAR4 e RAR5 vengono letti da **7-Zip 26.06 o successivo**, installato separatamente. `Setup.cmd` verifica la versione e installa/aggiorna il pacchetto ufficiale `7zip.7zip` tramite WinGet quando serve. Il motore viene cercato in `%ProgramFiles%/7-Zip/7z.exe`; `RLM_7ZIP` può indicare un altro percorso assoluto amministrato dall'operatore. Un motore assente o obsoleto produce una diagnosi con l'azione necessaria e il job rimane ripetibile. Le librerie Python continuano a gestire ZIP e 7z ordinari.

Non vengono distribuiti binari 7-Zip nel repository. Il progetto usa il programma installato tramite invocazioni senza shell, esclusivamente per elencare, verificare e decodificare dati verso stdout. La [licenza ufficiale](https://www.7-zip.org/license.txt) permette l'uso anche commerciale; distingue LGPL, porzioni BSD e restrizione unRAR. Un'eventuale distribuzione futura dei binari deve conservare gli avvisi e rispettare le relative condizioni. Il decoder RAR non viene usato per implementare un compressore RAR. [Download ufficiale](https://www.7-zip.org/download.html).

## Volumi multipli

Selezionare insieme tutti i volumi, oppure leggere la cartella già autorizzata. Non servono concatenazioni o rinomine manuali. Sono gestiti:

- RAR `nome.part1.rar`, `nome.part2.rar`, ecc., anche con zeri iniziali.
- RAR con nomi precedenti: `nome.rar`, `nome.r00`, `nome.r01`, ecc.
- 7z/ZIP suddivisi in byte: `nome.7z.001`, `.002`, ecc. e `nome.zip.001`, `.002`, ecc.
- ZIP con dischi: `nome.z01`, `.z02`, ecc. e volume finale `nome.zip`.

Una famiglia viene analizzata una volta anche selezionando i volumi in ordine inverso. Gli hash di **tutti** i volumi partecipano all'identità della cache; modificare un volume non riusa una preparazione basata sugli altri. I volumi devono essere file regolari nella stessa cartella, massimo 1.000 e 8 GiB complessivi. Parti mancanti, numerazione non consecutiva e fine archivio troncata sono segnalate prima dell'installazione. La stessa logica vale per volumi presenti dentro un altro archivio. Non sono supportate convenzioni di volume arbitrarie o archivi autoestraenti.

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

ZIP, RAR e 7z protetti da password, link, file speciali, percorsi assoluti, traversal, ADS, nomi riservati Windows, collisioni di nomi e conflitti file/cartella sono rifiutati. Il contenuto estratto non può superare le dimensioni dichiarate. CRC e hash verificano la decompressione e la conservazione dei file; l'originale viene nuovamente verificato prima della pubblicazione.

Il worker esegue soltanto codice dell’app e, quando necessario, il motore 7-Zip installato. Nessun file dell’archivio viene eseguito. Il Job Object Windows contiene launcher Python, interprete e al massimo un decoder esterno; il limite di 1 GiB è complessivo. Il parser controlla nomi, dimensioni, link e stream prima di passare al decoder, che invia i byte allo stdout: soltanto il writer dell’app crea i file di destinazione già validati. La pausa, l'annullamento o l'arresto del backend terminano il decoder al punto di controllo del processo principale; una morte improvvisa del padre chiude il Job Object Windows. I file incompleti restano nello staging e non sono mai installazioni valide.

Lo staging viene ripulito dopo gli errori e all'avvio. I file già pubblicati in `data/prepared-archives` sono sorgenti persistenti e vengono mantenuti per libreria, ripresa e deduplica: non cancellare manualmente questa cartella. Una copia preparata modificata viene segnalata, senza sovrascriverla automaticamente.

API e limiti della libreria di decompressione: [py7zr](https://py7zr.readthedocs.io/en/latest/api.html). Limiti Windows: [Job Objects](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information).

## Formati non supportati e caso Tekken

ECM e Monkey's Audio (APE) non vengono convertiti. Un `.bin.ecm` non è un BIN direttamente utilizzabile dal core. L'assenza del CUE impedisce inoltre di verificare ordine, tipo, pregap e indici delle tracce: non vengono ricostruiti dal nome dei file.

La rianalisi mostra i membri, le firme rilevate e i file associati nella cartella autorizzata. Una copia completa ottenuta legittimamente in BIN/CUE, ISO o CHD supportato può essere aggiunta ancora compressa: l'app si occupa della preparazione. Non viene chiesto all'utente di estrarre o rinominare i membri dell'archivio problematico.

EmulationStation non viene mai riavviata via SSH. La coda metadati mantiene il comportamento descritto in [INSTALLATIONS.md](INSTALLATIONS.md). Evidenze e limiti del collaudo reale: [VALIDATION-INCREMENT7-2.md](VALIDATION-INCREMENT7-2.md).
