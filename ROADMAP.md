# Roadmap

## Incremento 1 — Libreria locale (completato)

Catalogo, dashboard, importazione con anteprima e deduplica, PS1 multidisco, manifest provider, download con integrità, esportazioni locali con dry-run e manifest, test e script Windows.

## Incremento 2 — Game Discovery e download (completato)

Cataloghi reali GBDev/GBADev/NESDev, ricerca e filtri, selezione multipla, prove delle autorizzazioni, regole automatiche con conferma, coda persistente concorrente con pausa/ripresa/retry, verifica e importazione, deduplica SHA-256, copertine autorizzate, arricchimento conservativo e capacità target 32/128 GB. itch.io e PDRoms restano collegamenti alle fonti: non è stato accertato un accesso automatico anonimo utilizzabile nel progetto. Incluse guide, test backend/browser e verifica live dei provider.

## Incremento 3 — Raspberry Pi e SSH/SFTP

Dispositivi multipli e predefinito, assistente Ed25519 e fingerprint, diagnostica reale, sincronizzazione incrementale con dry-run/conferma, gruppi atomici PS1, SHA-256, annullamento/retry, capacità effettiva, gamelist con backup e preservazione dei metadati, copertine locali autorizzate, test automatici e collaudo sul Raspberry. Nessun aggiornamento del sistema o trasferimento BIOS. I risultati e i limiti del collaudo sono in docs/VALIDATION-INCREMENT3.md.

## Incremento 4 proposto — Qualità, compatibilità e recupero

- Revisione guidata dei conflitti remoti, ripristino dei backup gamelist e adozione dei giochi già presenti fuori dalle directory RLM.
- Profili verificati per core PS1/Arcade, collaudi di avvio concordati e librerie grandi su microSD 128 GB.
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
