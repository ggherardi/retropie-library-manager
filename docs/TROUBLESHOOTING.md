# Risoluzione dei problemi

| Problema | Controllo e recupero |
| --- | --- |
| Host non raggiungibile | Verificare alimentazione, LAN, hostname/IP e porta. Modificare il dispositivo se DHCP ha cambiato indirizzo. |
| Host key sconosciuta | Confrontare la fingerprint con il Raspberry e confermarla nell'assistente. |
| Host key cambiata | Interrompere i tentativi, verificare l'identità reale e correggere solo la voce pertinente in known_hosts. Non disattivare i controlli SSH. |
| Nessun handshake Ed25519 | Verificare server OpenSSH e host key disponibili. Nessun fallback debole viene applicato. |
| Accesso con chiave rifiutato | Ripetere l'assistente interattivo, verificare utente e permessi .ssh/authorized_keys. Inserire password solo nel terminale OpenSSH. |
| Console SSH non disponibile | Verificare la presenza del client OpenSSH Windows e che l'app sia eseguita nell'account desktop interattivo. |
| Directory o permessi errati | Correggere il percorso dispositivo. La diagnostica mostra presenza/lettura/scrittura; l'app non esegue chmod sulle cartelle ROM o BIOS. |
| File remoto differente | Riesaminare il gioco e la destinazione. Il sistema non sovrascrive il contenuto e non lo cancella automaticamente. |
| Symlink non consentito | Usare una radice canonica dedicata. Solo l'alias EmulationStation rilevato e verificato viene risolto esplicitamente. |
| Spazio insufficiente | Ridurre selezione o liberare spazio consapevolmente. Conservare il margine minimo; viene letto lo spazio reale disponibile all'utente SSH. |
| Connessione interrotta | Usare Riprova trasferimento. I file parziali vengono confrontati e ripresi; i gruppi completi sono saltati. |
| Gamelist cambiato dopo anteprima | Preparare un nuovo dry-run; nessuna sostituzione del file modificato avviene con il vecchio piano. |
| Metadati rinviati | Chiudere EmulationStation in un momento concordato, poi ripetere il dry-run. L'app non interrompe sessioni di gioco. |
| posix-rename non disponibile | Conservare il backup e verificare il server SFTP. Non è previsto un fallback che cancelli il gamelist prima di rinominarlo. |
| CHD bloccato | Verificare core PS1, versione e configurazione. Confermare il supporto nel dispositivo solo dopo tale verifica. |
| Copertina assente | Verificare il file locale e l'autorizzazione; l'omissione viene segnalata e non cancella un'immagine già registrata nel gamelist. |

I log applicativi sono in data/application.log; piani e report sono conservati in SQLite. Chiavi private e password non fanno parte dei log. Prima di condividere log o report, considerare che possono contenere percorsi locali/remoti e nomi dei giochi.
