# Grandi Classici, raccolte e media

## Tre viste della libreria

**Grandi Classici** contiene solo file locali esistenti, riconosciuti con identificatori affidabili oppure inclusi esplicitamente dall'utente. Sono disponibili ricerca, filtri piattaforma/genere, preferiti e ordine manuale. Rimuovere un gioco dalla raccolta non cancella il gioco e non lo nasconde nella Collezione Completa.

**Collezione Completa** conserva anche homebrew e file temporaneamente non disponibili. I filtri distinguono presenza del file, completezza del set, sincronizzazione e test riferiti dall'operatore. Un set validato o trasferito non equivale a un gioco provato sul Raspberry.

**Da Recuperare** presenta i classici senza una copia locale identificata. I 914 record iniziali sono metadati, non download di ROM. I campi sconosciuti restano vuoti; i riferimenti ai DAT non concedono diritti sui giochi. Da questa vista si apre il normale flusso di importazione con anteprima, verifica e deduplica. Una copia non ancora identificata può restare in Collezione Completa mentre il corrispondente classico appare ancora da recuperare.

## Catalogo e identificazione

La selezione editoriale è esplicita in `backend/classics_selection.py`; il risultato versionato è `backend/resources/essential_classics.json`. Non è una classifica e non contiene voti. Ogni voce conserva motivazione, piattaforma, identificatori e riferimenti alle revisioni delle fonti; anno, genere, sviluppatore e publisher sono presenti solo quando disponibili. Le versioni per piattaforme diverse sono voci distinte; varianti regionali dello stesso titolo condividono la voce.

Fonti utilizzate:

- [Libretro Database](https://github.com/libretro/libretro-database/tree/969e31a324119a17add184e8b716315a74adb51b): DAT No-Intro, metadati e seriali PlayStation. Ogni record conserva revisione e hash della fonte.
- DAT e driver ufficiali MAME 0.78 e FBNeo, già acquisiti dal modulo [Arcade Intelligence](ARCADE.md), alle revisioni registrate nei record.

**Riconosci classici** confronta piattaforma e SHA-1 del contenuto per le cartucce singole, verificando prima lo SHA-256 locale. Per arcade richiede una validazione completa e corrente, riferita al DAT attivo, al suo hash e all'archivio presente. Nessuna corrispondenza deriva dalla somiglianza del titolo. Ambiguità e set di dischi PS1 richiedono revisione; è disponibile un'associazione manuale esplicita nel dettaglio. Un cambiamento dell'hash rende obsoleta l'identità precedente.

La presenza nel catalogo non certifica il core, il BIOS, le prestazioni o la licenza della copia posseduta. Restano attivi i blocchi per set arcade incompleti e dipendenze mancanti.

## Qualità e immagini

La pagina **Qualità e media** misura la completezza di titolo, genere, anno, sviluppatore, publisher, descrizione e immagini. Completezza e correttezza sono distinte: una verifica manuale richiede una nota con la fonte e diventa da revisionare quando cambiano i metadati.

1. Aggiornare le fonti in Game Discovery e scegliere **Trova media autorizzati**.
2. Esaminare anteprime, tipo di immagine, fonte, licenza e corrispondenza con la ROM. Sono proposte solo identità esatte; la prima proposta per tipo è selezionata, ma può essere cambiata.
3. Confermare le associazioni. Lo stesso piano applicato due volte non scarica nuovamente gli asset. Un cambiamento della ROM, della fonte o dell'immagine locale richiede una nuova anteprima.
4. Nel dettaglio è possibile assegnare un'immagine locale da una cartella autorizzata, confermando identità e diritti e indicando fonte e licenza. La cronologia conserva le assegnazioni precedenti.

I provider GBDev, GBADev e NESDev distinguono la licenza degli asset dalla licenza del software. Il manifest `reviewed_media.json` integra singole immagini homebrew già revisionate: lega SHA-256 del gioco, URL immutabile, hash Git del media e dichiarazione dei diritti. Le eccezioni di licenza per le immagini non estendono le autorizzazioni al download delle ROM.

La cache conserva prove e SHA-256 in `data/media`, fuori da Git. HTTPS pubblico, robots.txt, dimensioni, hash Git e decodifica con limiti sono verificati prima della conversione PNG. Nessuna ricerca per titolo approssimativo o scraping generico. Dove mancano diritti verificabili, restano un placeholder grafico e i dati sconosciuti.

Copertina e screenshot sono ruoli separati. Le vecchie copertine homebrew comprendono anche anteprime di gameplay: assegnare quella stessa immagine al ruolo screenshot non crea una nuova illustrazione. Nel collaudo 27 delle 30 associazioni screenshot riutilizzano immagini già note; tre provengono dai provider aggiornati.

## Collezione sulla console

Il pulsante di sincronizzazione delle raccolte seleziona i giochi disponibili e attiva metadati, immagini e raccolta; il dry-run resta obbligatorio. La raccolta richiede tutti i suoi membri nel piano, per evitare aggiornamenti parziali. Il piano viene invalidato se cambia la selezione o l'impronta dei metadati.

Il formato è stato confrontato con [CollectionSystemManager.cpp](https://github.com/RetroPie/EmulationStation/blob/d9efd746a983a382d9fe031b5336317455dd0d4d/es-app/src/CollectionSystemManager.cpp) e verificato nel binario installato. In `~/.emulationstation/collections/custom-Grandi Classici.cfg` viene registrato un percorso assoluto di avvio per riga. L'impostazione `CollectionSystemsCustom` abilita la raccolta. Con `UseCustomCollectionsSystem=true`, già presente sul dispositivo, la raccolta si trova nel sistema delle raccolte personalizzate.

`es_settings.cfg` di RetroPie è un **frammento XML con elementi fratelli, senza radice unica**, come mostra [Settings.cpp](https://github.com/RetroPie/EmulationStation/blob/master/es-core/src/Settings.cpp). Il parser sicuro usa una radice temporanea solo in memoria e salva il formato originale, mantenendo gli altri valori, commenti e mappe. Versioni non riconosciute lasciano la raccolta disponibile solo in Windows.

Le normali sezioni per console rimangono accessibili. Le ROM non vengono rinominate; rimane la correzione 5.1 dei titoli leggibili dei gruppi RLM. I gamelist conservano percorsi, campi non gestiti e statistiche. Gli screenshot usano `image`, le copertine separate `thumbnail`, secondo [GAMELISTS.md](https://github.com/RetroPie/EmulationStation/blob/master/GAMELISTS.md).

Se EmulationStation è attiva, il trasferimento delle impostazioni, della raccolta e dei gamelist viene rinviato. Chiuderla dalla console locale, rigenerare il dry-run e confermare. Backup, verifica degli originali, SHA-256 e rinomina atomica precedono la pubblicazione. File remoti differenti sono bloccati; riferimenti esterni aggiunti manualmente alla raccolta sono conservati. Non vengono eliminati ROM o salvataggi. Ripetere la sincronizzazione salta i file identici. Riavviare EmulationStation solo dalla console locale.

## Televisore 16:9

Sul dispositivo è installato **Carbon 2021**, con `resolution` 1920×1080, elenco a 32 unità, metadati a 24 e vista dettagliata con immagine e descrizione. Manteniamo titoli originali e descrizioni esistenti senza troncamenti o identificativi aggiunti. La raccolta eredita il tema e l'ordinamento della console; l'ordine manuale Windows non forza le preferenze di ordinamento di EmulationStation.

Valutazione delle alternative, senza installazione:

| Tema | Valutazione |
|---|---|
| Carbon 2021, già installato | Layout 16:9 verificato sul file effettivo, immagine grande nella vista dettagliata, supporto metadati e raccolte. È la scelta conservata. |
| [Carbon](https://github.com/RetroPie/es-theme-carbon) | Tema RetroPie ufficiale con viste basic/detailed e dimensioni relative. Alternativa per una presentazione più tradizionale; dimensione dei testi e distanza dal TV richiedono una prova visiva locale. |

Entrambi sono elencati nel [gestore ufficiale dei temi](https://github.com/RetroPie/RetroPie-Setup/blob/master/scriptmodules/supplementary/esthemes.sh). Non sono stati modificati tema, risoluzione, overscan, emulatori, kernel o firmware. L'app verifica i dati; la leggibilità dal divano resta una valutazione dell'utente sul proprio televisore.

Carbon 2021 non include SVG specifici per il nome “Grandi Classici”: il log segnala logo/controller mancanti e la raccolta usa il titolo testuale. Il collaudo locale ha confermato raccolta e nomi visibili. Eventuali immagini dedicate al tema richiedono un intervento separato, senza confonderle con le copertine dei giochi.
