# Configurazione SSH su Windows

## Assistente

1. In Dispositivi, aggiungere nome, hostname/IP, porta, utente, directory ROM/BIOS e margine libero. L'indirizzo è configurabile e può essere un hostname risolvibile nella LAN.
2. Premere Verifica fingerprint. Una chiave già presente nel known_hosts di Windows viene indicata come nota. Una nuova fingerprint va confrontata con una fonte affidabile, per esempio la chiave pubblica host visualizzata sulla console del Raspberry con `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256`.
3. Confermare l'identità. La verifica viene ripetuta prima di salvarla nel known_hosts dedicato dell'app.
4. Aprire Configura chiave Ed25519. La console OpenSSH chiede la password dell'utente Raspberry quando necessaria. Non inserirla in chat, nel browser, in file o in comandi.
5. Attendere la verifica di accesso con chiave e SFTP, poi eseguire Test SSH e diagnostica nell'app.

## Chiavi e permessi

La chiave privata viene generata da cryptography nel formato OpenSSH e rimane in `%LOCALAPPDATA%/RetroPieLibraryManager/ssh/id_ed25519`. Non viene inviata al Raspberry. La cartella e il file hanno ACL senza ereditarietà, limitate all'utente Windows. La chiave non ha passphrase: proteggerla tramite l'account Windows e la sicurezza del disco. L'app conserva in SQLite solo configurazione pubblica e fingerprint, senza password o chiavi private.

L'installazione remota controlla proprietà e assenza di symlink su .ssh e authorized_keys. Prima di modificare un file esistente salva `authorized_keys.rlm-backup-<data>-<id>`, con permessi 600. L'aggiunta è idempotente e la pubblicazione avviene tramite file temporaneo. Non vengono modificate le impostazioni di sshd né disabilitata l'autenticazione password. Il wizard verifica poi la nuova chiave senza password.

## Host key

Il probe richiede Ed25519. Server senza tale algoritmo devono essere verificati dall'operatore: non viene adottato un algoritmo debole o disattivato StrictHostKeyChecking. Paramiko usa RejectPolicy e OpenSSH usa StrictHostKeyChecking=yes. Una host key cambiata blocca la connessione; controllare fisicamente il Raspberry prima di correggere il relativo known_hosts.

Cambiare host, porta o utente nel dispositivo azzera l'identità confermata e richiede nuova verifica. La rimozione del dispositivo cancella soltanto la registrazione locale; chiavi e autorizzazioni remote restano disponibili e possono essere revocate consapevolmente.

Riferimenti: [OpenSSH ssh](https://man.openbsd.org/ssh), [OpenSSH ssh-keygen](https://man.openbsd.org/ssh-keygen), [politiche host key Paramiko](https://docs.paramiko.org/en/stable/api/client.html).
