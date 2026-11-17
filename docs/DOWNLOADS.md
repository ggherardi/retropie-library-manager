# Guida ai download

## Selezione manuale

1. Aggiornare i provider in **Game Discovery**.
2. Usare ricerca, ordinamento e filtri per piattaforma, fonte, genere e licenza.
3. Selezionare singoli giochi o tutti i risultati filtrati, anche oltre la pagina corrente.
4. Premere **Prepara riepilogo**. Controllare giochi, file, byte, elementi esclusi e spazio.
5. Premere **Conferma e avvia** per creare la coda persistente.

Il riepilogo esclude formati o autorizzazioni non supportati, voci già in coda e duplicati secondo la configurazione. Un cambiamento del catalogo o delle regole prima della conferma richiede un nuovo riepilogo. Ripetere la conferma dello stesso piano restituisce la stessa coda.

## Selezione automatica

Aprire **Capacità RetroPie e regole automatiche**. Scegliere piattaforme, fonti e licenze ammesse, budget massimo per esecuzione, esclusione dei duplicati e concorrenza. Selezionare la modalità automatica e preparare il riepilogo. I criteri vengono salvati e applicati in ordine di titolo e identificatore fino al budget consentito.

La creazione del riepilogo lascia i trasferimenti in attesa della conferma esplicita. Chiudere il dialogo annulla soltanto la proposta. L'app mantiene la modalità manuale come scelta iniziale a ogni apertura della pagina.

## Coda persistente

**Download Manager** aggiorna la visualizzazione ogni 1,5 secondi. Mostra byte ricevuti, totale atteso, tentativi, stato, errori, SHA-256 e riferimento dell'autorizzazione. La concorrenza è configurabile da 1 a 8. Diminuirla limita l'avvio di nuovi trasferimenti mentre quelli attivi terminano o vengono messi in pausa.

Pausa e annullamento vengono registrati immediatamente nella coda. Il worker interrompe il trasferimento al successivo controllo dei dati ricevuti o al timeout di rete. La ripresa utilizza Range e If-Range quando possibile. Se il server risponde con il file completo, il parziale viene riscritto da zero. La risposta Content-Range deve concordare con offset e dimensione attesi.

Gli errori di trasporto e HTTP 408, 429, 500, 502, 503 e 504 comportano fino a tre tentativi con backoff esponenziale e rispetto di Retry-After. Gli errori permanenti o di integrità richiedono un retry esplicito. La coda conserva tentativi, messaggio e istante del prossimo retry. Dopo un riavvio, i trasferimenti attivi diventano pausati. Le voci già confermate e ancora in coda possono proseguire.

L'annullamento elimina i file di lavoro del task dopo l'uscita del worker. Una verifica di integrità fallita elimina il parziale. Un file completo che richiede un retry dell'importazione può essere riutilizzato dopo una nuova verifica. I giochi importati restano nella libreria.

## Integrità e archivi

Ogni download ha una dimensione prevista e un riferimento di integrità proveniente dalla fonte. Il provider a manifest richiede SHA-256. Per GitHub si usa SHA-256 quando dichiarato e l'hash Git del blob presente nell'inventario immutabile. Il controllo Git comprende l'intestazione `blob <dimensione>\0`. Il risultato viene sempre identificato localmente con SHA-256 e deduplicato prima dell'importazione.

Gli archivi ZIP Arcade/Neo Geo restano archivi. Il controllo legge i contenuti per validare CRC, percorsi, assenza di link simbolici e cifratura, numero di elementi, dimensione espansa e rapporto di compressione. Non vengono estratti file nel filesystem. I limiti attuali sono 2.000 elementi, 2 GiB espansi e rapporto massimo 1.000. L'importazione di archivi non accettati richiede una revisione della fonte.

La transazione finale associa il task al gioco, completa i metadati disponibili e registra l'hash. Acquisizioni concorrenti dello stesso contenuto producono un solo record di catalogo. La copia ridondante viene rimossa quando il file già catalogato è ancora integro. Una riacquisizione esplicita può ripristinare un percorso mancante senza sostituire le correzioni dei metadati.

## Capacità e spazio

La capacità utile è la capacità nominale meno la percentuale di margine filesystem e la riserva per il sistema operativo. I valori iniziali sono 32 GB, 5% e 8 GB. È possibile impostare 128 GB o un'altra capacità. La stima include l'intera libreria e le acquisizioni riservate dalla coda. Si tratta di una previsione conservativa dell'esportazione complessiva. La selezione specifica in **Esportazione** mantiene il calcolo esatto dei file e del manifest.

Prima della conferma, il piano controlla anche lo spazio del disco locale, i byte ancora da ricevere e un margine di 64 MiB. Un piano oltre i limiti deve essere ridotto o accompagnato da una configurazione aggiornata. Errori del filesystem durante il trasferimento vengono mostrati nella coda e possono essere riprovati dopo aver liberato spazio.

## Arricchimento della libreria

In **Game Discovery**, usare **Anteprima arricchimento**. Il confronto usa SHA-256 o, per file singoli, l'hash Git ricalcolato dopo aver verificato il SHA-256 locale. Sono mostrati cambiamenti proposti, copertine autorizzate, hash sconosciuti, file mancanti e corrispondenze ambigue.

**Applica metadati e copertine autorizzate** completa i campi vuoti. Anno, autore, genere e descrizione compilati manualmente restano conservati. Il titolo rimane quello scelto nel catalogo. Licenza e provenienza vengono completate quando contengono ancora i valori iniziali. I problemi delle copertine vengono riportati e possono essere ritentati con un nuovo arricchimento.
