# Collaudo accesso LAN — 22 novembre 2026

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

## Collaudo effettivo su Windows

- Avvio normale aggiornato: salute 200, versione 0.8.0, solo `127.0.0.1:8000` in ascolto.
- `Start.cmd --port 18004`: avvio realmente eseguito su dati isolati, salute 200; inoltro degli argomenti verificato. Istanza di prova arrestata.
- `backend.launch --certfile ... --keyfile ... --port 18003`: server HTTPS realmente avviato con dati isolati, certificato temporaneo con SAN localhost/127.0.0.1 verificato dal client. Bootstrap autenticato e API 200, cookie Secure/HttpOnly/SameSite=Strict, logout e successivo 401. Istanza di prova arrestata. Nessuna CA installata nei dispositivi personali.
- Pagina locale **Impostazioni → Accesso** aperta e verificata con screenshot Chromium: larghezza viewport e pagina entrambe 390 pixel, modulo password presente, profilo Pubblico mostrato e LAN disattivata. Screenshot solo in `.runtime/lan`, escluso da Git.
- Ethernet 2: IP effettivo `192.168.0.31/24`, subnet `192.168.0.0/24`, profilo Windows **Public**. Firewall attivo; nessuna regola dedicata dell'app rilevata.
- Script firewall analizzato da PowerShell e simulato con `-WhatIf`: proposta soltanto la conversione di Ethernet 2 in Privata e la regola `RetroPieLibraryManager-LAN-8000`, limitata a TCP 8000, profilo Private, subnet 192.168.0.0/24, IP locale 192.168.0.31, stessa interfaccia e `C:\Python310\python.exe`. Nessuna modifica applicata in attesa del consenso richiesto dall'utente.

## Verifiche reali ancora da completare

**L'accesso LAN operativo non è ancora attivato.** La password amministratore deve essere scelta e inserita dall'utente nel modulo locale. È stata richiesta separatamente l'autorizzazione a cambiare il profilo dell'interfaccia e creare la regola firewall; la richiesta non equivale al consenso. L'app rimane intenzionalmente su localhost, senza configurare una password al posto dell'utente o aprire un accesso anonimo.

Dopo questi passaggi occorre attivare la preferenza, riavviare soltanto il server Windows e verificare una connessione da un altro dispositivo LAN. Il Raspberry è disponibile via SSH per controlli in sola lettura; la raggiungibilità del sito dal Raspberry non è stata ancora dichiarata verificata. Nessun accesso su iPhone fisico è stato eseguito: **WebKit con viewport iPhone è una simulazione locale, non Safari su un telefono reale**. L'attendibilità di un eventuale certificato sul telefono e un tunnel privato non sono collaudati.

HTTP rimane non cifrato. Login e controlli API non proteggono le credenziali o i file dall'intercettazione sulla rete. La [guida LAN](LAN.md) documenta HTTPS e tunnel senza introdurre servizi cloud obbligatori.

Il [rapporto Neo Geo separato](NEOGEO-BIOS-REVIEW.md) registra le verifiche in sola lettura del core e dei sei candidati, e i due percorsi BIOS ancora necessari. Non è stato trasferito alcun BIOS.
