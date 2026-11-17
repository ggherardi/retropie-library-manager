# Incremento 6 — Collaudo e risultati

Verifica del 18 novembre 2026, su Windows 11 e Raspberry Pi 3 B+ con RetroPie 4.8. I rapporti dettagliati, le immagini e le copie di sicurezza locali restano in `.runtime/increment6`, esclusa da Git. Non vengono pubblicati ROM, BIOS, media scaricati o credenziali.

## Numeri effettivi

| Voce | Risultato |
|---|---:|
| Classici catalogati, solo metadati | 914 |
| Classici identificati e realmente presenti | 7 |
| Classici senza copia locale identificata | 907 |
| Giochi sul Raspberry | 97 |
| Giochi nel catalogo Windows al termine | 98 |
| Giochi con copertina/anteprima preesistente | 35 |
| Giochi con screenshot associato | 30 |
| Publisher completati da DAT verificati | 15 |
| Nuovi titoli RLM da correggere | 0 |
| Nomi leggibili preservati | 97 giochi e 97 cartelle |
| Download media falliti | 0 |

Il catalogo Windows include la nuova importazione locale di **Vagrant Story**, effettuata durante il lavoro: è stata conservata, senza trasferirne i file in questa operazione dedicata ai 97 giochi già presenti. Il matching automatico dei dischi PS1 resta conservativo: il titolo del file da solo non basta ad associarlo al catalogo.

I sette membri identificati sono Circus, Robot Bowl, Rip Cord, Crash, Star Fire (set 1), Spectar (revision 3) e Gridlee. L'identità è legata al DAT e agli archivi validati; questo incremento non ha avviato giochi e non certifica prestazioni o giocabilità. Il conteggio “Da Recuperare” è riferito alle identità confermate, non a una ricerca approssimativa dei nomi.

Le 30 associazioni screenshot comprendono **27 immagini homebrew già note come anteprime/copertine** e **3 screenshot dai provider aggiornati**: Nova the Squirrel, UR4GUYS e madpew's battlegrounds. Non sono 30 nuove illustrazioni o box art. I ruoli sono ora separati e conservano fonte, licenza e hash. Sul Raspberry sono stati aggiunti 29 file immagine: un contenuto era già presente con lo stesso hash. Non sono state scaricate nuove ROM commerciali.

## Distribuzione del catalogo

| Piattaforma | Titoli |
|---|---:|
| NES / Famicom | 80 |
| SNES | 78 |
| Mega Drive | 75 |
| Master System | 44 |
| Game Boy | 49 |
| Game Boy Color | 34 |
| Game Boy Advance | 69 |
| PC Engine | 40 |
| Neo Geo, identificatori FBNeo | 86 |
| Arcade / MAME | 241 |
| PlayStation 1 | 118 |

Le voci per piattaforme differenti sono intenzionalmente distinte. La selezione è editoriale e i metadati sono riferiti a fonti versionate: nessuna classifica, disponibilità commerciale o licenza inventata. Per i campi assenti viene mantenuto lo stato sconosciuto.

## Sincronizzazione reale e preservazione

Il primo controllo ha rilevato il formato effettivo di `es_settings.cfg`: elementi XML fratelli senza una radice unica. Il generatore è stato adattato e testato prima della scrittura. Il formato delle collezioni è stato verificato nel codice RetroPie e nel binario installato, SHA-256 `605a304afec9b9cddc2c2694b4442996165f443c029ca57c09704964207d331a`.

L'utente ha chiuso EmulationStation dalla console locale; la verifica remota ha confermato l'assenza del processo. Una nuova fotografia dei dati è stata acquisita dopo la chiusura, così da includere gli ultimi salvataggi e le statistiche scritte dalla console.

| Controllo | Risultato |
|---|---:|
| File remoti preesistenti, tutti invariati per SHA-256 | 232 |
| ROM preservate | 97 |
| Salvataggi individuati e preservati | 2 |
| XML gamelist validi | 11 |
| Gamelist modificati / già identici | 8 / 3 |
| Membri della raccolta Grandi Classici | 7 |
| File immagine verificati per hash | 64 |
| File metadati/configurazione verificati per hash | 13 |
| Backup verificati | 9 |
| Byte trasferiti | 1.186.166 |
| Spazio libero dopo il trasferimento | 26.990.796.800 byte, circa 25,14 GiB |
| Margine minimo configurato | 4 GiB |

La raccolta è stata creata in `~/.emulationstation/collections/custom-Grandi Classici.cfg`, con sette percorsi assoluti di ROM esistenti. È stata aggiunta a `CollectionSystemsCustom`; tutti gli altri valori di configurazione sono stati confrontati e preservati, compresi tema, video e controlli. `UseCustomCollectionsSystem=true` raggruppa le raccolte personalizzate nella relativa sezione della console.

Gli otto gamelist modificati e le impostazioni hanno backup `.rlm-backup-<id esecuzione>` verificati prima della sostituzione. La raccolta era nuova e non aveva un file precedente da salvare. Sono stati mantenuti nomi, percorsi, statistiche e campi preesistenti; le modifiche alle immagini sono quelle selezionate nel piano. Nessuna cancellazione o rinomina di ROM, nessun cambiamento di emulatori, firmware, kernel o video.

Il secondo dry-run ha rilevato **zero byte necessari**, zero nuove immagini e tutti i 13 file metadati/configurazione già identici. Anche la seconda esecuzione confermata ha trasferito **zero byte**, saltato 161 file già presenti e creato zero backup. Spazio libero finale: **26.990.792.704 byte**, circa 25,14 GiB.

L'utente ha riaperto EmulationStation dalla console locale e confermato: **«Raccolta e titoli visibili»**. Non sono stati impartiti comandi SSH di avvio, arresto o riavvio del frontend o del Raspberry. La verifica della raccolta non equivale a una nuova prova di avvio dei singoli giochi.

Il processo effettivo è stato rilevato su `/dev/tty1`; il log conferma il caricamento di `custom-Grandi Classici.cfg` e del controller ESM-9101. Carbon 2021 segnala l'assenza di SVG dedicati al nuovo nome della raccolta (logo/controller): è un limite grafico, con titolo testuale visibile confermato dall'utente. Non sono stati installati asset o alterati i temi per nascondere questi avvisi.

## Test automatici

- **143 test backend Pytest superati**, nessun fallimento finale.
- **8 test frontend Vitest superati**.
- **6 test browser Playwright superati**, con libreria E2E separata e layout mobile a 390 px.
- Ruff, mypy su 33 moduli, ESLint, TypeScript e build Vite superati.
- Verifica browser aggiuntiva sui dati reali: pagine classici, mancanti, qualità e collezione completa; nessun errore JavaScript o overflow mobile.
- Controllo dei file destinati a Git: nessun segreto, credenziale, ROM, BIOS o file runtime; `git diff --check` senza problemi.

Regressioni coperte: hash/piattaforma/ambiguità, presenti contro mancanti, inclusione ed esclusione manuale senza cancellazione, metadati incompleti e verifica obsoleta, immagini sbagliate e candidate non appartenenti al piano, cache corrotta, licenze, correzioni locali e percorsi autorizzati, cronologia, duplicati, XML reale senza radice, raccolta supportata/non supportata, EmulationStation attiva, modifica concorrente delle impostazioni, backup, ROM/salvataggi e sincronizzazione ripetuta. Rimangono attivi i test della correzione 5.1 per NES, Game Boy e arcade.

## Limiti dichiarati

- I 907 classici mancanti non sono installati né scaricabili automaticamente dal solo riferimento DAT. Le copie devono essere ottenute legittimamente e importate.
- Le copertine commerciali prive di autorizzazione verificata non sono state scaricate; si usano placeholder, senza immagini inventate.
- La completezza non certifica la correttezza: 98 giochi restano da verificare o completare. I campi conosciuti nella libreria finale sono titolo 100%, genere 41,8%, anno 46,9%, sviluppatore 70,4%, publisher 15,3%, descrizione 70,4%, copertina/anteprima 35,7%, screenshot 30,6%.
- Non sono stati eseguiti test di avvio di giochi in questo incremento. Le evidenze di test preesistenti restano separate dalla sincronizzazione.
- Carbon 2021 è stato mantenuto dopo la verifica del layout 16:9. Carbon è documentato come alternativa, senza installazione. L'ordine e la resa della raccolta seguono le preferenze di EmulationStation; la valutazione dal televisore richiede la console locale.
- Il tema non dispone di logo/controller dedicati a “Grandi Classici”; usa il titolo testuale e registra avvisi per quegli SVG mancanti. La raccolta è caricata e visibile.
