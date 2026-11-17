# Guida ai provider

## Estensione verificata nell'Incremento 4

Il provider `curated-homebrew` aggiunge **due file specifici**, verificati il 17 novembre 2026. Il refresh live è riuscito: legge inventari e prove di licenza senza scaricare i giochi. Insieme alle tre fonti precedenti Discovery contiene 1.193 voci, **51 idonee** all'acquisizione autorizzata. La disponibilità finale si ricontrolla al download. L'Incremento 4 non ha avviato nuovi download di ROM.

| Titolo | Piattaforma / formato | Autore | Prova dei diritti |
| --- | --- | --- | --- |
| Miniplanets REMIX REV04 | Mega Drive / BIN | Javier Degirolmo (Sik) | [Progetto originale](https://github.com/sikthehedgehog/miniplanets), LICENSE.txt Zlib del commit fissato nell'adapter, verificata per hash. |
| Horizontal Shooter | SNES / SFC | Marcus Rowe (UnDisbeliever) | [Progetto originale](https://github.com/undisbeliever/horizontal-shooter), MIT per codice e CC0 per asset; [dichiarazione per il file distribuito](https://github.com/retrobrews/snes-games/blob/master/horizontal-shooter.txt). |

Ogni voce registra URL originale, autore, licenze separate, revisione immutabile, URL/dimensione/hash Git del file, dichiarazione e data di verifica. La cache della dichiarazione è ricontrollata al riuso. Non si estende l'autorizzazione agli altri file di retrobrews o di raccolte simili.

La ricerca Neo Geo/arcade ha incluso [ngdevkit-examples](https://github.com/dciabrin/ngdevkit-examples): codice/esempi con licenze dichiarate, ma nessuna release binaria verificata per acquisizione automatica in questo incremento. Rimane un collegamento originale. [MAME legal ROM downloads](https://www.mamedev.org/roms/) prevede condizioni specifiche e accettazione sulle pagine originali: l'app fornisce il collegamento, senza aggirare il flusso o automatizzare l'archivio. Nessun provider BIOS.

NES/GB/GBC/GBA continuano a usare le tre fonti descritte sotto. Fonti senza diritti/release verificabili non sono conteggiate come download disponibili. La selezione massiva per fonte/piattaforma/licenza usa l'anteprima con conferma. **Esporta report dei file acquisiti** aggiunge un riepilogo JSON nel Download Manager.

## Fonti operative

La verifica live del 17 novembre 2026 ha letto gli inventari GitHub e tutti i metadati dei tre database. I conteggi comprendono le voci di tipo `game` e `homebrew`. Strumenti, musica, demo e hack ROM vengono esclusi.

| Provider | Piattaforme | Giochi individuati | Idonei all'acquisizione automatica |
| --- | --- | --- | --- |
| GBDev / Homebrew Hub | Game Boy, Game Boy Color | 925 | 34 |
| GBADev / Homebrew Hub | Game Boy Advance | 243 | 10 |
| NESDev / Homebrew Hub | NES | 23 | 5 |
| Totale | | 1.191 | 49 |

I tre cataloghi sono mantenuti dalle rispettive comunità. L'elenco dei database e i repository originali sono pubblici. [Database Homebrew Hub](https://github.com/gbdev/homebrewhub/blob/main/DATABASES.md), [GBDev](https://github.com/gbdev/database), [GBADev](https://github.com/gbadev-org/games), [NESDev](https://github.com/nesdev-org/homebrew-db).

L'idoneità viene determinata dai metadati verificati, dalla presenza del file nell'inventario, dal formato e dalle condizioni dichiarate per la singola voce. Il collaudo end-to-end su rete reale ha acquisito un solo gioco, **2048gb**, da 32.768 byte, con licenza Zlib. È stata inoltre verificata l'acquisizione della copertina autorizzata di **Bit Bang**. La disponibilità effettiva di ogni altro file viene verificata quando parte il relativo trasferimento. I conteggi possono cambiare al successivo aggiornamento. [Licenza originale di 2048gb](https://github.com/Sanqui/2048-gb/blob/master/LICENSE).

## Aggiornamento del catalogo

In **Game Discovery**, aprire **Stato dei provider** e aggiornare ciascuna fonte. L'adapter usa l'API GitHub Git Trees e scarica soltanto i file `entries/*/game.json` tramite URL immutabili riferiti alla revisione dell'albero. Le dimensioni e gli identificatori dei file provengono dall'inventario GitHub. La cache dei metadati è indicizzata per hash del blob. Un errore di rete mantiene il catalogo precedente e viene mostrato nello stato del provider.

Le richieste usano un User-Agent identificabile, una pausa minima di 250 ms per host, il maggiore eventuale crawl-delay e la verifica di robots.txt. Un divieto o regole non verificabili fermano l'accesso. Redirect, credenziali URL, destinazioni private e proxy ambientali vengono esclusi. L'API GitHub viene usata senza token e può applicare limiti per indirizzo IP. Riprovare l'aggiornamento dopo il ripristino della quota in caso di risposta 403/429. [API Git Trees](https://docs.github.com/en/rest/git/trees), [limiti REST GitHub](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api).

## Autorizzazioni e condizioni

La licenza GPL del database riguarda il progetto del database. Ogni gioco e i suoi asset hanno condizioni proprie. L'adapter valuta `gameLicense` o il campo precedente `license`, oltre a `assetsLicense`/`assetLicense` quando presente. Conserva la dichiarazione JSON originale, l'URL immutabile, la revisione e la data di verifica. Il file `authorization.json` accompagna ogni acquisizione nella cartella dati. Il manifest di esportazione conserva licenza, autore e provenienza. [Licenze del database GBDev](https://github.com/gbdev/database#license), [schema delle voci](https://github.com/gbdev/database/blob/master/schemas/game-schema-d5.json).

Il codice applica un elenco esplicito di licenze riconosciute, consultabile in `backend/discovery_sources.py`. Comprende MIT, Zlib, ISC, BSD, Apache, Unlicense, CC0, GPL e le varianti Creative Commons elencate. I vincoli di attribuzione, condivisione allo stesso modo, uso non commerciale o assenza di opere derivate rimangono applicabili secondo la licenza selezionata. L'esportazione prepara copie per uso personale. Eventuali ulteriori distribuzioni richiedono il rispetto delle condizioni della fonte.

I flag `disable-downloads`, i titoli indicati come commerciali, le licenze sconosciute, gli asset con condizioni incompatibili e le scelte ambigue tra più file impediscono l'acquisizione automatica. La voce resta consultabile con il motivo. Per le copertine è richiesta una licenza degli asset esplicita e riconosciuta. Le immagini vengono verificate, limitate a 8 MB e 20 milioni di pixel, convertite in PNG e conservate in cache locale.

## Fonti con collegamento originale

**itch.io** è disponibile come collegamento al sito. La documentazione delle API richiede credenziali e scopes, mentre robots.txt esclude `/game/download/` e `/bundle/download/`. Questo incremento presenta la pagina originale, dove l'utente può seguire le condizioni del creatore. [API itch.io](https://itch.io/docs/api/serverside), [robots.txt](https://itch.io/robots.txt).

**PDRoms** è disponibile come collegamento originale. Durante l'integrazione la verifica TLS di robots.txt ha segnalato un certificato scaduto e l'autorizzazione all'automazione non è stata accertata. L'app mantiene i controlli TLS. [PDRoms](https://pdroms.de/), [robots.txt della fonte](https://pdroms.de/robots.txt).

L'API del sito Homebrew Hub su hh3.gbdev.io ha restituito HTTP 403 durante la verifica. L'integrazione operativa usa direttamente i repository GitHub pubblici documentati come sorgenti dei database. [Documentazione Homebrew Hub](https://github.com/gbdev/homebrewhub/blob/main/README.md).

## Provider a manifest

**Sorgenti e download** continua ad accettare il formato dell'Incremento 1, documentato nel README. Il manifest deve provenire da una fonte autorizzata e riportare URL HTTPS diretto, licenza, riferimento dei diritti, dimensione e SHA-256. `redistribution_allowed: true` è una dichiarazione esplicita dell'operatore, che deve aver verificato i diritti. Il semplice accesso pubblico al file non costituisce tale dichiarazione.

Le voci vengono importate anche in Discovery. Sono supportati i formati singoli riconosciuti e ZIP/7Z per Arcade, Neo Geo, fba e mame-libretro. Il controllo dell'archivio all'acquisizione non sostituisce la successiva validazione DAT prima dell'export/sync. CUE isolati richiedono l'importazione locale dei file collegati. SNES e Mega Drive hanno i due titoli preconfigurati sopra; ulteriori titoli richiedono manifest esplicitamente verificati dall'operatore.

## Metadati

Titolo, autore, data, genere e descrizione derivano dai campi dichiarati. I dati mancanti rimangono sconosciuti. Gli identificatori esterni e gli hash collegano le acquisizioni al catalogo locale. L'arricchimento massivo usa corrispondenze esatte e segnala più voci con lo stesso hash come ambigue. Le correzioni manuali del catalogo vengono conservate.
