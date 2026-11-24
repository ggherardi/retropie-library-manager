"""Read-only user projection of durable installation evidence, including legacy jobs.

This module never grants validation, edits a job or performs remote I/O.
Legacy diagnostic text is classified here once, not independently in each client.
"""

import re
from collections import Counter
from pathlib import PureWindowsPath

PHASES = {
    "queued": "In attesa",
    "ready": "Pronto per installare",
    "reanalyzing": "Analisi dei file",
    "validating": "Controllo dei file",
    "importing": "Aggiunta alla libreria",
    "enriching": "Ricerca immagini e informazioni",
    "preparing_sync": "Preparazione sulla console",
    "transferring": "Copia sulla console",
    "verifying": "Verifica dei file copiati",
    "waiting_device": "Attendo la connessione alla console",
    "scanning": "Analisi della selezione",
}
ACTIVE = set(PHASES)
LABELS = {
    "working": "In lavorazione",
    "installed": "Installato",
    "already_installed": "Già installato",
    "console_update": "Da aggiornare sulla console",
    "intervention": "Serve il tuo intervento",
    "blocked": "Installazione bloccata",
    "unsupported_platform": "Console non supportata",
    "local": "Nella libreria PC",
    "excluded": "Escluso",
}

DIAGNOSIS_LABELS = {
    "corrupt_archive": "Archivio corrotto",
    "unreadable_archive": "Archivio non valido",
    "incomplete_disc": "Gioco incompleto",
    "incomplete_set": "Gioco incompleto",
    "missing_bios": "BIOS mancante o non verificato",
    "insufficient_hardware": "Hardware insufficiente",
    "unidentified": "Gioco non identificato",
    "ambiguous_set": "Scelta del set richiesta",
}


def diagnose(item):
    info, error = item.get("identification", {}), item.get("error", {})
    # On a failed reanalysis, the previous identification is still in the job history.
    if error.get("cause"):
        info = {}
    reason = error.get("cause") or info.get("reason", "")
    text = reason.lower()
    candidates = info.get("candidates", [])
    primary = candidates[0].get("report", {}) if candidates else {}
    complete_candidate = any(c.get("report", {}).get("launchable") for c in candidates)
    bios = set(primary.get("bios", []))
    bios_missing = any(p.get("set") in bios for p in primary.get("problems", []))
    if item.get("status") == "unsupported_platform" or (
        "core configurato non disponibile per " in text
        or "core configurato non rilevato sul raspberry" in text
    ):
        return (
            "unsupported_platform",
            "unsupported_platform",
            reason,
            "L’installazione richiede un profilo e un core compatibili con questa piattaforma.",
        )
    if text.startswith("hardware insufficiente") or error.get("code") == "insufficient_hardware":
        return (
            "insufficient_hardware",
            "blocked",
            reason,
            "Verifica il requisito hardware indicato per il dispositivo selezionato.",
        )
    if info.get("kind") == "unidentified_archive" or text.startswith("nessun gioco riconoscibile"):
        return (
            "unidentified",
            "intervention",
            "L’archivio è leggibile. Il suo contenuto non identifica un gioco conosciuto.",
            "Consulta i membri nei dettagli e verifica la piattaforma e la provenienza della copia.",
        )
    if "ecm" in text or "ape" in info.get("unsupported_formats", []) or info.get("unsupported_formats"):
        return (
            "unsupported_disc",
            "blocked",
            "Il disco non è in un formato completo utilizzabile.",
            "Fornisci una copia completa in un formato supportato, con il descrittore del disco. L’app la controllerà prima di installarla.",
        )
    if any(
        w in text
        for w in (
            "iso9660",
            "immagine incompleta",
            "nastro c64 incompleta",
            "rom nes troncata",
            "bin troncato",
            "rom game boy troncata",
            "rom atari 7800 troncata",
            "componente mancante",
            "riferimento mancante",
        )
    ):
        return (
            "incomplete_disc",
            "blocked",
            "I dati del gioco sono incompleti o incoerenti con il formato dichiarato.",
            "Verifica o sostituisci la copia con tutti i suoi componenti, poi analizzala nuovamente. I file attuali non vengono installati.",
        )
    if (bios_missing and not complete_candidate) or (
        "bios" in text and any(w in text for w in ("manc", "non verific", "non disponibile"))
    ):
        return (
            "missing_bios",
            "intervention",
            "Manca un BIOS compatibile per questa console.",
            "Aggiungi un BIOS ottenuto legittimamente nelle posizioni previste dalla diagnostica. Poi scegli Rianalizza o Riprova: il gioco e le dipendenze saranno ricontrollati.",
        )
    if "gamelist" in text and any(w in text for w in ("cambiato", "conflitto")):
        return (
            "metadata_changed",
            "intervention",
            "L’elenco giochi sulla console è cambiato durante l’operazione.",
            "Scegli Aggiorna piano. Il programma leggerà l’elenco attuale e preparerà un nuovo piano verificato. Se richiesto, chiudi EmulationStation dalla console locale.",
        )
    if any(w in text for w in ("conflitto", "sovrascritt", "remoto differente", "file differente")):
        return (
            "remote_conflict",
            "intervention",
            "Sulla console esistono file diversi da quelli selezionati.",
            "Controlla i file indicati nei dettagli. Dopo aver risolto la differenza, riprova: verrà preparato un nuovo piano senza sovrascritture automatiche.",
        )
    if any(w in text for w in ("password", "cifrato", "cifratura")):
        return (
            "encrypted",
            "blocked",
            "L’archivio è protetto da password.",
            "Fornisci una copia non cifrata che sei autorizzato a usare. La nuova selezione sarà controllata automaticamente.",
        )
    if "archivio suddiviso incompleto o corrotto" in text:
        return (
            "invalid_archive",
            "blocked",
            "Il gruppo di volumi è incompleto o danneggiato.",
            "Controlla tutti i volumi, incluso quello finale, e ripeti l’analisi.",
        )
    if "il file zip contiene una pagina html" in text or "file is not a zip file" in text:
        return (
            "unreadable_archive",
            "blocked",
            "Il file contiene una pagina HTML salvata con estensione ZIP."
            if "pagina html" in text
            else "Il file selezionato non è un archivio ZIP leggibile.",
            "Verifica il file di origine e seleziona una copia ZIP valida.",
        )
    if any(w in text for w in ("corrott", "badzip", "bad7z", "bad crc", "crcerror", "lzmaerror")):
        return (
            "corrupt_archive",
            "blocked",
            "Il decoder ha rilevato dati d’archivio danneggiati.",
            "Sostituisci la copia con un archivio integro e ripeti l’analisi.",
        )
    if any(
        w in text
        for w in (
            "non supportat",
            "limite",
            "oltre il",
            "volume mancante",
            "non sicur",
        )
    ):
        return (
            "invalid_archive",
            "blocked",
            "Non possiamo preparare questo archivio in sicurezza.",
            "Consulta la causa nei dettagli e fornisci una copia integra in un formato supportato e nei limiti indicati. Poi scegli Rianalizza.",
        )
    if any(
        w in text for w in ("timeout", "timed out", "connection", "socket", "winerror", "offline", "spazio")
    ):
        return (
            "temporary",
            "intervention",
            "La console non è raggiungibile o non ha spazio sufficiente.",
            "Controlla collegamento e spazio libero, poi riprova. I file già verificati saranno riutilizzati.",
        )
    if info.get("variants"):
        return (
            "variant",
            "intervention",
            "Ci sono più versioni verificate dello stesso gioco.",
            "Espandi la scheda e scegli la versione da installare. Il programma continuerà con i controlli previsti.",
        )
    if candidates:
        if complete_candidate:
            return (
                "ambiguous_set",
                "intervention",
                "Il DAT ha verificato un set completo. La scelta richiede conferma.",
                "Apri i dettagli e verifica la variante completa per il core desiderato.",
            )
        if primary.get("status") != "incomplete":
            return (
                "set_review",
                "intervention",
                "Il set arcade richiede una verifica.",
                "Consulta il rapporto DAT e controlla la versione e le dipendenze.",
            )
        return (
            "incomplete_set",
            "intervention",
            "Alcuni componenti richiesti dal DAT mancano o differiscono per nome, dimensione o hash.",
            "Controlla i componenti nei dettagli e aggiungi quelli mancanti ottenuti legittimamente. Poi scegli Rianalizza; una scelta non aggira la verifica.",
        )
    if item.get("status") == "awaiting_decision":
        return (
            "identity",
            "intervention",
            "Non riusciamo ancora a identificare questa copia con certezza.",
            "Apri Risolvi problema e conferma solo informazioni note dalla fonte. Poi il programma controllerà nuovamente i file.",
        )
    return (
        "error",
        "blocked",
        "L’installazione si è fermata durante il controllo dei file.",
        "Consulta la causa nei dettagli. Dopo averla corretta, riprova l’analisi o seleziona una copia completa.",
    )


def view(item, batch, run=None):
    status = item.get("status", "queued")
    progress = item.get("progress", {})
    report = (run or {}).get("report")
    report = report or progress.get("report", {})
    verified = bool(report.get("games")) and all(
        g.get("status") in {"transferred", "present"} for g in report["games"]
    )
    prior = [
        r
        for r in progress.get("reports", [])
        if r.get("games") and all(g.get("status") in {"transferred", "present"} for g in r["games"])
    ]
    verified = verified or bool(prior)
    deferred = bool(report.get("metadata_deferred")) or status == "pending_refresh"
    state, code, message, action = "working", "", "", ""
    actions = []
    if verified:
        # A subsequent metadata pass must never turn verified ROMs back into a transfer.
        metadata_pending = (
            deferred
            or bool(progress.get("metadata_review"))
            or status in {"failed", "preparing_sync", "pending_refresh"}
        )
        first_report = prior[0] if prior else report
        already = all(g.get("status") == "present" for g in first_report.get("games", [])) and bool(
            first_report.get("games")
        )
        state = "console_update" if metadata_pending else "already_installed" if already else "installed"
        message = "I file sulla console sono stati verificati. L’avvio del gioco resta una verifica separata."
        if metadata_pending:
            action = "Chiudi EmulationStation dalla console locale per aggiornare titoli e immagini. Attendi la fine dell’aggiornamento qui, poi riaprila localmente."
            code = "console_metadata"
        if status == "failed" and diagnose(item)[0] == "metadata_changed":
            code, _, message, action = diagnose(item)
        if progress.get("metadata_review"):
            code = "metadata_review"
            action = "Apri il gioco nella libreria e correggi il titolo o l’immagine. Poi scegli Aggiorna metadati; se necessario, chiudi EmulationStation dalla console locale."
            if status == "installed":
                actions.append("retry")
        if item.get("game_id"):
            actions.append("library")
        if status == "failed":
            actions.append("retry")
        elif status == "installed" and item.get("visibility") != "operator_confirmed":
            actions.append("visible")
        if status == "installed":
            actions.append("metadata_review")
    elif status == "installed":
        state, code = "intervention", "missing_evidence"
        message = "Manca il rapporto di verifica di questa operazione precedente."
        action = "Consulta la cronologia tecnica e verifica la copia dalla libreria prima di considerarla installata."
        actions = ["library"] if item.get("game_id") else []
    elif status == "imported_local":
        state, message = (
            "local",
            "Importazione sul PC completata; nessuna installazione sulla console richiesta.",
        )
        actions = ["library"]
    elif status in {"ignored", "prepared"}:
        state = "excluded"
    elif batch.get("control") != "run" or status in {"paused", "cancelled"}:
        state, code = "intervention", "paused"
        message, action = (
            "L’operazione è in pausa o è stata annullata.",
            "Scegli Riprendi per continuare dal prossimo punto sicuro.",
        )
        actions = ["resume"]
    elif status in {"awaiting_decision", "unsupported_platform", "failed"}:
        code, state, message, action = diagnose(item)
        if status in {"awaiting_decision", "unsupported_platform"}:
            actions.append("skip")
            if state == "intervention" and code != "unidentified":
                actions.append("resolve")
        if not item.get("game_id"):
            actions.append("reanalyze")
        elif state in {"intervention", "unsupported_platform"}:
            actions.append("retry")
    elif status == "waiting_device":
        code, message = "offline_retry", "Attendo la console; la connessione verrà riprovata automaticamente."
    elif not batch.get("authorized"):
        state, code = "intervention", "confirmation"
        message, action = (
            "I file sono pronti per la tua conferma.",
            "Controlla l’anteprima e scegli Installa automaticamente.",
        )
    if state == "blocked":
        actions.append("replace")
    if state == "working":
        actions = ["pause", "cancel"]
    sync = progress.get("sync", {})
    measured = status == "transferring" and isinstance(sync.get("total"), (int, float)) and sync["total"] > 0
    transfer = (
        {"kind": "bytes", "value": min(max(0, sync.get("bytes", 0)), sync["total"]), "total": sync["total"]}
        if measured
        else {"kind": "indeterminate"}
        if state == "working"
        else {"kind": "none"}
    )
    return {
        "state": state,
        "label": "Gioco non identificato"
        if code == "identity" and not item.get("identification", {}).get("platform")
        else DIAGNOSIS_LABELS.get(code, LABELS[state]),
        "section": "active"
        if state == "working"
        else "completed"
        if state in {"installed", "already_installed", "console_update", "local", "excluded"}
        else "attention",
        "tone": "blue"
        if state == "working"
        else "green"
        if state in {"installed", "already_installed", "local"}
        else "yellow"
        if state == "intervention"
        else "red"
        if state in {"blocked", "unsupported_platform"}
        else "neutral",
        "phase": PHASES.get(
            status, "Aggiornamento dei titoli sulla console" if state == "console_update" else LABELS[state]
        ),
        "code": code,
        "message": message,
        "next_step": action,
        "actions": actions,
        "progress": transfer,
        "files_verified": verified,
        "visibility": item.get("visibility", "not_checked"),
        "launched": item.get("launched", False),
        "technical_status": status,
    }


def cards(items):
    """Fold companion tracks only for display; retain every raw operation in details."""
    groups: dict[tuple, list] = {}
    for item in items:
        if item.get("status") in {"prepared", "ignored"}:
            continue
        path = PureWindowsPath(item.get("source_key", ""))
        stem = re.sub(r"(?i)\s*\(track\s*\d+\)", "", path.stem).removesuffix(".bin")
        companion = path.suffix.lower() in {".cue", ".bin", ".ape", ".ecm", ".7z"} and (
            "(track " in path.stem.lower() or path.suffix.lower() == ".cue"
        )
        key = (
            (item.get("batch_id"), str(path.parent).casefold(), stem.casefold())
            if companion
            else (item["id"],)
        )
        groups.setdefault(key, []).append(item)
    result = []
    for group in groups.values():
        primary = max(
            group,
            key=lambda i: (
                i["experience"]["files_verified"],
                i["experience"]["state"] == "blocked",
                PureWindowsPath(i["source_key"]).suffix == ".cue",
            ),
        )
        result.append(
            {
                **primary,
                "operation_ids": [i["id"] for i in group],
                "companions": [i for i in group if i["id"] != primary["id"]],
            }
        )
    return result


def metrics(items, batches=()):
    grouped = cards(items)
    by_sha = {
        i.get("candidate", {}).get("sha256"): i["game_id"]
        for i in items
        if i.get("game_id") and i.get("candidate", {}).get("sha256")
    }
    unique = {}
    for item in sorted(grouped, key=lambda i: (i.get("created_at", ""), i["id"])):
        sha = item.get("candidate", {}).get("sha256")
        identity = item.get("game_id") or by_sha.get(sha) or sha
        archive_sha = item.get("identification", {}).get("archive", {}).get("sha256")
        if item.get("identification", {}).get("match") == "verified" and item["identification"].get(
            "reference"
        ):
            identity = identity or archive_sha
        source = PureWindowsPath(item.get("source_key", ""))
        member = re.sub(r"(?i)\s*\(track\s*\d+\)", "", source.stem).removesuffix(".bin").casefold()
        if "files" in source.parts:
            index = len(source.parts) - 1 - list(reversed(source.parts)).index("files")
            member = str(PureWindowsPath(*source.parts[index + 1 : -1]) / member).casefold()
        key = (
            ("game", identity)
            if identity
            else ("unresolved_archive", archive_sha, member)
            if archive_sha
            else ("unresolved", item["id"])
        )
        unique[key] = item
    values = list(unique.values())
    counts = Counter(i["experience"]["state"] for i in values)
    current = [
        {
            "id": i["id"],
            "batch_id": i["batch_id"],
            "title": i.get("title") or i.get("identification", {}).get("title", "Gioco in analisi"),
            **i["experience"],
        }
        for i in grouped
        if i["experience"]["state"] == "working"
    ]
    total, completed = (
        len(values),
        sum(counts[s] for s in ("installed", "already_installed", "console_update", "local")),
    )
    scanning = any(
        b.get("status") in {"queued", "scanning", "draft"} and b.get("control") == "run" for b in batches
    )
    return {
        "total": total,
        "identified": total - sum(k[0].startswith("unresolved") for k in unique),
        "completed": completed,
        "active": counts["working"],
        "intervention": counts["intervention"],
        "blocked": counts["blocked"] + counts["unsupported_platform"],
        "console_update": counts["console_update"],
        "operations": len(grouped),
        "unresolved": sum(k[0].startswith("unresolved") for k in unique),
        "current": current,
        "scanning": scanning,
        "progress": {
            "kind": "indeterminate" if scanning or current else "count",
            "value": completed,
            "total": total,
        },
    }
