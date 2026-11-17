# Roadmap

## Incremento 1 — Libreria locale (completato)

Catalogo, dashboard, importazione con anteprima e deduplica, PS1 multidisco, manifest provider, download con integrità, esportazioni locali con dry-run e manifest, test e script Windows.

## Incremento 2 — Game Discovery e download (completato)

Cataloghi reali GBDev/GBADev/NESDev, ricerca e filtri, selezione multipla, prove delle autorizzazioni, regole automatiche con conferma, coda persistente concorrente con pausa/ripresa/retry, verifica e importazione, deduplica SHA-256, copertine autorizzate, arricchimento conservativo e capacità target 32/128 GB. itch.io e PDRoms restano collegamenti alle fonti: non è stato accertato un accesso automatico anonimo utilizzabile nel progetto. Incluse guide, test backend/browser e verifica live dei provider.

## Incremento 3 proposto — Sincronizzazione RetroPie

- SSH/SFTP con verifica host key e credenziali nel credential store Windows.
- Inventario remoto, confronto con manifest, anteprima delle differenze e conferma delle operazioni.
- Spazio effettivo sul Raspberry Pi, trasferimenti riprendibili, verifica hash, pubblicazione atomica e report.
- Generazione gamelist.xml, copertine e metadati EmulationStation con percorsi relativi e corretta codifica XML.
- Prove su Raspberry Pi 3 B+ e microSD 32/128 GB; verifica core e versioni dei romset Arcade/Neo Geo.
- Politica di conflitto e backup esplicita; nessuna cancellazione remota implicita.

## Incremento 4 — Fonti e qualità del catalogo

- Provider SNES, Mega Drive, Master System, Neo Geo/Arcade con API e autorizzazioni verificabili; oggi supportati tramite importazione locale o manifest dell'operatore.
- Nuove fonti di metadati e immagini autorizzate, mantenendo il matching conservativo.
- Percorsi spostati, reindicizzazione, raccolte e modifica massiva con anteprima.
- Gestione avanzata dei dischi e conversioni opzionali CHD con strumenti locali autorizzati.
- Cataloghi firmati e report delle variazioni di licenza/disponibilità.

## Incremento 5 — Distribuzione desktop

- Installer Windows firmato, aggiornamenti espliciti e backup/ripristino guidato.
- Selezione cartelle tramite shell nativa e avanzamento/cancellazione dei lavori locali.
- Benchmark con decine di migliaia di titoli, limiti di cache configurabili e recupero dopo arresto forzato.
- Revisione dell'accessibilità e traduzioni dell'interfaccia.
