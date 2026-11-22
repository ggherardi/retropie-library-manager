# Verifica Neo Geo — stato parziale del 22 novembre 2026

**I due archivi indicati come MAME 0.251 (new) e MAME 0.111 (old) non sono ancora stati individuati.** La scansione è stata limitata alle radici di importazione configurate nell'app, senza estenderla a file personali. Download non è tra le radici autorizzate. Sono stati richiesti i due percorsi esatti; non è possibile attribuire contenuti o compatibilità a quei due archivi prima di leggerli.

## Configurazione effettiva e controllo in sola lettura

Il Raspberry 192.168.0.13 risponde con il core **FinalBurn Neo v1.0.0.03 af50579**, SHA-256 del binario `37dc6340f459a5f50d30c5ab9bcf5974926de4245a5ead2d07046868ade57643`. Il sistema neogeo usa `lr-fbneo` come default. Nessun `neogeo.zip` è stato trovato nell'inventario dei percorsi BIOS, BIOS/fbneo e ROM/neogeo controllati dal probe esistente. Questi controlli non hanno installato né scritto file sul Raspberry, non hanno avviato emulatori e non hanno modificato ROM, salvataggi o configurazioni.

DAT attivo: revisione `af50579270a610eda8ac580648d9c12acc7bb565`, SHA-256 `85f9a7988545ea22de01d1d2814df5d8a19b1153ebbbb385df6fe5471c3e016e`. L'entry neogeo contiene 38 componenti con CRC32 e dimensioni; **non contiene SHA-1**. Gli SHA-1 dei file possono essere calcolati, ma non confrontati con un valore che il DAT non fornisce.

## Sei archivi di gioco già autorizzati

Sono stati riletti e ricalcolati i contenuti, senza modificare gli originali. I componenti di gioco corrispondono al DAT, mentre ciascun archivio contiene solo 26 dei 38 componenti BIOS dell'entry attiva. L'app non li ha importati come giochi installabili: rimangono candidati in attesa di decisione.

| Set | Componenti gioco verificati | Componenti BIOS incorporati validi | Simulazione locale |
|---|---:|---:|---|
| `mslug5` | 13 / 13 | 26 / 38 | Bloccata dalla validazione BIOS |
| `wjammers` | 11 / 11 | 26 / 38 | Bloccata dalla validazione BIOS |
| `magdrop3` | 9 / 9 | 26 / 38 | Bloccata dalla validazione BIOS |
| `pbobblen` | 13 / 13 | 26 / 38 | Bloccata dalla validazione BIOS |
| `turfmast` | 9 / 9 | 26 / 38 | Bloccata dalla validazione BIOS |
| `kf2k2mp2` | 14 / 14 | 26 / 38 | Bloccata dalla validazione BIOS |

Per tutti e sei è stata eseguita nuovamente la validazione esistente nelle modalità non-merged e full-non-merged. La modalità non-merged richiede un BIOS condiviso completo esterno; full-non-merged richiede tutti i componenti incorporati e segnala i 12 mancanti sotto. La simulazione si ferma a questo preflight: **non è stato generato né confermato un piano di trasferimento SFTP installabile**. `kf2k2mp2` è un clone di `kof2002`; nella copia non-merged esaminata i suoi 14 componenti di gioco sono presenti, e la dipendenza BIOS neogeo viene risolta anche attraverso il parent. Nessun trasferimento e nessuna prova di avvio sono avvenuti.

## I dodici componenti da confrontare

La colonna “Copie di gioco” riguarda soltanto i sei ZIP già autorizzati; le ultime due colonne non sono risultati negativi, ma verifiche ancora impossibili senza i percorsi dei nuovi archivi.

| Componente | Byte attesi | CRC32 atteso | Copie di gioco | MAME 0.251 new | MAME 0.111 old |
|---|---:|---|---|---|---|
| `sp-s3.sp1` | 131,072 | `91b64be3` | Mancante | Da analizzare | Da analizzare |
| `sp1-u2` | 131,072 | `62f021f4` | Mancante | Da analizzare | Da analizzare |
| `sp1-u4.bin` | 131,072 | `1179a30f` | Mancante | Da analizzare | Da analizzare |
| `sp1-u3.bin` | 131,072 | `2025b7a2` | Mancante | Da analizzare | Da analizzare |
| `sp-j3.sp1` | 524,288 | `486cb450` | Mancante | Da analizzare | Da analizzare |
| `sp1-j3.bin` | 131,072 | `fbc6d469` | Mancante | Da analizzare | Da analizzare |
| `neo-po.bin` | 131,072 | `16d0c132` | Mancante | Da analizzare | Da analizzare |
| `neo-epo.bin` | 131,072 | `d27a71f1` | Mancante | Da analizzare | Da analizzare |
| `neodebug.bin` | 131,072 | `698ebb7d` | Mancante | Da analizzare | Da analizzare |
| `uni-bios_4_0.rom` | 131,072 | `a7aab458` | Mancante | Da analizzare | Da analizzare |
| `uni-bios_3_3.rom` | 131,072 | `24858466` | Mancante | Da analizzare | Da analizzare |
| `neopen.sp1` | 131,072 | `cb915e76` | Mancante | Da analizzare | Da analizzare |

Non è stato preparato un nuovo neogeo.zip: la disponibilità di tutti i componenti e i diritti per trasferirli non sono ancora dimostrati.

## Completezza DAT e BIOS necessari al core

Il [driver Neo Geo della revisione installata](https://github.com/libretro/FBNeo/blob/af50579270a610eda8ac580648d9c12acc7bb565/src/burn/drv/neogeo/d_neogeo.cpp#L938) distingue:

- BIOS 68000 selezionabili: il default `sp-s3.sp1` (91b64be3) e alternative MVS regionali, AES, development, Universe BIOS e NeoOpen. Le alternative sono marcate BRF_SELECT e BRF_OPT; non costituiscono trentacinque BIOS da eseguire contemporaneamente.
- Componenti comuni: `sm1.sm1` (94416d67), `sfix.sfix` (c2ea0cfd), `000-lo.lo` (5a86cff2), tutti da 131072 byte. Sono presenti e corrispondono nelle sei copie esaminate. Il percorso effettivo di caricamento dipende anche dal modello/BIOS selezionato.
- Universe BIOS 4.0 e 3.3 sono alternative riconosciute dal driver, rispettivamente CRC a7aab458 e 24858466. I commenti “free” nel sorgente non dimostrano da soli l'autorizzazione a redistribuire firmware SNK o interi archivi BIOS.

La [selezione libretro](https://github.com/libretro/FBNeo/blob/af50579270a610eda8ac580648d9c12acc7bb565/src/burner/libretro/retro_common.cpp#L547), il [caricamento del BIOS scelto](https://github.com/libretro/FBNeo/blob/af50579270a610eda8ac580648d9c12acc7bb565/src/burn/drv/neogeo/neo_run.cpp#L435) e la [verifica dei file opzionali nel frontend del core](https://github.com/libretro/FBNeo/blob/af50579270a610eda8ac580648d9c12acc7bb565/src/burner/libretro/libretro.cpp#L909) confermano che la completezza dell'intera entry DAT è più ampia del sottoinsieme usato da una configurazione di avvio. Non basta tuttavia un qualsiasi file UniBIOS per provare la configurazione e i diritti di tutti i giochi.

Il validatore dell'app usa gli attributi del DAT attivo, che in questa entry non distinguono le alternative opzionali del driver: richiede quindi tutti i 38 componenti. **Non sono stati allentati controlli, ignorati hash o cambiati profili del core.** Un eventuale profilo minimo di avvio richiederebbe evidenza sulla selezione effettiva, regressioni dedicate e un rapporto distinto dalla completezza DAT. Non è stato introdotto durante questa verifica incompleta.

## Prossimo passo indispensabile

Leggere i due archivi ai percorsi che l'utente deve indicare, calcolare inventario CRC32/SHA-1/dimensioni e struttura anche annidata, confrontare tutti i componenti con il DAT e verificare i diritti di utilizzo/trasferimento. La pubblicazione su Internet Archive e l'etichetta della versione MAME non costituiscono da sole prova di autorizzazione o compatibilità.

**Possiamo installare i sei giochi Neo Geo con questi BIOS? Non è ancora possibile confermarlo.** Nelle copie attualmente esaminate mancano i 12 componenti elencati; i due nuovi BIOS restano da analizzare. Prima di ogni trasferimento BIOS serve comunque la conferma esplicita dell'utente. Fino a quel momento non viene installato o trasferito alcun BIOS.
