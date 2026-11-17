# Catalogazione massiva

## Conteggi e identità

Un record DAT descrive un set, non un file posseduto e non un'autorizzazione al download. `catalog_records` include giochi, BIOS e dispositivi; `catalog_games` esclude BIOS/dispositivi. `unique_families` conta parent/famiglie distinti **per fonte**, mentre `clones` conta le varianti. Fonti differenti possono descrivere lo stesso titolo: non sommare le famiglie dichiarandole giochi globalmente unici. Il collegamento tra fonti richiederà evidenze specifiche, non titoli simili.

`local_files` è il numero di elementi registrati nella libreria, inclusi eventuali set/BIOS importati. `present_files` verifica l'esistenza dei percorsi fisici distinti, incluse le tracce dei gruppi PS1; `missing_files` segnala percorsi registrati non più presenti. Esistenza e integrità sono controlli differenti: l'hash viene riletto durante validazione/export/sync. I download autorizzati sono le voci Discovery attualmente disponibili e idonee, non un conteggio di ROM commerciali scaricabili.

I set validati hanno un rapporto completo riferito a SHA del file e del DAT attivo. Un aggiornamento del DAT invalida il risultato ai fini del trasferimento; ripetere la verifica. I test riusciti richiedono un dispositivo e un resoconto dell'operatore, con hash del gioco; non derivano da un DAT o da un download riuscito.

## Importare un catalogo

1. In Impostazioni aggiungere una cartella autorizzata. Inserirvi il manifest, oppure usare `data/catalogs`.
2. In Cataloghi DAT assegnare ID e nome, percorso, formato, piattaforma e, se conosciuti, core/versione/origine/revisione.
3. Avviare l'importazione. Attività mostra record elaborati, fase, errori e annullamento. I report JSON conservano aggiunte, modifiche, record invariati, duplicati e tempi.
4. Per un aggiornamento usare lo stesso ID. Un file identico con la stessa configurazione viene saltato; i dati nuovi sono preparati separatamente e pubblicati con un unico cambio di versione attiva.

Un errore, conflitto tra due record omonimi, parent ciclico o annullamento prima della pubblicazione conserva il catalogo precedente. All'avvio i lavori interrotti sono marcati falliti e lo staging non attivo viene rimosso. Ripetere esplicitamente l'importazione. L'annullamento dopo il punto atomico di pubblicazione non annulla un aggiornamento già completato.

Limiti: 512 MiB per manifest, 500.000 record per fonte, blocchi di 250 inserimenti, 10.000 componenti per set, pagina API massima di 100 record (UI 36). FTS5 usa termini indicizzati parametrizzati e prefissi; le liste non caricano tutti i componenti. La vista dettaglio carica il solo record richiesto e fino a 500 varianti della famiglia. L'associazione manuale rapida presenta i primi 100 archivi; la verifica massiva per nome tecnico supporta fino a 20.000 ID selezionati via API.

## Formati

- **XML MAME / ClrMamePro XML:** `game` o `machine` con name, cloneof, romof, isbios/isdevice; description, year, manufacturer, rom/disk, input, display/video, driver, device_ref. I vecchi record MAME `runnable="no"` sono risorse BIOS. Entità XML e riferimenti esterni sono disabilitati; la dichiarazione DTD interna priva di entità viene tollerata.
- **DAT ClrMamePro testuale:** `clrmamepro (...)`, `game (...)`, `machine (...)`, `resource (...)`, componenti `rom (...)` e `disk (...)`, campi parent/clone e hash. I dischi CHD descritti nel DAT sono segnalati come non validabili dall'attuale verificatore arcade ZIP/7z.
- **JSON:** array di oggetti, letto in streaming. **CSV UTF-8:** prima riga con nomi campi; `components` come array JSON nella cella, `dependencies` separate da `|`.

Campi JSON/CSV: `name` obbligatorio e stabile, `title` o `description`, `platform`, `system`, `manufacturer`, `year`, `genre`, `players`, `orientation`, `controls`, `parent`/`cloneof`, `romof`, `kind` (`game`, `bios`, `device`), `components`, `dependencies`, `synopsis`. Esempio di soli metadati sintetici:

```json
[
  {"name":"demo-parent","title":"Demo originale","platform":"arcade","system":"CPS-1","players":2,"components":[]},
  {"name":"demo-clone","title":"Demo variante","parent":"demo-parent","platform":"arcade","components":[]}
]
```

Un componente richiede `name`, `size` e almeno un hash `crc`, `sha1`, `sha256` o `md5`. Può dichiarare `merge`, `optional`, `status`, `bios`. L'esempio senza componenti è consultabile ma non validabile per l'esportazione.

## Cataloghi ufficiali

MAME 2003 usa il DAT [MAME 0.78 mantenuto da libretro](https://github.com/libretro/mame2003-libretro/blob/master/metadata/mame2003.xml). Il pulsante FBNeo installato legge la versione reale del core, risolve la revisione Git e acquisisce il DAT di **quella revisione** da [FBNeo](https://github.com/libretro/FBNeo/tree/master/dats). La variante FBNeo attuale serve all'esplorazione e non viene dichiarata compatibile con un core diverso.

Per CPS-1/2/3 e Neo Geo, i nomi tecnici e i metadati disponibili sono letti anche dalle strutture BurnDriver dei quattro driver originali della stessa revisione. Nome tecnico esatto, sistema, giocatori e genere sono applicati soltanto ai record corrispondenti. File DAT e sorgenti dei metadati sono memorizzati per hash Git; la cache viene verificata anche al riuso. Nessun codice remoto viene eseguito e nessuna ROM viene acquisita da questo flusso.

## Raccolte e arricchimento

Le viste permettono piattaforma, sistema arcade, genere, multiplayer, preferiti, test riusciti, dipendenze mancanti, file posseduti, varianti preferite e non sincronizzati. La sincronizzazione registrata descrive l'ultima copia verificata con lo stesso hash, non una scansione continua della scheda SD. La cronologia conclusa dell'Incremento 3 viene recuperata solo quando gli hash dei file coincidono.

L'anteprima dei metadati arcade richiede un'associazione DAT validata, attiva e univoca. Applicare ripete i controlli e preserva modifiche concorrenti e campi già valorizzati. Un titolo ancora uguale al nome del file può diventare quello leggibile del DAT. Discovery mantiene il matching per contenuto dell'Incremento 2. Copertine e correzioni manuali restano nel Catalogo; screenshot autorizzati si registrano nel dettaglio di File e raccolte. Nessuna immagine viene scelta sulla sola somiglianza del titolo.
