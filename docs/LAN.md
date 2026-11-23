# Accesso da iPhone, Android e altri computer

## Primo avvio

1. Eseguire `Setup.cmd` dopo l'aggiornamento, poi `Start.cmd`. Aprire sul PC ospite http://127.0.0.1:8000/#access.
2. In **Impostazioni → Accesso da smartphone e altri PC**, scegliere e ripetere la password amministratore (12–128 caratteri). Nessuna password predefinita; non inviarla in chat. Dopo la configurazione il login protegge anche localhost, API e OpenAPI.
3. Verificare nell'app che l'interfaccia domestica sia **Privata**. Se Windows la considera Pubblica, il server rifiuta di abilitare la LAN. Cambiare profilo soltanto per la connessione domestica fidata, con il consenso dell'amministratore: le politiche Windows delle reti Private possono consentire maggiore individuazione/condivisione rispetto al profilo Pubblico.
4. Abilitare **Accesso dalla LAN privata**, scegliere la porta e salvare. Attendere la conclusione di upload, download e sincronizzazioni; fermare soltanto il server Windows e riaprire `Start.cmd`.
5. Il server mostra gli indirizzi effettivi delle interfacce Private con gateway. Collegare il telefono alla stessa LAN, aprire l'indirizzo indicato o usare il QR in Impostazioni. Accedere con la password configurata. Il QR contiene soltanto l'URL, mai token o password.

`data/network.json` conserva la preferenza e la porta (1024–65535). `Start.cmd --port 8001` consente una porta temporanea per quell'avvio; per conservarla usare Impostazioni. Il login del dispositivo resta separato da quello del PC. Se non ci sono password o una connessione Privata, l'avvio ricade su localhost. Non eseguire più istanze sullo stesso database.

## Firewall Windows e consenso

L'app non cambia profili, regole o router. Verificare prima se una regola sia necessaria. Per predisporre la regola dedicata, dopo aver ottenuto il consenso, aprire una PowerShell amministratore nella cartella del progetto:

```powershell
.\scripts\enable-lan-firewall.ps1 -InterfaceAlias 'Ethernet 2' -Port 8000 -WhatIf
```

Sostituire l'alias con quello effettivo mostrato nell'app. Dopo aver esaminato la simulazione, eseguire senza `-WhatIf`: PowerShell richiede conferma. `-SetPrivate` propone anche il cambio di profilo della sola interfaccia specificata; usarlo esclusivamente con consenso esplicito.

La regola `RetroPieLibraryManager-LAN-<porta>` consente TCP in ingresso soltanto al Python reale del venv, all'IP locale, interfaccia e subnet rilevati, con profilo **Private**. Non amplia né sostituisce regole esistenti. Se esiste già una regola con quel nome, lo script si ferma. Per disabilitare l'accesso, togliere la preferenza LAN e riavviare il server; la rimozione della sola regola dedicata è un'operazione amministrativa distinta. Nessun port forwarding, UPnP o modifica al router.

Il DHCP può cambiare IP o subnet. L'app aggiorna URL e QR in base agli indirizzi reali; una regola vincolata al vecchio IP può richiedere un aggiornamento amministrativo autorizzato. Le reti ospiti o l'isolamento dei client Wi-Fi possono impedire la comunicazione anche se l'app è configurata correttamente.

## Autenticazione e trasporto

La password è memorizzata come hash scrypt con salt casuale. Le sessioni sono HttpOnly e SameSite=Strict, durano al massimo otto ore e scadono dopo trenta minuti inattive. Il logout le revoca sul server. Le API mutanti richiedono il CSRF associato alla sessione; CORS non è wildcard. Dopo cinque tentativi per IP in cinque minuti, il login richiede di attendere. Il limite globale e quello ai calcoli scrypt simultanei limitano l'abuso delle risorse.

**HTTP non cifra nulla: password, cookie di sessione, percorsi e file possono essere intercettati da chi osserva la connessione. L'hashing sul disco non protegge la password in transito.** La modalità HTTP serve alla semplicità sulla propria LAN fidata e non è adatta a reti condivise non fidate. Non esporre il servizio su Internet.

Per proteggere il trasporto sono disponibili due opzioni senza un cloud obbligatorio:

- **HTTPS locale**: fornire un certificato per il nome/IP effettivo e la relativa chiave privata, conservati fuori dal repository. Avviare `Start.cmd --certfile C:\percorso\server.crt --keyfile C:\percorso\server.key`. Occorre installare e verificare la CA locale sui dispositivi, includere i nomi/IP usati nei SAN e gestire rinnovo e accesso alla chiave. Un certificato non attendibile non va ignorato alla cieca. Questo avvio serve HTTPS anche su localhost; il normale `Start.cmd` mantiene HTTP locale. Con HTTPS il cookie è Secure. Gli argomenti TLS vanno ripassati a ogni avvio.
- **Tunnel SSH privato**: un amministratore può predisporre sul PC ospite un server SSH verificato; un altro PC inoltra una porta locale a 127.0.0.1:8000 con `ssh -N -L 8000:127.0.0.1:8000 utente@pc-ospite`. Si usa poi il browser su localhost, mantenendo l'app in modalità locale. Verificare host key, credenziali e binding locale del tunnel. Su iPhone occorre un client/tunnel appropriato o una VPN privata già amministrata. L'app non installa né configura server SSH/VPN automaticamente.

HTTPS è preferibile per l'uso abituale da Safari senza client aggiuntivi. Certificati, tunnel e funzionamento TLS reale non sono preconfigurati dal progetto; i test verificano i flag dei cookie HTTPS, non l'attendibilità dei certificati sui telefoni personali. [WebCrypto richiede un contesto sicuro](https://developer.mozilla.org/en-US/docs/Web/API/SubtleCrypto); la pipeline usa SHA-256 locale anche su HTTP, senza perdere le verifiche dei blocchi.

## File e smartphone

Selezionare ZIP, RAR o 7z dall'app File/Download del telefono. La scelta di cartelle intere dipende dal browser e dal sistema; non è necessaria per gli archivi. I file vengono caricati sul PC che ospita FastAPI, senza esecuzione dei contenuti. Restano i limiti della [pipeline archivi](ARCHIVES.md), checksum dei blocchi, inventario sicuro e controlli del Raspberry.

Il progresso mostra byte reali; preparazione e verifica senza un totale misurabile restano indeterminate. Il browser deve rimanere attivo durante l'upload: iOS può sospendere una scheda in background. Dopo un'interruzione, riconnettersi/accedere e riselezionare gli stessi originali quando richiesto dal flusso: l'inbox e le ricevute persistenti riusano i blocchi verificati. Non presumere upload continuativo dopo la chiusura del browser.

Una volta ricevuti e confermati i file, importazione e installazione proseguono sul PC. Chiudere EmulationStation soltanto dalla console locale se i metadati devono essere pubblicati. Questo incremento non riavvia EmulationStation né modifica la configurazione del Raspberry.

## Recupero

Per cambiare una password dimenticata, attendere la fine dei job, arrestare il server ed eseguire `Start.cmd --reset-password` sul PC ospite. Il prompt non mostra la password, chiede conferma e revoca tutte le sessioni. Riavviare `Start.cmd`. Non cancellare i dati della libreria.

Se il sito non risponde, verificare PC acceso, server avviato, URL e porta correnti, profilo Privato, regola firewall e assenza di isolamento Wi-Fi. Se scade la sessione, accedere nuovamente. Nessuna funzione di gestione viene resa anonima per risolvere un errore di login.


## ERR_SSL_PROTOCOL_ERROR prima del login

Con l'avvio HTTP ordinario, aprire l'URL completo con `http://`, per esempio `http://192.168.0.31:8000/`. Se il browser tenta `https://` sulla stessa porta HTTP, l'handshake TLS fallisce prima che l'app possa mostrare il login. Il server HTTP non può correggere un errore avvenuto durante il tentativo TLS tramite un redirect applicativo. Controllare lo schema nella barra, aprire una nuova scheda e incollare l'indirizzo completo; non ignorare errori di certificato e non disattivare globalmente le protezioni del browser.

Alcuni browser possono tentare HTTPS per primi: vedere la [documentazione WebKit](https://webkit.org/blog/16301/webkit-features-in-safari-18-2/#security-and-privacy) e la [guida Chrome alle connessioni sicure](https://support.google.com/chrome/answer/10468685). Questo non dimostra quale impostazione fosse attiva sul singolo telefono. Nel collaudo reale del 23 novembre 2026 l'URL HTTP esplicito ha risolto l'errore; l'utente ha poi confermato login e navigazione. Per usare effettivamente HTTPS occorrono certificato attendibile e avvio TLS, come descritto sopra; HTTP continua a non cifrare il traffico.
