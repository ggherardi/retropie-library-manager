# Installazione e aggiornamento su Windows 11

Il percorso di riferimento è `C:\Projects\retropie-library-manager`. Sono richiesti Python 3.10+ e Node.js 22.12+ LTS. Git viene usato per aggiornare il codice. Le credenziali GitHub del computer restano gestite esternamente all'applicazione.

## Installazione

Eseguire `Setup.cmd`, poi `Start.cmd`. L'interfaccia è disponibile su [localhost](http://127.0.0.1:8000). Il backend serve la build React e i font locali. L'installazione scarica le dipendenze dai registri Python e npm. La gestione della libreria e dei cataloghi già memorizzati funziona offline.

## Aggiornamento dall'Incremento 1

1. Attendere la fine delle operazioni in corso e arrestare il server con Ctrl+C nella console di avvio.
2. Salvare una copia della cartella `data` e delle ROM esterne alla cartella del progetto.
3. Eseguire `git pull --ff-only` dalla cartella del repository.
4. Eseguire `Setup.cmd` per installare le nuove dipendenze e ricompilare il frontend.
5. Eseguire `Start.cmd`. Alembic applica la migrazione `0002`, conservando giochi e impostazioni precedenti.
6. Aprire Game Discovery e aggiornare i provider.

La migrazione aggiunge autore ai giochi e tabelle per Discovery, provider, piani e download. Il database dell'Incremento 1 rimane compatibile con le funzionalità di catalogo, importazione e preparazione RetroPie. Usare una sola istanza del server sul database.

## Dati locali

- `data/library.db` contiene catalogo, impostazioni e coda.
- `data/provider_cache` conserva i metadati verificati dei provider.
- `data/covers` contiene immagini autorizzate convertite in PNG.
- `data/downloads/<id-task>` contiene file del download e prova dell'autorizzazione.
- `.runtime` contiene i risultati locali dei collaudi e i backup creati durante lo sviluppo.

`RLM_DATA_DIR` permette di usare un'altra cartella dati. Arrestare il servizio prima di copiare il database per un backup ordinario. Il database può contenere percorsi assoluti di ROM e copertine, che vanno mantenuti disponibili durante il ripristino.

## Verifiche

`Check.cmd` esegue Ruff, mypy, pytest, ESLint, TypeScript, Vitest, build e Playwright. Alla prima esecuzione installare il browser di test con `cd frontend` e `npx playwright install chromium`. I test browser usano la porta 18001, un database separato e file sintetici. Le verifiche live dei provider sono documentate nella guida ai provider.

Il servizio locale usa la porta 8000. Se occupata, identificare l'applicazione che la utilizza prima di avviare un'altra istanza. Gli errori di runtime sono registrati in `data/application.log`, con rotazione. Il controllo delle dipendenze frontend è disponibile con `npm audit` nella cartella `frontend`.
