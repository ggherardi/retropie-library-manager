# Verifica dei due BIOS Neo Geo — 23 novembre 2026

## Esito

**Il nuovo `neogeo.zip` è il candidato tecnicamente adatto a una configurazione MVS standard del core installato, ma non supera la validazione automatica attuale dell'intero DAT: 34 componenti corretti su 38.** Mancano quattro BIOS alternativi/opzionali. Il vecchio ZIP non è adatto a questo DAT: tre componenti non corrispondono e il quarto è un BIOS MVS con un nome differente. Gli archivi originali non sono stati modificati, rinominati, estratti permanentemente o trasferiti.

Il controllo verifica contenuti e compatibilità prevista, **non costituisce una prova di avvio** e non dimostra da solo i diritti di utilizzo/trasferimento.

## Archivi individuati nella cartella indicata dall'utente

| Archivio | Dimensione ZIP | Membri | Corrispondenze del contenuto nel DAT | SHA-256 ZIP |
|---|---:|---:|---|---|
| `Desktop/bios/neogeo.zip` (indicato come MAME 0.251 new) | 1858095 | 34 | 34 / 38, nomi corretti | `e86ab6faaaa490175d3f7edfd56f258ce26f24e625ba3d99cf0eb0f12e78f2c0` |
| `Desktop/bios/neogeo old.zip` (indicato come MAME 0.111 old) | 55722 | 4 | 1 / 38 per hash, **0 / 38 per nome e hash** | `87174122434511980eca227fd488b1c133b268d2cee1bb00eed4ff8def90b9f5` |

Entrambi sono ZIP validi, con file direttamente nella radice e **nessun archivio annidato**. I membri sono stati letti in memoria con limiti di numero, profondità e byte; il CRC interno ZIP è stato verificato durante la lettura. Nessuna esecuzione di contenuti. SHA-256 degli originali ricontrollati dopo le simulazioni: invariati. Le etichette MAME sono quelle indicate dall'utente, non una prova di compatibilità FBNeo o di autorizzazione alla distribuzione.

Il nuovo ZIP contiene BIOS SNK MVS regionali e Deck, i tre componenti comuni e quindici varianti Universe BIOS, comprese **4.0 e 3.3**. Il vecchio non contiene alcun UniBIOS: `aes-bios.bin` ha in realtà il CRC e la dimensione di `sp-s2.sp1`, BIOS **MVS Asia/Europe ver. 5**, non di un BIOS AES. Non è stato rinominato.

## Core e DAT effettivamente verificati

Raspberry Pi 3 B+, RetroPie 4.8, core `lr-fbneo` predefinito per neogeo: **v1.0.0.03 af50579**, SHA-256 `37dc6340f459a5f50d30c5ab9bcf5974926de4245a5ead2d07046868ade57643`. Verifica SSH ripetuta il 23 novembre, in sola lettura, senza inizializzare il core né avviare giochi. Il probe non trova neogeo.zip in BIOS, BIOS/fbneo o ROM/neogeo; nessun BIOS è stato installato.

DAT attivo alla revisione `af50579270a610eda8ac580648d9c12acc7bb565`, SHA-256 `85f9a7988545ea22de01d1d2814df5d8a19b1153ebbbb385df6fe5471c3e016e`, identico a quello collegato al core. L'entry neogeo elenca 38 componenti con CRC32 e dimensione. **Il DAT non fornisce SHA-1:** quelli sotto sono calcolati per identificare i file e non vengono presentati come confrontati con un valore atteso inesistente.

## I dodici componenti precedentemente mancanti

| Componente | Byte attesi | CRC32 atteso | ZIP nuovo | ZIP vecchio |
|---|---:|---|---|---|
| `sp-s3.sp1` | 131072 | `91b64be3` | Corretto | Mancante |
| `sp1-u2` | 131072 | `62f021f4` | Corretto | Mancante |
| `sp1-u4.bin` | 131072 | `1179a30f` | Corretto | Mancante |
| `sp1-u3.bin` | 131072 | `2025b7a2` | Corretto | Mancante |
| `sp-j3.sp1` | 524288 | `486cb450` | Corretto | Mancante |
| `sp1-j3.bin` | 131072 | `fbc6d469` | Corretto | Mancante |
| `neo-po.bin` | 131072 | `16d0c132` | **Mancante** | Mancante |
| `neo-epo.bin` | 131072 | `d27a71f1` | **Mancante** | Mancante |
| `neodebug.bin` | 131072 | `698ebb7d` | **Mancante** | Mancante |
| `uni-bios_4_0.rom` | 131072 | `a7aab458` | Corretto | Mancante |
| `uni-bios_3_3.rom` | 131072 | `24858466` | Corretto | Mancante |
| `neopen.sp1` | 131072 | `cb915e76` | **Mancante** | Mancante |

Il nuovo ZIP risolve **8 dei 12** componenti segnalati; il vecchio nessuno. L'unione dei due nuovi archivi con le copie di gioco già autorizzate conserva gli stessi quattro mancanti: **non permette di preparare un neogeo.zip completo secondo il DAT attuale**. Non è stato creato un BIOS combinato incompleto né aggiunto un componente con hash differente.

## Necessari all'avvio e alternative

Il [driver alla revisione installata](https://github.com/libretro/FBNeo/blob/af50579270a610eda8ac580648d9c12acc7bb565/src/burn/drv/neogeo/d_neogeo.cpp#L938) distingue il BIOS 68000 selezionato dai componenti comuni. Il nuovo ZIP contiene il default MVS `sp-s3.sp1` (131072 byte, CRC 91b64be3), `sm1.sm1` (131072, 94416d67), `sfix.sfix` (131072, c2ea0cfd) e `000-lo.lo` (131072, 5a86cff2), tutti verificati.

Le quattro assenze corrispondono a **AES Japan**, **AES Asia**, **development kit** e **NeoOpen beta**. Il driver le marca BRF_SELECT e BRF_OPT. Non sono quattro parti da concatenare al BIOS MVS e la loro mancanza non equivale alla mancanza del BIOS MVS di avvio. UniBIOS 4.0/3.3 sono ulteriori alternative presenti e corrette, non sostituti dei componenti comuni.

La [selezione libretro](https://github.com/libretro/FBNeo/blob/af50579270a610eda8ac580648d9c12acc7bb565/src/burner/libretro/retro_common.cpp#L547), il [caricamento del BIOS scelto](https://github.com/libretro/FBNeo/blob/af50579270a610eda8ac580648d9c12acc7bb565/src/burn/drv/neogeo/neo_run.cpp#L435) e la [gestione delle ROM opzionali](https://github.com/libretro/FBNeo/blob/af50579270a610eda8ac580648d9c12acc7bb565/src/burner/libretro/libretro.cpp#L909) confermano che un sottoinsieme dipendente dalla configurazione può bastare al core. La compatibilità MVS è dunque **prevista sulla base di dati tecnici**, non verificata avviando i sei titoli. Una configurazione AES/debug/NeoOpen che richiedesse espressamente uno dei quattro file mancanti non è coperta da questo risultato.

Il validatore dell'app usa gli attributi del DAT: questa entry non distingue come opzionali le alternative del driver, quindi la politica corrente richiede tutti i 38 componenti. Il rapporto di completezza DAT non deve essere confuso con un profilo minimo di avvio. Non è stato modificato il validatore, ignorato un hash o cambiata la configurazione funzionante del Raspberry. La risoluzione del BIOS condiviso, incluso il clone kf2k2mp2 attraverso il parent, funziona nelle simulazioni; non è emerso un nuovo difetto di risoluzione delle dipendenze condivise.

## Sei giochi: dodici simulazioni nella pipeline esistente

| Set | Componenti di gioco corretti | BIOS richiesto | Nuovo ZIP: DAT | Vecchio ZIP | Installazione automatica attuale |
|---|---:|---|---:|---|---|
| `mslug5` | 13 / 13 | neogeo | 34 / 38 | Non valido | Bloccato: 4 varianti BIOS mancanti nel DAT completo |
| `wjammers` | 11 / 11 | neogeo | 34 / 38 | Non valido | Bloccato: 4 varianti BIOS mancanti nel DAT completo |
| `magdrop3` | 9 / 9 | neogeo | 34 / 38 | Non valido | Bloccato: 4 varianti BIOS mancanti nel DAT completo |
| `pbobblen` | 13 / 13 | neogeo | 34 / 38 | Non valido | Bloccato: 4 varianti BIOS mancanti nel DAT completo |
| `turfmast` | 9 / 9 | neogeo | 34 / 38 | Non valido | Bloccato: 4 varianti BIOS mancanti nel DAT completo |
| `kf2k2mp2` | 14 / 14 | neogeo | 34 / 38 | Non valido | Bloccato: 4 varianti BIOS mancanti nel DAT completo |

Ogni gioco è stato validato nuovamente con ciascuno dei due ZIP nella modalità non-merged, senza importazioni o conferme. Il nuovo produce esattamente quattro mancanze BIOS per ciascun set, senza componenti di gioco mancanti; il vecchio non soddisfa nessun componente BIOS con nome e hash richiesti. kf2k2mp2 è un clone di kof2002, ma i suoi 14 componenti di gioco nella copia non-merged risultano presenti; la dipendenza neogeo è individuata correttamente attraverso il parent.

Si tratta di **dodici preflight reali e bloccati**, non di dodici installazioni riuscite. Non viene prodotto né confermato un piano SFTP installabile dopo un controllo DAT negativo. Giochi importati nuovi: 0; giochi sincronizzati nuovi: 0; BIOS trasferiti: 0; giochi avviati durante questa verifica: 0. Originali ROM e BIOS preservati, nessuna modifica a salvataggi o configurazioni del Raspberry, nessun riavvio di EmulationStation.

## Inventario completo

### neogeo.zip

| File | Byte | CRC32 calcolato | SHA-1 calcolato | Confronto DAT |
|---|---:|---|---|---|
| `sp1-j3.bin` | 131072 | `fbc6d469` | `46b2b409b5b68869e367b40c846373623edb632a` | Nome, dimensione e CRC corretti |
| `sp1-u2` | 131072 | `62f021f4` | `62d372269e1b3161c64ae21123655a0a22ffd1bb` | Nome, dimensione e CRC corretti |
| `sp1-u3.bin` | 131072 | `2025b7a2` | `73d774746196f377111cd7aa051cc8bb5dd948b3` | Nome, dimensione e CRC corretti |
| `sp1-u4.bin` | 131072 | `1179a30f` | `866817f47aa84d903d0b819d61f6ef356893d16a` | Nome, dimensione e CRC corretti |
| `sp-1v1_3db8c.bin` | 131072 | `162f0ebe` | `fe1c6dd3dfcf97d960065b1bb46c1e11cb7bf271` | Nome, dimensione e CRC corretti |
| `sp-45.sp1` | 524288 | `03cc9f6a` | `cdf1f49e3ff2bac528c21ed28449cf35b7957dc1` | Nome, dimensione e CRC corretti |
| `sp-e.sp1` | 131072 | `2723a5b5` | `5dbff7531cf04886cde3ef022fb5ca687573dcb8` | Nome, dimensione e CRC corretti |
| `sp-j2.sp1` | 131072 | `acede59c` | `b6f97acd282fd7e94d9426078a90f059b5e9dd91` | Nome, dimensione e CRC corretti |
| `sp-j3.sp1` | 524288 | `486cb450` | `52c21ea817928904b80745a8c8d15cbad61e1dc1` | Nome, dimensione e CRC corretti |
| `sp-s.sp1` | 131072 | `c7f2fa45` | `09576ff20b4d6b365e78e6a5698ea450262697cd` | Nome, dimensione e CRC corretti |
| `sp-s2.sp1` | 131072 | `9036d879` | `4f5ed7105b7128794654ce82b51723e16e389543` | Nome, dimensione e CRC corretti |
| `sp-s3.sp1` | 131072 | `91b64be3` | `720a3e20d26818632aedf2c2fd16c54f213543e1` | Nome, dimensione e CRC corretti |
| `sp-u2.sp1` | 131072 | `e72943de` | `5c6bba07d2ec8ac95776aa3511109f5e1e2e92eb` | Nome, dimensione e CRC corretti |
| `uni-bios_1_0.rom` | 131072 | `0ce453a0` | `3b4c0cd26c176fc6b26c3a2f95143dd478f6abf9` | Nome, dimensione e CRC corretti |
| `uni-bios_1_1.rom` | 131072 | `5dda0d84` | `4153d533c02926a2577e49c32657214781ff29b7` | Nome, dimensione e CRC corretti |
| `uni-bios_1_2.rom` | 131072 | `4fa698e9` | `682e13ec1c42beaa2d04473967840c88fd52c75a` | Nome, dimensione e CRC corretti |
| `uni-bios_1_2o.rom` | 131072 | `e19d3ce9` | `af88ef837f44a3af2d7144bb46a37c8512b67770` | Nome, dimensione e CRC corretti |
| `uni-bios_1_3.rom` | 131072 | `b24b44a0` | `eca8851d30557b97c309a0d9f4a9d20e5b14af4e` | Nome, dimensione e CRC corretti |
| `uni-bios_2_0.rom` | 131072 | `0c12c2ad` | `37bcd4d30f3892078b46841d895a6eff16dc921e` | Nome, dimensione e CRC corretti |
| `uni-bios_2_1.rom` | 131072 | `8dabf76b` | `c23732c4491d966cf0373c65c83c7a4e88f0082c` | Nome, dimensione e CRC corretti |
| `uni-bios_2_2.rom` | 131072 | `2d50996a` | `5241a4fb0c63b1a23fd1da8efa9c9a9bd3b4279c` | Nome, dimensione e CRC corretti |
| `uni-bios_2_3.rom` | 131072 | `27664eb5` | `5b02900a3ccf3df168bdcfc98458136fd2b92ac0` | Nome, dimensione e CRC corretti |
| `uni-bios_2_3o.rom` | 131072 | `601720ae` | `1b8a72c720cdb5ee3f1d735bbcf447b09204b8d9` | Nome, dimensione e CRC corretti |
| `uni-bios_3_0.rom` | 131072 | `a97c89a9` | `97a5eff3b119062f10e31ad6f04fe4b90d366e7f` | Nome, dimensione e CRC corretti |
| `uni-bios_3_1.rom` | 131072 | `0c58093f` | `29329a3448c2505e1ff45ffa75e61e9693165153` | Nome, dimensione e CRC corretti |
| `uni-bios_3_2.rom` | 131072 | `a4e8b9b3` | `c92f18c3f1edda543d264ecd0ea915240e7c8258` | Nome, dimensione e CRC corretti |
| `uni-bios_3_3.rom` | 131072 | `24858466` | `0ad92efb0c2338426635e0159d1f60b4473d0785` | Nome, dimensione e CRC corretti |
| `uni-bios_4_0.rom` | 131072 | `a7aab458` | `938a0bda7d9a357240718c2cec319878d36b8f72` | Nome, dimensione e CRC corretti |
| `vs-bios.rom` | 131072 | `f0e8f27d` | `ecf01eda815909f1facec62abf3594eaa8d11075` | Nome, dimensione e CRC corretti |
| `000-lo.lo` | 131072 | `5a86cff2` | `5992277debadeb64d1c1c64b0a92d9293eaf7e4a` | Nome, dimensione e CRC corretti |
| `japan-j3.bin` | 131072 | `dff6d41f` | `e92910e20092577a4523a6b39d578a71d4de7085` | Nome, dimensione e CRC corretti |
| `sfix.sfix` | 131072 | `c2ea0cfd` | `fd4a618cdcdbf849374f0a50dd8efe9dbab706c3` | Nome, dimensione e CRC corretti |
| `sm1.sm1` | 131072 | `94416d67` | `42f9d7ddd6c0931fd64226a60dc73602b2819dcf` | Nome, dimensione e CRC corretti |
| `sp1.jipan.1024` | 131072 | `9fb0abe4` | `18a987ce2229df79a8cf6a84f968f0e42ce4e59d` | Nome, dimensione e CRC corretti |

### neogeo old.zip

| File | Byte | CRC32 calcolato | SHA-1 calcolato | Confronto DAT |
|---|---:|---|---|---|
| `aes-bios.bin` | 131072 | `9036d879` | `4f5ed7105b7128794654ce82b51723e16e389543` | Hash di `sp-s2.sp1`, nome differente |
| `sfix.sfx` | 131072 | `354029fc` | `4ae4bf23b4c2acff875775d4cbff5583893ce2a1` | Nessuna corrispondenza nel DAT attivo |
| `sm1.sm1` | 131072 | `97cf998b` | `977387a7c76ef9b21d0b01fa69830e949a9a9626` | Nessuna corrispondenza nel DAT attivo |
| `000-lo.lo` | 65536 | `e09e253c` | `2b1c719531dac9bb503f22644e6e4236b91e7cfc` | Nessuna corrispondenza nel DAT attivo |

## Diritti e prossima operazione

I due ZIP non contengono testi di licenza o permessi. La presenza su Internet Archive e l'etichetta freeware/UniBIOS non attestano i diritti di trasferimento di tutti i BIOS SNK inclusi. Il sito ufficiale UniBIOS non è risultato accessibile durante la verifica; non viene attribuita all'intero archivio una licenza non dimostrata. Non è stato scaricato altro firmware e non è stato distribuito alcun BIOS.

Per utilizzare il nuovo ZIP in modalità MVS va prima risolta la distinzione tra la politica di DAT completo e un eventuale profilo di avvio esplicitamente verificato rispetto alla configurazione scelta, conservando i controlli di integrità. L'alternativa è completare il DAT esclusivamente con copie legittime dai CRC attesi. Queste quattro varianti non vanno richieste come se fossero intrinsecamente necessarie al boot MVS.

**Possiamo installare i sei giochi Neo Geo con questi BIOS? Non ancora tramite la pipeline automatica attuale.** Il nuovo è il candidato corretto per la compatibilità MVS prevista e contiene tutti i componenti di avvio standard verificati, ma il preflight dell'app rimane bloccato dalle quattro varianti elencate; il vecchio non è utilizzabile per questo DAT. Nessuna prova di avvio è stata dichiarata. Prima di qualsiasi trasferimento BIOS restano necessari diritti di utilizzo verificati e conferma esplicita dell'utente.
