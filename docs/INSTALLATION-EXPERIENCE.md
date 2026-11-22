# Installazioni: stati e azioni

La modalità iniziale rimane **Importa e installa sul Raspberry**. Seleziona ZIP/RAR/7z o cartelle, controlla l'anteprima e conferma l'autorizzazione all'installazione. La selezione si richiude durante il lavoro per lasciare spazio alle schede; è sempre riapribile.

| Stato | Significato | Azione |
| --- | --- | --- |
| In lavorazione — blu | Analisi, preparazione, importazione, copia o verifica attiva | Attendere; pausa/annullamento ai punti sicuri |
| Installato — verde | I file necessari sono stati copiati e verificati | Aprire nella libreria; la prova d'avvio è facoltativa e separata |
| Già installato — verde | La copia era presente e i file sono stati verificati | Nessuna reinstallazione necessaria |
| Da aggiornare sulla console — neutro | File verificati, ma aggiornamento titoli/immagini o elenco ancora necessario | Seguire l'indicazione locale o aggiornare il piano |
| Serve il tuo intervento — giallo | Serve una scelta, una dipendenza o la risoluzione di un conflitto | Espandere e seguire il passo successivo |
| Installazione bloccata — rosso | File incompleti, archivio corrotto o formato non preparabile in sicurezza | Correggere o selezionare una copia completa, poi rianalizzare |

Gli stati sono scritti per esteso: il colore non è l'unico indicatore. Le fasi non misurabili mostrano un'animazione indeterminata, non una percentuale stimata. La barra a riposo indica solo copie concluse sul totale della selezione, non tempo trascorso. Il numero di operazioni distingue i tentativi ripetuti dalle copie identificate tramite prove affidabili. Le copie ancora da identificare non vengono unite per titolo.

**In corso**, **Serve intervento**, **Completati** e **Tutti** filtrano l'intero job prima della paginazione. Ordinamento per data, titolo o stato. I completati escono dalla sezione In corso automaticamente; gli aggiornamenti sulla console hanno già file verificati e sono nei completati con indicazione separata. La barra superiore comprende tutti i job e consente di aprire quelli concorrenti. La cronologia conserva anche i job vecchi.

Una scheda chiusa mostra titolo, console, stato, fase/progresso quando pertinenti e indicatore di apertura. Usa clic, Invio o Spazio per espanderla. Troverai problema, azione necessaria, cosa accadrà dopo, file, percorso, controlli, dipendenze e diagnostica completa. Le tracce di un gruppo sono nei dettagli e non gonfiano la lista principale. Le vecchie operazioni e i file esclusi restano nella cronologia tecnica, anche quando non sono schede di giochi.

Se il titolo o l'immagine non corrispondono sulla console, usa **Lo vedo, ma titolo o immagine sono da correggere**. Questa azione registra la tua osservazione senza alterare i file. Apri il gioco nella libreria, correggi i metadati, poi usa **Aggiorna metadati**. Il piano viene rigenerato con le protezioni abituali. Se EmulationStation è aperta, l'app chiede di chiuderla localmente; attendi il completamento prima di riaprirla dalla console. Nessun riavvio SSH.

Se l'elenco remoto cambia dopo l'anteprima, il sistema può rigenerare automaticamente il piano una volta. La ripetizione del conflitto rimane esplicita: **Aggiorna piano** legge lo stato attuale senza concedere sovrascritture. Un errore strutturale invece non provoca retry automatici infiniti. Le scelte e i tentativi non aggirano la verifica di integrità o compatibilità.

[Collaudo sui job reali](VALIDATION-INCREMENT7-3.md) · [Pipeline e archivi](ARCHIVES.md) · [Installazioni](INSTALLATIONS.md).
