# Incremento 5.1 — Titoli EmulationStation

## Diagnosi sul dispositivo reale

Il catalogo locale contiene 97 titoli leggibili. I 97 elementi `<game>` nei 11 gamelist del Raspberry contenevano già i nomi corretti; mancavano tutti gli elementi `<folder>` delle directory `rlm-<hash>`. EmulationStation mostrava quindi il nome tecnico della cartella prima di entrarvi. La cartella segnalata `rlm-01b764db2ebd393c37388e89` contiene F-FF: la voce del gioco era già corretta.

Sono stati controllati i tre percorsi di ricerca documentati: directory ROM, directory utente EmulationStation, directory di sistema. I gamelist attivi sono sotto `/opt/retropie/configs/all/emulationstation/gamelists/<console>/gamelist.xml`, tramite il collegamento `~/.emulationstation`. Nessun gamelist alternativo li mascherava; il log confermava il caricamento da questo percorso. `SaveGamelistsMode` era `on exit`.

Riferimento primario: [formato e precedenza dei gamelist di RetroPie EmulationStation](https://github.com/RetroPie/EmulationStation/blob/master/GAMELISTS.md), che distingue i metadati di gioco e cartella.

## Correzione

Il generatore crea le voci delle cartelle gestite con titolo, descrizione e copertina del gioco. Mantiene gli identificativi nei percorsi interni e non sposta le ROM. Non rinomina cartelle personali. Conserva attributi, commenti, campi sconosciuti, statistiche e i valori predefiniti omessi da EmulationStation.

Il titolo acquisito nel catalogo ha precedenza. Se manca, il merge conserva un nome leggibile già nei metadati remoti; in ultima istanza mantiene il nome originale del file, senza espansioni speculative. Identificativi tecnici e nomi generici di tracce/dischi restano «Titolo da verificare». La mancanza di un titolo di catalogo viene segnalata nel piano e negli avvisi anche nelle sincronizzazioni successive.

## Test automatici

- Backend: **130 test passati**; nessun fallimento.
- Frontend: **6 test Vitest passati**, **5 test Playwright passati**.
- Ruff, mypy, ESLint, TypeScript, build Vite: tutti superati.
- Formattazione Ruff dei file Python modificati e `git diff --check`: superati.
- Regressioni: NES/F-FF, Game Boy/2048gb, arcade/Gridlee, titoli già corretti, titolo mancante, identificativi interni, percorsi relativi/assoluti, cartelle personali, conflitti, multidisco, XML sicuro, statistiche/preferiti, backup, ROM e salvataggi, seconda sincronizzazione senza scritture.

## Verifica reale

EmulationStation è stata chiusa dall'utente dalla console locale, con successiva verifica dell'assenza del processo. Il dry-run ha verificato ROM e copertine già presenti e previsto esclusivamente gli 11 XML, con 140.732 byte necessari includendo i backup. Il margine configurato di 4 GiB è stato rispettato.

| Controllo | Risultato |
| --- | ---: |
| Titoli delle cartelle corretti | 97 |
| Titoli ancora sconosciuti | 0 |
| Voci gioco già corrette conservate | 97 |
| Gamelist aggiornati e verificati SHA-256 | 11 |
| Backup dei gamelist verificati SHA-256 | 11 |
| Byte XML trasferiti | 90.443 |
| File preesistenti con percorso, dimensione e SHA-256 invariati | 230 |
| ROM tra questi file | 97 |
| Copertine tra questi file | 35 |
| Avvisi di provenienza/licenza tra questi file | 97 |
| Salvataggi presenti e preservati | 1 |
| Spazio libero dopo la correzione | 26.992.111.616 byte |
| Byte richiesti dal secondo dry-run | 0 |
| Byte trasferiti dalla seconda sincronizzazione completata | 0 |

Il salvataggio reale di 2048 misura 8.192 byte ed è rimasto identico. Le statistiche di gioco e tutti i campi delle voci `<game>` sono semanticamente identici al baseline acquisito dopo la chiusura di EmulationStation. Il catalogo locale non è stato modificato. Sono stati verificati anche l'esistenza dei percorsi di gioco/cartella e delle immagini referenziate.

La seconda sincronizzazione è stata realmente confermata ed è terminata con tutti gli 11 XML già presenti, zero nuovi backup e zero byte trasferiti.

Manifest, snapshot, database di backup e log operativi rimangono nella directory `.runtime/increment5-1/`, esclusa da Git. I backup remoti sono accanto agli XML, con suffisso `.rlm-backup-<run-id>`. Nessuna ROM, BIOS, chiave o credenziale è inclusa nel commit.

Non è stato eseguito alcun riavvio remoto di EmulationStation o del Raspberry. Questa verifica riguarda metadati, percorsi e integrità; non certifica l'avvio o la giocabilità dei 97 titoli.
