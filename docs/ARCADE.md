# Arcade, Neo Geo e compatibilità

## Evidenze separate

1. **Metadati:** il DAT descrive il nome tecnico, titolo, produttore, anno, parent/clone, BIOS e componenti. Giocatori, orientamento, controlli e genere rimangono sconosciuti quando la fonte non li dichiara.
2. **Completezza:** i contenuti dell'archivio coincidono con il manifest scelto. Questo non prova che il gioco sia veloce o avviabile sul Raspberry.
3. **Corrispondenza DAT/core:** il dry-run rileva versione e hash del core installato, profilo e configurazione effettivamente usata da runcommand.
4. **Test di gioco:** dichiarazione dell'operatore sul dispositivo e sullo specifico hash, con risultati osservati. La semplice apertura dello ZIP o una sincronizzazione riuscita non costituisce un test.

## Organizzazione dei set

| Organizzazione | Posizione attesa dei componenti |
| --- | --- |
| Split | Componenti propri nel clone, componenti `merge` nel parent/BIOS dichiarato; dipendenze verificate separatamente. |
| Merged | Componenti parent e clone nell'archivio parent; accettati nomi diretti o sottocartella tecnica del clone. |
| Non-merged | Componenti di gioco e parent nell'archivio del gioco; BIOS esterno quando dichiarato. |
| Full-non-merged | Componenti di gioco, parent e BIOS nell'archivio del gioco. |

La validazione è conservativa: richiede tutti i componenti non opzionali dichiarati dal DAT. Può segnalare come incompleto un insieme minimo che un particolare core riuscirebbe comunque ad avviare. `nodump`, componenti senza hash e dischi esterni sono segnalati; nessuna riparazione o ricostruzione automatica.

Un clone merged può essere completo ma non esportabile automaticamente come gioco distinto: avviare il nome del parent non seleziona necessariamente il clone. L'app blocca questa preparazione e conserva il rapporto. Per il trasferimento usare un set split/non-merged legittimamente disponibile. Un BIOS è una risorsa, mai un gioco esportabile.

ZIP e 7z vengono decompressi **solo verso funzioni di hashing in memoria**, senza creare file di contenuto sul disco. Si controllano dimensione, CRC/SHA1/SHA256/MD5 dichiarati, percorsi, duplicati, link, cifratura, numero dei membri (20.000), dimensione espansa (2 GiB) e rapporto di compressione (1.000). I componenti vengono confrontati per nome, dimensione e tutti gli hash presenti. L'archivio principale e le dipendenze ricevono anche SHA-256 esterno.

## Profili dei core

- **lr-mame2003:** DAT MAME 0.78 e binario che dichiara 0.78; ZIP. Non usare set MAME recenti o MAME 2003-plus come equivalenti. [Documentazione originale](https://docs.libretro.com/library/mame_2003/).
- **lr-fbneo:** ZIP/7z; DAT della revisione effettiva. Il numero generico 1.0.0.03 non identifica da solo una build. L'acquisizione ufficiale verifica Git commit e hash; in assenza di revisione rilevabile è richiesta un'associazione documentata dell'operatore fissata agli hash del DAT e del core. [Documentazione originale](https://docs.libretro.com/library/fbneo/).

Il rilevamento chiama solo `retro_get_system_info` in un processo isolato, senza `retro_init` o caricamento di un gioco. Elenca gli altri core già presenti, senza installarli o dichiararli profili arcade validati. Le nuove console richiedono un core predefinito configurato e rilevato prima della sincronizzazione.

Le preferenze per sistema e gioco sono **locali all'applicazione**. Il dry-run controlla `emulators.cfg` del sistema e gli override in `configs/all/emulators.cfg` (chiave nome tecnico e forma legacy). Un disallineamento blocca il trasferimento e richiede una configurazione nella sessione locale RetroPie. Nessun file di sistema viene cambiato dall'app. [Selezione core runcommand](https://github.com/RetroPie/RetroPie-Setup/blob/master/scriptmodules/supplementary/runcommand/runcommand.sh).

## Neo Geo MVS / AES e BIOS

La sezione Neo Geo raccoglie i set riconosciuti dal DAT, dai driver originali o dal sistema esplicito nel manifest. MVS/AES sono modalità registrabili per il gioco; non sono due copie artificiali dello stesso titolo. La preferenza registrata non modifica le opzioni BIOS/UniBIOS del core: impostarle dalla console locale.

Importare manualmente soltanto BIOS ottenuti legittimamente, dalla normale Importazione con piattaforma Neo Geo. Validarli usando il record BIOS del DAT. Il rilevamento remoto controlla presenza/hash nelle posizioni supportate; il dry-run FBNeo verifica anche nomi, dimensioni e hash dei componenti BIOS già presenti in `bios_root` o `bios_root/fbneo`. Se mancano o sono diversi, il piano è bloccato. Il BIOS non viene aggiunto alla lista dei trasferimenti. Il backend non distribuisce né scarica BIOS proprietari.

Per MAME con BIOS esterno, l'attuale preparazione richiede un set full-non-merged legittimamente disponibile: la copia automatica del BIOS separato rimane disabilitata. I set con BIOS incorporato sono confrontati con il DAT completo.

## Esportazione e sincronizzazione

Si conservano nomi tecnici, estensioni e archivi intatti. Ogni gioco ha un gruppo atomico: `neogeo/rlm-<hash>/<set>.zip`, oppure `arcade`, `fba`, `mame-libretro` secondo la piattaforma. I parent necessari stanno nello stesso gruppo del clone. La copia di un parent in due gruppi non viene conteggiata come un nuovo titolo di catalogo; lo spazio del piano include le copie effettive.

La preparazione verifica nuovamente file, dipendenze e DAT; l'esecuzione ricontrolla profilo e prove del dry-run. Restano attivi SHA-256, staging SFTP, controllo spazio, blocco dei conflitti, gamelist con backup e copertine autorizzate dell'Incremento 3. EmulationStation attiva rinvia i gamelist. Nessun aggiornamento del sistema o dei core.

## Sessione locale e limiti del Pi 3 B+

Il precedente avvio via SSH non aveva terminale di controllo (`TTY_NR=0`) e ha impedito l'avvio dei giochi con errori `/dev/tty`. Il ripristino è stato effettuato dall'utente con reboot completo. **Non avviare EmulationStation tramite nohup/SSH con sola redirezione verso `/dev/tty1`: non garantisce una sessione locale valida.** L'app espone PID e TTY_NR in sola lettura e non contiene un'azione di riavvio.

L'Incremento 4 non riavvia Raspberry, servizi o frontend. Qualunque futura prova che lo richieda necessita di consenso specifico e di un metodo che conservi la sessione locale. Il test di avvio deve essere fatto dalla console con controller; l'esito va registrato separatamente.

CPS-3, set pesanti e alcuni titoli PS1 possono richiedere più risorse del Pi 3 B+. La corrispondenza DAT/core non è una promessa di frame rate. Arcade CHD, selezione automatica dei cloni merged, modifica delle opzioni core e conversioni dei set restano fuori dall'attuale verificatore.
