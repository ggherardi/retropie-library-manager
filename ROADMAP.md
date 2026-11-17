# Roadmap

## Incremento 1 — Libreria locale (completato)

Catalogo, dashboard, importazione con anteprima e deduplica, PS1 multidisco, manifest provider, download con integrità, esportazioni locali con dry-run e manifest, test e script Windows.

## Incremento 2 — Game Discovery e download (completato)

Cataloghi reali GBDev/GBADev/NESDev, ricerca e filtri, selezione multipla, prove delle autorizzazioni, regole automatiche con conferma, coda persistente concorrente con pausa/ripresa/retry, verifica e importazione, deduplica SHA-256, copertine autorizzate, arricchimento conservativo e capacità target 32/128 GB. itch.io e PDRoms restano collegamenti alle fonti: non è stato accertato un accesso automatico anonimo utilizzabile nel progetto. Incluse guide, test backend/browser e verifica live dei provider.

## Incremento 3 — Raspberry Pi e SSH/SFTP

Dispositivi multipli e predefinito, assistente Ed25519 e fingerprint, diagnostica reale, sincronizzazione incrementale con dry-run/conferma, gruppi atomici PS1, SHA-256, annullamento/retry, capacità effettiva, gamelist con backup e preservazione dei metadati, copertine locali autorizzate, test automatici e collaudo sul Raspberry. Nessun aggiornamento del sistema o trasferimento BIOS. I risultati e i limiti del collaudo sono in docs/VALIDATION-INCREMENT3.md.

## Incremento 4 — Massive Library & Arcade Intelligence

Implementati cataloghi DAT/XML/JSON/CSV versionati, streaming/background/cancel, FTS5 e paginazione; parent/clone/BIOS, ZIP/7z con hash componenti e set split/merged/non-merged/full-non-merged; MAME 0.78 e FBNeo per revisione reale; rilevamento read-only e blocchi di sync; piattaforme/Arcade/Neo Geo, raccolte e varianti; evidenze di test, screenshot e matching conservativo; due homebrew verificati SNES/Mega Drive, report acquisizioni e cancellazione delle scansioni. Aggiunte SG-1000, PCE, Atari 2600/7800, Game Gear, NGP/NGPC. Collaudo su oltre 10.000 record reali e migliaia di file sintetici.

I limiti sono espliciti: nessuna promessa di frame rate, nessun clone merged esportato fingendo di selezionarlo, nessuna ROM commerciale o BIOS acquisito automaticamente, nessun riavvio o configurazione remota impliciti. Corrispondenza DAT/core e test di gioco restano separati.

## Incremento 5 proposto — Prove e recupero guidato

- Collaudo assistito dalla **sessione locale RetroPie**, con consenso per ogni cambiamento: core/opzioni, controller, avvio e prestazioni per singolo gioco, priorità ai contenuti autorizzati già posseduti. CPS-3 e PS1 da valutare sul Pi 3 B+.
- Ripristino dei backup gamelist, revisione dei conflitti e adozione di librerie già presenti fuori dalle directory RLM, senza cancellazioni automatiche.
- Riconciliazione esplicita delle identità tra DAT, senza unificare titoli per somiglianza; rapporti delle variazioni di manifest/licenze.
- Selezione dei cloni merged tramite capacità realmente supportate dai core; profili BIOS opzionali documentati, senza distribuzione proprietaria.
- Reindicizzazione di percorsi spostati, selezioni massive guidate oltre la pagina, software-list/CHD e conversioni locali opzionali autorizzate.
- Aggiornare la dipendenza di sviluppo picomatch appena il manutentore pubblica una correzione, mantenendo audit e test.

## Incremento 6 proposto — Distribuzione desktop

Installer Windows firmato, selezione cartelle nativa, backup/ripristino guidato, aggiornamenti espliciti, cache configurabile, accessibilità e localizzazioni. Benchmark su librerie remote reali e schede 128 GB quando disponibili e autorizzate.
