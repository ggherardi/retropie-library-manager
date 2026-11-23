# Collaudo accesso LAN — 22–23 novembre 2026

Versione applicazione 0.8.0, evoluzione di main 18151371b7ca5de736662f4462a34604bd1b7069. Questa verifica non installa giochi o BIOS e non modifica ROM, salvataggi o configurazioni del Raspberry.

## Risultati automatici

| Verifica eseguita realmente | Esito |
|---|---|
| Suite backend completa finale, `python -m pytest -q` | **329 passati**, 408,67 secondi |
| Ruff, `ruff check backend tests migrations` | Passato |
| mypy, `mypy backend` | Passato, 49 moduli |
| Dipendenze Python, `pip check` | Nessun conflitto |
| ESLint, `npm run lint` | Passato |
| TypeScript, `npm run typecheck` | Passato |
| Vitest, `npm test` | **17 passati**, cinque file |
| Build, `npm run build` | Passata, asset locali e avviso MIT del modulo SHA-256 inclusi |
| Playwright completo finale, `npm run test:e2e` | **14 passati**, 2,0 minuti |
| Audit dipendenze frontend produzione, `npm audit --omit=dev` | Zero vulnerabilità segnalate |

I 23 test di autenticazione coprono hash non in chiaro, digest dei token, API e diagnostica protette, CSRF/Origin/Host, cookie HttpOnly/SameSite/Secure con HTTPS, rotazione e revoca, scadenza per inattività e assoluta, nonce bootstrap, login rate-limited persistente, limite di due calcoli scrypt simultanei, rete Pubblica o fuori subnet bloccata, forwarded headers ignorati, preferenze persistenti e generazione PNG del QR da IP verificato. Sette test dell'avvio coprono binding e porta: il server non si espone senza password, su rete Pubblica o quando la LAN è disattivata.

Le prove browser includono **Chromium e WebKit**, viewport 390×844 e SubtleCrypto deliberatamente assente per simulare il contesto HTTP LAN. In entrambi i motori sono stati caricati ZIP, RAR4, RAR5 e 7z veri, generati con contenuti NES sintetici: analisi, importazione, installazione sul trasporto Raspberry simulato, metadati, verifica e logout. Quattro giochi sintetici per motore, **nessun nuovo gioco sul Raspberry reale**. Non si tratta di un decoder mock; restano esclusivamente dati di test, non ROM commerciali o firmware. Navigazione e assenza di overflow sono verificate su Dashboard, Aggiungi giochi, Libreria, Grandi Classici, Da Recuperare, Installazioni e Impostazioni. Un altro test verifica il recupero da errore di connessione, uno la revoca della sessione durante un blocco upload con ritorno al login e API 401.

Le prove preesistenti verificano gli altri flussi, incluse ripresa/ritentativi, sincronizzazione incrementale e preservazione dei dati. Le simulazioni usano dati isolati, non la libreria personale o un dispositivo reale.

## Collaudo iniziale su Windows (22 novembre, prima dell’attivazione)

- Avvio normale aggiornato: salute 200, versione 0.8.0, solo `127.0.0.1:8000` in ascolto.
- `Start.cmd --port 18004`: avvio realmente eseguito su dati isolati, salute 200; inoltro degli argomenti verificato. Istanza di prova arrestata.
- `backend.launch --certfile ... --keyfile ... --port 18003`: server HTTPS realmente avviato con dati isolati, certificato temporaneo con SAN localhost/127.0.0.1 verificato dal client. Bootstrap autenticato e API 200, cookie Secure/HttpOnly/SameSite=Strict, logout e successivo 401. Istanza di prova arrestata. Nessuna CA installata nei dispositivi personali.
- Pagina locale **Impostazioni → Accesso** aperta e verificata con screenshot Chromium: larghezza viewport e pagina entrambe 390 pixel, modulo password presente, profilo Pubblico mostrato e LAN disattivata. Screenshot solo in `.runtime/lan`, escluso da Git.
- Ethernet 2: IP effettivo `192.168.0.31/24`, subnet `192.168.0.0/24`, profilo Windows **Public**. Firewall attivo; nessuna regola dedicata dell'app rilevata.
- Script firewall analizzato da PowerShell e simulato con `-WhatIf`: proposta soltanto la conversione di Ethernet 2 in Privata e la regola `RetroPieLibraryManager-LAN-8000`, limitata a TCP 8000, profilo Private, subnet 192.168.0.0/24, IP locale 192.168.0.31, stessa interfaccia e `C:\Python310\python.exe`. Nessuna modifica applicata in attesa del consenso richiesto dall'utente.

## Attivazione e collaudo LAN reale — 23 novembre

L'utente ha configurato la password personalmente nel modulo locale e ha autorizzato esplicitamente entrambe le modifiche amministrative. Sono stati ricontrollati IP/subnet e assenza di job attivi prima di intervenire. La password non è stata letta né sostituita, le sessioni sono rimaste persistenti e soltanto il server Windows è stato riavviato.

**Accesso LAN attivo:** http://192.168.0.31:8000. Anche http://127.0.0.1:8000 resta funzionante. Preferenza persistente LAN=true e porta 8000; binding effettivo 0.0.0.0, nessun riavvio necessario per le preferenze correnti. La sessione locale già aperta continua a ricevere API 200 dopo il riavvio, senza richiedere né esporre la password nei tool.

Profilo effettivo di **Ethernet 2: Private**. Verificata la sola nuova regola `RetroPieLibraryManager-LAN-8000`: abilitata, inbound allow TCP 8000, profilo Private, LocalAddress 192.168.0.31, RemoteAddress 192.168.0.0/24, InterfaceAlias Ethernet 2, Program C:\Python310\python.exe. Nessuna modifica al router, nessun port forwarding e nessuna altra regola modificata. Gli IP del QR sono derivati dall'interfaccia reale; nessuna credenziale o token inclusi.

**Connessione reale dal Raspberry 192.168.0.13 al PC**, eseguita con il suo client HTTP e senza credenziali:

| Risorsa | HTTP osservato |
|---|---:|
| `/` | 200 |
| `/api/health` | 200 |
| `/api/access/status` | 200, configured=true, authenticated=false, local=false, nonce/CSRF vuoti |
| `/api/games` | 401 |
| `/api/settings` | 401 |
| `/api/access/network` | 401 |
| `/api/access/qr` | 401 |

Questa è una prova su un altro dispositivo fisico nella LAN, non un browser locale. Dimostra raggiungibilità del servizio e protezione delle API anonime; non viene presentata come un login Safari effettuato sul telefono. Non sono stati copiati cookie o password sul Raspberry. Il suo filesystem ROM/BIOS/salvataggi e le configurazioni sono rimasti invariati; non è stato avviato o riavviato EmulationStation.

Anche la pagina login sul vero URL http://192.168.0.31:8000 è stata caricata in WebKit locale a 390×844: modulo visibile, pagina larga 390 pixel e SubtleCrypto realmente assente sul contesto HTTP LAN, senza override artificiali. Questa verifica non inserisce la password personale e non viene presentata come uso di un iPhone fisico. Screenshot in .runtime/lan, escluso da Git.

Il login e gli upload autenticati sono collaudati nei browser Chromium/WebKit con dati isolati descritti sopra. **Collaudo sul telefono reale confermato dall'utente:** il modulo password compare, il login riesce e la libreria/sezioni sono navigabili. L'errore iniziale ERR_SSL_PROTOCOL_ERROR è stato risolto aprendo una nuova scheda e incollando l'URL completo `http://192.168.0.31:8000/`. Il confronto diagnostico ha mostrato HTTP 200 senza redirect e un handshake TLS non valido usando invece https sulla stessa porta. Non sono state modificate impostazioni del browser, firewall o server per risolverlo. L'attendibilità di un certificato HTTPS sul telefono e un tunnel privato non sono collaudati.

HTTP rimane non cifrato: password, cookie e file possono essere intercettati sulla connessione. La [guida LAN](LAN.md) documenta HTTPS locale e tunnel senza cloud obbligatorio. Il firewall ristretto e il login non sostituiscono la cifratura.

Questa prosecuzione modifica solo configurazione runtime autorizzata e verbali: nessuna modifica ai sorgenti rispetto al codice già collaudato del commit 42a1cd7 (329 backend, 17 frontend, 14 browser, lint/typecheck/build superati il 22 novembre). Le nuove verifiche del 23 novembre sono l'analisi dei due archivi, dodici preflight dei giochi e il collaudo LAN effettivo; non si dichiarano rieseguite inutilmente suite invariate.

Il [rapporto Neo Geo](NEOGEO-BIOS-REVIEW.md) ora contiene entrambi gli inventari CRC32/SHA-1/dimensioni e i risultati dei sei giochi. Nessun BIOS trasferito.
