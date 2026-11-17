# Sincronizzazione RetroPie

## Arcade nell'Incremento 4

Prima del normale dry-run, i set arcade devono avere un rapporto DAT completo e attuale. Si rileggono hash e dipendenze, versione/hash del core installato, default/override del gioco e BIOS esterni già presenti nelle posizioni supportate. Incompletezza, DAT aggiornato, core diverso o BIOS mancante bloccano il piano. [ARCADE.md](ARCADE.md) descrive organizzazioni dei set, cloni merged e nomi tecnici.

Le preferenze core sono salvate localmente: l'app non modifica emulators.cfg. Nessun BIOS viene scaricato o trasferito separatamente. Le nuove console richiedono un core rilevato/configurato. Restano attive le garanzie SFTP e gamelist sotto descritte.

Non avviare EmulationStation direttamente da SSH senza terminale locale valido. Il precedente TTY_NR=0 ha causato errori `/dev/tty`, risolti dall'utente con reboot. Il nuovo rilevamento legge il TTY senza riavviare nulla. Reboot o cambiamenti di sessione richiedono consenso specifico.

## Uso

Selezionare i giochi nel Catalogo e premere Sincronizza sul Raspberry, oppure usare la selezione paginata in Sincronizzazione. Scegliere il dispositivo, metadati e copertine opzionali. Analizza e prepara dry-run legge e verifica gli originali, la configurazione EmulationStation e i file remoti. Non modifica il Raspberry.

L'anteprima distingue nuovi, già presenti e differenti, mostra tutti i file dei giochi, le immagini disponibili, i percorsi gamelist individuati e lo spazio effettivo. Il margine iniziale è 1 GB; è configurabile per dispositivo e viene ricontrollato durante il lavoro. Confermare i diritti sui giochi e separatamente sulle immagini prima di avviare. Il software non determina la titolarità dei contenuti locali; conserva la dichiarazione dell'operatore insieme al piano. Non trasferisce BIOS.

Il riepilogo resta quello preparato: cambiare opzioni o selezione richiede un nuovo dry-run. Una configurazione dispositivo cambiata invalida i piani precedenti. Conflitti, dipendenze mancanti e spazio insufficiente bloccano la pubblicazione.

## File e ripresa

Le cartelle gestite sono `<rom-root>/<console>/rlm-<hash-gioco>`. I percorsi esistenti esterni a queste cartelle non vengono adottati, rinominati o cancellati. Il confronto incrementale riguarda la destinazione gestita, non una ricerca di equivalenze nell'intera libreria remota. Identici SHA-256 vengono saltati; contenuti differenti o gruppi parziali già pubblicati richiedono revisione dell'utente.

I nuovi giochi sono caricati in `.rlm-stage-<run>-<gioco>`. La rinomina finale avviene solo dopo la verifica di ogni file. La pubblicazione è atomica per gioco, non per l'intera selezione. Un annullamento conserva i giochi completi già pubblicati e rimuove lo staging di quel run, quando la connessione lo permette. Non elimina alcun gioco preesistente.

La coda e i report sono persistenti. Errori di rete hanno fino a tre tentativi con backoff. Dopo un arresto dell'app occorre un retry esplicito. I parziali vengono ripresi soltanto se il prefisso remoto coincide con quello locale; altrimenti vengono riscritti. Dopo ogni trasferimento si ricalcola SHA-256 rileggendo il file via SFTP. Su immagini PS1 grandi la verifica può richiedere tempo e traffico aggiuntivo.

Una disconnessione durante la pulizia può lasciare lo staging. Riprovare lo stesso run dopo il ripristino della connessione; nessuna pulizia estesa o cancellazione di file estranei viene eseguita. I backup gamelist restano conservati.

## PlayStation

CUE e M3U vengono ricontrollati insieme alle dipendenze, senza cambiare gli originali. Un gruppo multidisco include tutte le tracce/dischi e una playlist generata, pubblicata insieme al gruppo. PBP resta un file integro. CHD richiede sia l'estensione nella configurazione EmulationStation sia conferma dell'operatore sul core PS1 rilevato. L'elenco delle estensioni non certifica il supporto dell'emulatore. I BIOS sono esterni a questo flusso.

## Gamelist e copertine

L'app legge il percorso dei sistemi da es_systems.cfg: prima la configurazione utente, poi quella di sistema. Cerca i gamelist nell'ordine ROM della console, directory utente EmulationStation, directory di sistema. Un fallback di sistema viene conservato come base e pubblicato nella destinazione utente scrivibile. La cartella utente può essere il symlink RetroPie verso /opt/retropie/configs/all/emulationstation, risolto esplicitamente durante la diagnostica.

XML UTF-8 con escape, titolo, descrizione, genere, anno, sviluppatore, publisher, preferiti, percorso di avvio e immagine. Un anno senza data completa viene rappresentato come 1 gennaio di quell'anno nel formato richiesto da EmulationStation. I valori sconosciuti non vengono inventati. Campi remoti non gestiti, attributi, commenti, cartelle, rating e contatori sono preservati. Campi locali vuoti non cancellano informazioni remote; campi locali gestiti e compilati prevalgono dopo conferma.

Prima di aggiornare un XML esistente vengono ricontrollati gli hash e creato un backup verificato `gamelist.xml.rlm-backup-<run>`. Cambiamenti intervenuti dal dry-run richiedono una nuova anteprima. La sostituzione è atomica e richiede posix-rename OpenSSH.

EmulationStation in esecuzione può riscrivere i metadati in memoria. Per questo l'app trasferisce ROM/media ma rinvia i gamelist e lo indica nel report. Non chiude né riavvia il frontend. Dopo la chiusura concordata con l'utente, un nuovo dry-run completa i metadati. Il gioco sarà visibile dopo il successivo avvio/aggiornamento di EmulationStation; l'app non certifica il lancio nell'emulatore.

Le copertine vengono copiate da file locali selezionati e autorizzati, senza download aggiuntivi. Il nome basato su SHA-256 consente deduplicazione per console. I file mancanti vengono segnalati e omessi. I riferimenti sono relativi alla directory della console, anche quando il gamelist risiede nella cartella utente.

Riferimenti: [ricerca dei gamelist nel codice RetroPie](https://github.com/RetroPie/EmulationStation/blob/master/es-app/src/SystemData.cpp), [formato gamelist](https://github.com/RetroPie/EmulationStation/blob/master/GAMELISTS.md), [SFTP Paramiko](https://docs.paramiko.org/en/stable/api/sftp.html).
