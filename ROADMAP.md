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

## Incrementi 5 e 5.1 — Popolamento e titoli leggibili (completati)

Acquisizione autorizzata e sincronizzazione di 97 giochi, copertine disponibili e gamelist verificati. La correzione 5.1 assegna nomi leggibili anche ai nodi folder dei gruppi RLM, preservando percorsi e hash. Prove di trasferimento e prove di gioco restano separate.

## Incremento 6 — Essential Classics, Collections & Media

Catalogo di 914 classici con identificatori e fonti, matching conservativo e selezione manuale; Grandi Classici, Collezione Completa e Da Recuperare; dashboard qualità, media autorizzati con anteprima/cache/correzioni e ruoli separati; raccolta EmulationStation verificata sul dispositivo, sincronizzazione incrementale e backup. Valutazione del tema TV esistente senza modifiche video. Risultati e limiti in docs/VALIDATION-INCREMENT6.md.

## Incremento 7 — Installazioni unificate

Aggiungi giochi come ingresso predefinito; file/cartelle browser, drag & drop e sorgenti locali; orchestrazione persistente per elemento con riconoscimento strutturale/hash/DAT, importazione idempotente, arricchimento, preflight e sincronizzazione automatica. Upload riprendibili, pausa/retry, recupero dei job e coda metadati EmulationStation. Visibilità e avvio separati dal trasferimento; navigazione semplificata con strumenti avanzati conservati. Test e collaudo reale documentati in docs/VALIDATION-INCREMENT7.md.

## Sviluppi successivi — Prove e recupero guidato

- Collaudo assistito dalla **sessione locale RetroPie**, con consenso per ogni cambiamento: core/opzioni, controller, avvio e prestazioni per singolo gioco, priorità ai contenuti autorizzati già posseduti. CPS-3 e PS1 da valutare sul Pi 3 B+.
- Ripristino dei backup gamelist, revisione dei conflitti e adozione di librerie già presenti fuori dalle directory RLM, senza cancellazioni automatiche.
- Riconciliazione esplicita delle identità tra DAT, senza unificare titoli per somiglianza; rapporti delle variazioni di manifest/licenze.
- Selezione dei cloni merged tramite capacità realmente supportate dai core; profili BIOS opzionali documentati, senza distribuzione proprietaria.
- Reindicizzazione di percorsi spostati, selezioni massive guidate oltre la pagina, software-list/CHD e conversioni locali opzionali autorizzate.
- Aggiornare la dipendenza di sviluppo picomatch appena il manutentore pubblica una correzione, mantenendo audit e test.

## Sviluppi successivi — Distribuzione desktop

Installer Windows firmato, selezione cartelle nativa, backup/ripristino guidato, aggiornamenti espliciti, cache configurabile, accessibilità e localizzazioni. Benchmark su librerie remote reali e schede 128 GB quando disponibili e autorizzate.

## Incremento 7.1 — Archivi universali (implementato)

ZIP/7z console e PS1, annidamento limitato, decoder isolato, staging atomico, rianalisi dei job, varianti verificate e conservazione del formato arcade. ECM/APE e ricostruzione di descrittori mancanti restano fuori dal supporto automatico: non vengono inventate tracce o dichiarate complete immagini non verificabili.

## Incremento 7.2 — ZIP, RAR e 7z (implementato)

Motore 7-Zip installato e verificato per RAR4/RAR5; volumi RAR, ZIP e 7z, inventario sicuro, decodifica senza destinazioni controllate dall'archivio. Preparazione ZIP dei set arcade soltanto dopo validazione DAT, deduplica fra compressioni e mantenimento dei percorsi esistenti. Test con decoder reali, fixture testuali compresse/solid/multivolume e diagnosi conservativa ECM/APE. Dettagli in docs/VALIDATION-INCREMENT7-2.md.

## Incremento 7.3 — Esperienza installazioni (implementato)

Proiezione backend condivisa degli stati, completamenti basati sui rapporti verificati, distinzione metadati/visibilità/avvio, errori strutturali e interventi, schede compatte, filtri prima della paginazione, avanzamento misurabile o indeterminato, riepiloghi senza duplicati certi, cronologia completa e polling coordinato. Rigenerazione una sola volta del piano in caso di gamelist cambiato, senza aggirare conferme e verifiche. Collaudo con job reali e test documentati in docs/VALIDATION-INCREMENT7-3.md.
