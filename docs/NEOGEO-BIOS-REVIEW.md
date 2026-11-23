# BIOS Neo Geo e sei giochi — installazione del 23 novembre 2026

## Risultato attuale

**BIOS condiviso e tutti e sei i giochi installati sul Raspberry**, con SHA-256 locali/remoti uguali, XML valido e secondo dry-run a zero byte. L'utente ha autorizzato esplicitamente l'installazione dopo correzione e verifica del validatore. Nessun archivio originale è stato modificato; dieci file di salvataggio/configurazione controllati hanno mantenuto lo stesso SHA-256 prima e dopo. Nessun riavvio di EmulationStation tramite SSH.

Alla verifica tecnica non è stato avviato nessun gioco. La conferma dell'operatore dalla console locale viene registrata separatamente; non deriva dal successo della copia.

## Correzione del validatore

Profilo `fbneo-mvs-standard-v1`, limitato a `lr-fbneo v1.0.0.03 af50579`, revisione completa af50579270a610eda8ac580648d9c12acc7bb565. Il catalogo deve essere ufficiale verificato e tutti i 38 nomi/dimensioni/CRC dell'entry neogeo devono coincidere con il manifest fissato nel codice. Un DAT o una revisione diversi conservano la validazione rigorosa precedente.

Il [driver verificato](https://github.com/libretro/FBNeo/blob/af50579270a610eda8ac580648d9c12acc7bb565/src/burn/drv/neogeo/d_neogeo.cpp#L938) richiede per il profilo MVS standard:

| Componente | Byte | CRC32 |
|---|---:|---|
| sp-s3.sp1 | 131072 | 91b64be3 |
| sm1.sm1 | 131072 | 94416d67 |
| sfix.sfix | 131072 | c2ea0cfd |
| 000-lo.lo | 131072 | 5a86cff2 |

Le quattro assenze neo-po.bin, neo-epo.bin, neodebug.bin, neopen.sp1 sono alternative AES/debug/NeoOpen marcate BRF_SELECT/BRF_OPT dal driver. Il nuovo ZIP contiene 34 componenti corretti, inclusi i quattro obbligatori e UniBIOS 4.0/3.3. La completezza dei requisiti MVS non viene presentata come inventario 38/38 del DAT. Le alternative assenti sono esplicite nel rapporto; un'alternativa presente ma con hash errato blocca comunque il set. CRC32, dimensione e ogni altro hash dichiarato, incluso SHA-1, restano obbligatori. Nel DAT reale SHA-1 non è disponibile: gli SHA-1 dell'inventario sotto sono calcolati, non confrontati con valori inventati.

Prima della pianificazione e di nuovo prima del trasferimento sono stati letti core, comando effettivo, configurazioni RetroArch e opzioni. Il comando lr-fbneo è quello standard con il config neogeo; nessuna selezione AES o BIOS alternativo è attiva. Comandi personalizzati, include/percorsi non verificati, override BIOS incompatibili vengono rifiutati. Nessun config del Raspberry è stato modificato per rendere valido il set. La dipendenza BIOS del clone kf2k2mp2 viene risolta tramite kof2002.

## BIOS installato

Origine autorizzata: Desktop/bios/neogeo.zip. Destinazione `/home/pi/RetroPie/BIOS/neogeo.zip`, 1.858.095 byte.

SHA-256 verificato: `e86ab6faaaa490175d3f7edfd56f258ce26f24e625ba3d99cf0eb0f12e78f2c0`.

Dry-run iniziale: destinazione assente, nessun conflitto, 23.614.615.552 byte liberi. Pubblicazione tramite staging, verifica SHA-256 e rename senza sovrascritture, usando SafeRemote della pipeline. Consenso esplicito richiesto dal servizio per eseguire la copia; il valore predefinito rimane read-only. Il vecchio neogeo old.zip non è stato usato: un file corrisponde per hash a sp-s2.sp1 con nome differente; gli altri tre non corrispondono al DAT. Nessun nuovo firmware scaricato o pubblicato.

## Rapporto per gioco

| Set | Validazione | Trasferimento | SHA-256 remoto uguale all'originale | Avvio |
|---|---|---|---|---|
| `mslug5` | 13 componenti gioco corretti; MVS completo | Trasferito | `9d6bac660155bd05600e0bc3d4288440ffe18f2ab0ae148f884523063bc40d9b` | Non provato sulla console |
| `wjammers` | 11 componenti gioco corretti; MVS completo | Trasferito | `cd43ea666da62ba1c52e646b14aa05a08ce98622a5d472cdd3f338a2020251ec` | Non provato sulla console |
| `magdrop3` | 9 componenti gioco corretti; MVS completo | Trasferito | `a1ded4b29b2ea4481bc00dbfdc2a33900f81c0d9337917e45ec533143152d912` | Non provato sulla console |
| `pbobblen` | 13 componenti gioco corretti; MVS completo | Trasferito | `2ace03beb7af6fd35aa8ac1b81163a1f6126e6d47044fb58d8059481c0e1e7d8` | Non provato sulla console |
| `turfmast` | 9 componenti gioco corretti; MVS completo | Trasferito | `1178ee4b0d7265fa5f9a282fcf4ac9d9ddb6d4feb1159bd96ddb8915ece6d065` | Non provato sulla console |
| `kf2k2mp2` | 14 componenti gioco corretti; MVS completo | Trasferito | `f5d24763a5278b738c4912dacd152d83091a3583469bd36a28e8318849f5d3f0` | Non provato sulla console |

Sei righe libreria importate attraverso il servizio condiviso, deduplica per hash, metadati dal DAT ufficiale, nessuna riga BIOS trattata come gioco. Destinazioni neogeo/rlm-<hash>/<set>.zip generate dalla pipeline ordinaria. ArcadeValidation e SyncPresence persistenti riportano le stesse identità e hash.

Run ordinario DeviceService: `72030a73-190d-441a-a0cc-0fdabd14b10a`. Il dry-run completo non segnala conflitti; la conferma usa il consenso esplicito dell'utente. ROM e gamelist trasferiti: 201.223.624 byte, oltre ai 1.858.095 byte del BIOS condiviso. Spazio libero finale: **23.411.486.720 byte**, circa 23,41 GB / 21,80 GiB, sopra il margine minimo di 4 GiB.

Il gamelist Neo Geo è stato creato in `/opt/retropie/configs/all/emulationstation/gamelists/neogeo/gamelist.xml`, con i sei titoli leggibili e percorsi verificati. XML e SHA-256 controllati. EmulationStation era chiusa; metadati non rinviati. Non c'era un vecchio gamelist Neo Geo da sostituire: nessuna sovrascrittura o backup necessario per quel file nuovo. Gli altri gamelist non sono stati modificati.

Secondo dry-run `ec456371-6487-4a38-9631-2ceae63d2e0b`: **required_bytes=0**, nessun nuovo gruppo o metadato da trasferire. Gli hash finali sono stati riletti indipendentemente da SFTP, dopo il successo del run. Audit prima/dopo: dieci file di salvataggio/configurazione identici. Originali ZIP BIOS e giochi invariati.

## Test realmente eseguiti

- Suite backend completa: **335 passati**. Sulla versione finale, ulteriori regressioni mirate intelligence/BIOS: **34 passati**, incluse dieci prove dedicate.
- Casi BIOS: MVS valido con opzionali assenti, obbligatorio mancante, CRC errato, SHA-1 errato, opzionale presente corrotto, revisione sconosciuta, configurazioni incompatibili, dry-run read-only, copia verificata, ripetizione senza scritture, spazio insufficiente e conflitto senza sovrascrittura.
- Ruff passato, mypy passato su 50 moduli; ESLint, TypeScript, build passati; **17 test frontend e 14 browser passati**.
- File reali: BIOS e tutti i sei ZIP completi per il profilo MVS, core/configurazione reali, dry-run, trasferimento e verifica remota. Nessun mock usato per dichiarare i risultati dell'installazione reale.

## Prova sulla console

Richiesto all'utente di riaprire EmulationStation **dalla console locale**, controllare Neo Geo e provare almeno Metal Slug 5. Conferma ancora in attesa: nessun titolo viene dichiarato avviato sulla base del trasferimento.

**Possiamo installare i sei giochi Neo Geo con questi BIOS? Sì: ora risultano installati e verificati nel profilo MVS standard.** L'avvio effettivo resta uno stato separato e richiede la prova locale.

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
