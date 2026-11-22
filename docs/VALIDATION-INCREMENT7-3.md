# Incremento 7.3 — Installation Experience Redesign

Data del collaudo: **22 novembre 2026**. Versione: **0.7.3**.

## Risultato

Aggiungi giochi mantiene ZIP/RAR/7z e l'installazione automatica come percorso predefinito. La selezione è riapribile e si compatta quando è scelto un job. La barra persistente mostra tutti i job, le copie distinte, le operazioni, completati, attivi, interventi, bloccati e il gioco/fase correnti. I dati di trasferimento sono misurati in byte; analisi e verifica usano un indicatore indeterminato. A riposo la barra indica soltanto copie concluse sul totale, non una previsione di tempo.

Le schede chiuse mostrano titolo, console leggibile, icona/copertina, stato, fase e progresso pertinente. Nel collaudo reale desktop sono state misurate a **72 px**. Le informazioni tecniche, i rapporti storici, le tracce associate e le azioni sono consultabili espandendo la scheda. La cronologia tecnica ha una paginazione separata, anche per selezioni con soli file accessori.

In corso, Serve intervento, Completati e Tutti filtrano l'intero job prima della paginazione. Ordinamento per data, titolo e stato; i completati escono dagli attivi automaticamente. I colori hanno sempre un'etichetta testuale. Le schede details/summary sono apribili da tastiera, i controlli hanno focus visibile e i progressi un'etichetta accessibile; supportata la preferenza di riduzione del movimento. Verificato il layout a 390 px senza overflow orizzontale.

Il modello è prodotto dal backend: stato tecnico, stato utente, fase, causa, passo successivo, azioni consentite, progresso e file verificati. I rapporti di sincronizzazione sono la prova di completamento, non l'avvio del gioco. Nessuna migrazione: record e cronologia precedenti restano disponibili. La segnalazione di metadati errati usa i JSON già persistenti e conserva la visibilità confermata.

## Casi reali, senza simulare gli stati

| Caso | Evidenza osservata | Risultato nella UI |
| --- | --- | --- |
| Disney’s Hercules | Rapporti reali di trasferimento/verifica e aggiornamento XML. L'utente ha dichiarato visibilità confermata e titolo errato. | **Da aggiornare sulla console**, file verificati, visibilità confermata, metadati da correggere. Registrata solo questa osservazione effettiva; nessun cambio artificiale allo stato tecnico. Apri nella libreria e Aggiorna metadati sono disponibili. |
| PaRappa the Rapper | I file del gioco erano stati pubblicati/verificati prima del conflitto del gamelist. Il vecchio run resta fallito in cronologia. | **Da aggiornare sulla console**, spiegazione del conflitto comprensibile e azione **Aggiorna piano**, senza presentare le ROM come trasferimento ancora attivo. |
| Dino Crisis | Job reali con errore ISO9660 di immagine incompleta. | **Installazione bloccata**, richiesta di copia completa/corretta; nessun retry automatico infinito. Le tracce associate vengono raccolte nei dettagli. Restano separate le operazioni su copie per cui non esiste prova sufficiente di identità comune. |
| Neo Geo | Rapporti DAT reali di Neo Turf Masters, Windjammers e altri indicano dipendenze BIOS mancanti/non corrispondenti. | **Serve il tuo intervento**, indicazione della dipendenza e del ricontrollo dopo aver fornito un BIOS legittimo. Nessuna selezione di variante incompleta può aggirare la verifica. |
| Tekken 3 | ECM/APE non convertibili nella pipeline e descrittore assente nei job già caricati. | **Installazione bloccata**; un gruppo principale, tracce audio nei dettagli. Non dichiarato PS1 completo solo in base al nome. |
| Super Monaco GP II | Rapporto reale di trasferimento e verifica completati. | **Installato**, nella sezione Completati; nessuna prova di avvio inventata e nessun controllo tecnico generico usato come stato corrente. La progressione attiva è coperta dai test sul flusso reale con file sintetici. |

Il collaudo usa gli stati già presenti nella libreria reale. Non sono stati reimpostati per mostrare animazioni o completamenti. Hercules resta con titolo da correggere sulla console; il redesign rende esplicito questo problema, non lo dichiara risolto.

## PaRappa: nuovo piano sicuro

È stato generato un **dry-run reale in sola lettura**, senza confermarlo:

- `can_sync: true`, nessun blocco.
- Due file gioco **presenti**, zero nuovi e zero modificati.
- **3.364 byte** richiesti per i metadati.
- Spazio rilevato **23.614.611.456 byte**, riserva di 4 GiB rispettata.

Questo dimostra che il piano può essere rigenerato rispetto al gamelist attuale senza sovrascrivere file non verificati. L'esecuzione resta da avviare con l'azione contestuale; nessun XML remoto è stato scritto per far passare il collaudo. Per i futuri job attivi, un conflitto esatto di gamelist dopo il dry-run consente una sola rigenerazione automatica, con tutte le verifiche abituali ripetute. Un secondo conflitto richiede azione esplicita. Il comportamento automatico è testato con un dispositivo sintetico e controllando che la rigenerazione non scriva file.

## Riepiloghi e identificazione

Al rilascio, la cronologia contiene **60 operazioni di gioco**, riferite a **38 copie distinte secondo le evidenze disponibili**: **9 giochi identificati** e **29 copie ancora da identificare**. Nel riepilogo risultano 9 copie con file verificati/importazione locale conclusa (di cui 2 con aggiornamento console necessario), 0 attive, 22 richieste di intervento e 7 bloccate. Questi sono conteggi delle installazioni gestite dalla pipeline, non la dimensione dell'intera libreria.

ID gioco, hash candidato e hash archivio/membro evitano di contare la stessa copia più volte. Operazioni di job diversi rimangono tentativi distinti anche quando riusano la stessa cache. Titoli simili non bastano per unire copie sconosciute; membri omonimi in cartelle differenti restano distinti. I contenitori preparati, documenti e BIOS non vengono contati come giochi installati.

## Test eseguiti

| Verifica | Esito |
| --- | --- |
| Suite backend completa | **294 superati**, nessun fallimento |
| Suite finale del modello di esperienza, incluse 5 regressioni successive | **37 superati**; totale **299 casi backend distinti** verificati |
| Ruff backend, test e migrazioni | Superato |
| mypy backend | Superato, 47 moduli |
| Frontend Vitest | **14 superati** |
| ESLint, TypeScript e build produzione | Superati |
| Browser Playwright completo | **10 superati** |

Totale: **323 casi distinti superati**, nessun fallimento residuo. I browser test verificano preparazione e installazione automatica da ZIP/RAR, completamento senza prova d'avvio, duplicati, sezioni, schede compatte/espandibili, azioni contestuali, aggiornamento automatico, tastiera, persistenza del job dopo refresh e viewport mobile. I test backend coprono fasi intermedie, errori strutturali/temporanei, dipendenze, rapporti parziali prima del fallimento XML, conferma di visibilità distinta dai metadati, deduplica, job multipli, progresso misurabile/indeterminato, filtri e paginazione, compatibilità dei record precedenti e rigenerazione limitata dei piani.

## Conservazione dei dati

| Verifica prima/dopo | Risultato |
| --- | --- |
| Giochi nel database PC | **105**, invariati |
| Voci gioco nei gamelist remoti | **104**, invariati; distinto dal conteggio dei gruppi di file presenti |
| File remoti confrontati per percorso, dimensione e SHA-256 | **279**, tutti invariati |
| Salvataggi | **6**, tutti invariati, incluso Hercules |
| Gamelist validi confrontati | **12**, tutti invariati |
| Core PS1, BIOS, configurazione e Grandi Classici | Hash invariati |
| Stati tecnici, game ID e sync run ID dei job esistenti | Invariati |
| Nuovi giochi / trasferimenti richiesti | **0 / 0** |

EmulationStation risultava già chiusa prima e dopo il collaudo: non è stata interrotta o riavviata via SSH. Nessun riavvio del Raspberry. Il backend locale è stato aggiornato soltanto dopo aver verificato l'assenza di installazioni e sincronizzazioni attive. Backup del database eseguito prima delle modifiche. La sola annotazione utente aggiunta è la segnalazione effettiva di Hercules; il nuovo dry-run è conservato senza autorizzazione di esecuzione.

Una prima raccolta finale degli hash ha superato il timeout mentre erano in corso altre letture; è stata ripetuta in sequenza con un timeout adeguato, completando il confronto. Nessuna protezione della pipeline è stata rimossa. Inventari, risposte API, log, backup e screenshot rimangono in `.runtime/increment7-3`, ignorata da Git. ROM, BIOS, credenziali e file runtime non sono pubblicati.

Guida: [INSTALLATION-EXPERIENCE.md](INSTALLATION-EXPERIENCE.md). Architettura: [ARCHITECTURE.md](ARCHITECTURE.md).
