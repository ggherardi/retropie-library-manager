import { useCallback, useEffect, useRef, useState } from "react";
import {
  Check,
  FolderOpen,
  Gamepad2,
  HardDrive,
  LoaderCircle,
  UploadCloud,
} from "lucide-react";
import { api, bytes } from "./api";

type Issue = {
  phase: string;
  file: string;
  cause: string;
  operation: string;
  remedy: string;
  retryable: boolean;
};
type Candidate = {
  uid: string;
  title: string;
  platform: string;
  core: string;
  matched_components: number;
  mode: string;
  report: {
    status: string;
    problems: { set: string; file: string; reason: string }[];
  };
};
type Item = {
  id: string;
  title: string;
  platform: string;
  status: string;
  phase: string;
  source_key: string;
  game_id: number | null;
  cover_url: string;
  visibility: string;
  pc_present: boolean;
  installed: boolean;
  launched: boolean;
  compatibility: string;
  candidate: { size?: number };
  identification: {
    size?: number;
    reason?: string;
    basis?: string;
    duplicate?: boolean;
    kind?: string;
    candidates?: Candidate[];
    choices?: string[];
  };
  error: Partial<Issue>;
  warnings: string[];
  progress: {
    destination?: string;
    free_bytes?: number;
    sync?: {
      bytes?: number;
      total?: number;
      file?: string;
      file_bytes?: number;
      file_total?: number;
    };
    preflight?: {
      core?: string;
      bios?: { name: string; available: boolean; verified: boolean }[];
    };
    report?: { transferred_bytes: number; skipped_files: number };
  };
};
type Upload = {
  id: string;
  relative: string;
  size: number;
  received: number;
  status: string;
};
type Batch = {
  id: string;
  mode: string;
  status: string;
  control: string;
  authorized: boolean;
  created_at: string;
  counts: Record<string, number>;
  items: Item[];
  total: number;
  uploads: Upload[];
  error: Partial<Issue>;
  progress: { scanned_files?: number; total_files?: number };
};
type Device = {
  id: string;
  is_default: boolean;
  config: { name: string; host: string };
  diagnostics: { space?: { free: number } };
};
type Summary = { batches: Batch[]; devices: Device[] };
type Source = { name: string; path: string; directory: boolean };
type Picked = { file: File; relative: string };
export const statusLabel: Record<string, string> = {
  draft: "File da caricare",
  queued: "In attesa",
  scanning: "Analisi",
  identifying: "Riconoscimento",
  preview: "Anteprima pronta",
  ready: "Pronto",
  awaiting_decision: "Da verificare",
  validating: "Validazione",
  importing: "Importazione",
  enriching: "Metadati e immagini",
  preparing_sync: "Controlli sul Raspberry",
  transferring: "Trasferimento",
  verifying: "Verifica SHA-256",
  installed: "File installati e verificati",
  pending_refresh: "File installati · metadati in attesa",
  waiting_device: "In attesa del Raspberry",
  imported_local: "Presente nella libreria PC",
  ignored: "Escluso",
  failed: "Operazione non riuscita",
  paused: "In pausa",
  cancelled: "Annullato",
  running: "In corso",
  waiting: "In attesa di intervento",
  completed: "Completato",
  completed_with_errors: "Completato con errori",
};

export function selectedFiles(files: File[], recursive: boolean): Picked[] {
  return files
    .map((file) => ({
      file,
      relative: file.webkitRelativePath
        ? file.webkitRelativePath.split("/").slice(1).join("/")
        : file.name,
    }))
    .filter((p) => recursive || !p.relative.includes("/"));
}

async function droppedFiles(
  transfer: DataTransfer,
  recursive: boolean,
): Promise<Picked[]> {
  const result: Picked[] = [];
  async function walk(entry: FileSystemEntry, prefix: string) {
    if (result.length >= 20000)
      throw new Error("Selezionare al massimo 20.000 file.");
    if (entry.isFile) {
      const file = await new Promise<File>((resolve, reject) =>
        (entry as FileSystemFileEntry).file(resolve, reject),
      );
      result.push({ file, relative: prefix + file.name });
    } else if (entry.isDirectory) {
      const reader = (entry as FileSystemDirectoryEntry).createReader();
      for (;;) {
        const entries = await new Promise<FileSystemEntry[]>(
          (resolve, reject) => reader.readEntries(resolve, reject),
        );
        if (!entries.length) break;
        for (const child of entries)
          if (recursive || child.isFile)
            await walk(
              child,
              prefix + (child.isDirectory ? child.name + "/" : ""),
            );
      }
    }
  }
  // Capture entries synchronously: the browser clears DataTransfer after the drop event.
  const entries = Array.from(transfer.items)
    .map((i) => i.webkitGetAsEntry?.())
    .filter((e): e is FileSystemEntry => !!e);
  const fallback = Array.from(transfer.files);
  if (!entries.length) return selectedFiles(fallback, recursive);
  for (const entry of entries) await walk(entry, "");
  return result;
}

function DecisionControls({
  item,
  choose,
}: {
  item: Item;
  choose: (body: object) => void;
}) {
  const [platform, setPlatform] = useState("");
  const [title, setTitle] = useState("");
  if (item.identification.kind === "archive") return null;
  return (
    <div className="install-options">
      {!!item.identification.choices?.length && (
        <label>
          Piattaforma proposta
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
          >
            <option value="">Seleziona soltanto se verificata</option>
            {item.identification.choices.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
      )}
      <label>
        Titolo verificato presso la fonte
        <input
          value={title}
          maxLength={300}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Facoltativo, se noto"
        />
      </label>
      <button
        disabled={!platform && !title.trim()}
        onClick={() =>
          choose({
            action: "choose",
            platform,
            title: title.trim(),
            confirmed_title: !!title.trim(),
          })
        }
      >
        Conferma identificazione e verifica
      </button>
      <small>
        La scelta non sostituisce i controlli di integrità e compatibilità.
      </small>
    </div>
  );
}

export default function Installations({ view }: { view: "add" | "queue" }) {
  const [summary, setSummary] = useState<Summary>({ batches: [], devices: [] });
  const [batch, setBatch] = useState<Batch | null>(null);
  const [batchId, setBatchId] = useState("");
  const [page, setPage] = useState(1);
  const [deviceId, setDeviceId] = useState("");
  const [mode, setMode] = useState("install");
  const [recursive, setRecursive] = useState(true);
  const [keepLocal, setKeepLocal] = useState(true);
  const [rights, setRights] = useState(false);
  const [picked, setPicked] = useState<Picked[]>([]);
  const [uploadProgress, setUploadProgress] = useState({
    done: 0,
    total: 0,
    file: "",
  });
  const [roots, setRoots] = useState<string[]>([]);
  const [directory, setDirectory] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [localPaths, setLocalPaths] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [filter, setFilter] = useState("");
  const controller = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const refresh = useCallback(async () => {
    const result = await api<Summary>("/installations");
    setSummary(result);
    setError((previous) =>
      previous.startsWith("Backend non disponibile:") ? "" : previous,
    );
    if (batchId)
      setBatch(
        await api<Batch>(`/installations/${batchId}?page=${page}&page_size=40`),
      );
  }, [batchId, page]);
  useEffect(() => {
    let alive = true;
    const poll = () =>
      refresh().catch((e) => {
        if (alive)
          setError(
            `Backend non disponibile: ${String(e)}. La coda è conservata; riprovo automaticamente.`,
          );
      });
    void poll();
    const timer = setInterval(poll, 1500);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [refresh]);
  useEffect(() => {
    api<{ roots: string[] }>("/installations/sources")
      .then((r) => setRoots(r.roots))
      .catch((e) => setError(String(e)));
  }, []);
  useEffect(() => () => controller.current?.abort(), []);
  const perform = async (label: string, operation: () => Promise<unknown>) => {
    setBusy(label);
    setError("");
    try {
      await operation();
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy("");
    }
  };
  const browse = (path: string) =>
    perform("Apertura cartella", async () => {
      const result = await api<{ items: Source[] }>(
        `/installations/sources?path=${encodeURIComponent(path)}`,
      );
      setDirectory(path);
      setSources(result.items);
    });
  const chooseBatch = (id: string) => {
    setBatchId(id);
    setBatch(null);
    setPage(1);
    setRights(false);
  };
  const upload = () =>
    perform("Caricamento della selezione", async () => {
      if (!picked.length) throw new Error("Seleziona almeno un file.");
      const files = picked.map((p) => ({
        relative: p.relative,
        size: p.file.size,
      }));
      let current =
        batch?.status === "draft"
          ? batch
          : await api<Batch>("/installations/uploads", "POST", {
              files,
              mode,
              device_id: deviceId,
              recursive: true,
              request_key: crypto.randomUUID(),
            });
      if (
        current.uploads.length !== files.length ||
        current.uploads.some(
          (u) =>
            !files.some((f) => f.relative === u.relative && f.size === u.size),
        )
      )
        throw new Error(
          "Per riprendere, riseleziona gli stessi file. Per una selezione diversa, scegli Nuova selezione.",
        );
      if (current.control !== "run")
        await api(`/installations/${current.id}/control`, "POST", {
          action: "resume",
        });
      setBatchId(current.id);
      setBatch(current);
      const abort = new AbortController();
      controller.current = abort;
      const total = files.reduce((sum, f) => sum + f.size, 0);
      let done = 0;
      for (const file of picked) {
        const target = current.uploads.find(
          (u) => u.relative === file.relative,
        )!;
        // Recheck already acknowledged chunks too: a newly selected file must be identical.
        for (
          let offset = 0;
          offset < file.file.size || (offset === 0 && file.file.size === 0);
          offset += 4 * 1024 ** 2
        ) {
          const block = await file.file
            .slice(offset, offset + 4 * 1024 ** 2)
            .arrayBuffer();
          const sha = Array.from(
            new Uint8Array(await crypto.subtle.digest("SHA-256", block)),
          )
            .map((b) => b.toString(16).padStart(2, "0"))
            .join("");
          const response = await fetch(
            `/api/installations/${current.id}/uploads/${target.id}?offset=${offset}`,
            {
              method: "PUT",
              headers: {
                "X-RLM-Request": "1",
                "Content-Type": "application/octet-stream",
                "X-Chunk-SHA256": sha,
              },
              body: block,
              signal: abort.signal,
            },
          );
          if (!response.ok)
            throw new Error(
              (await response.json()).detail ||
                "Upload interrotto. Riseleziona gli stessi file per riprendere.",
            );
          done += block.byteLength;
          setUploadProgress({ done, total, file: file.relative });
          if (!file.file.size) break;
        }
      }
      await api(`/installations/${current.id}/analyze`, "POST");
      current = await api<Batch>(`/installations/${current.id}`);
      setBatch(current);
      setPicked([]);
    });
  const local = () =>
    perform("Analisi delle cartelle", async () => {
      const result = await api<Batch>("/installations/local", "POST", {
        paths: localPaths,
        recursive,
        mode,
        device_id: deviceId,
        request_key: crypto.randomUUID(),
      });
      chooseBatch(result.id);
      setLocalPaths([]);
    });
  const control = (action: string) =>
    perform("Aggiornamento coda", async () => {
      if (action === "pause" || action === "cancel")
        controller.current?.abort();
      await api(`/installations/${batchId}/control`, "POST", { action });
    });
  const device =
    summary.devices.find((d) => d.id === deviceId) ||
    summary.devices.find((d) => d.is_default) ||
    summary.devices[0];
  const totals = summary.batches.reduce<Record<string, number>>((all, b) => {
    for (const [key, count] of Object.entries(b.counts))
      all[key] = (all[key] || 0) + count;
    return all;
  }, {});
  return (
    <div className="installations">
      {error && (
        <div className="error" role="alert">
          {error}
          <button
            onClick={() => {
              setError("");
              void refresh();
            }}
          >
            Riprova connessione
          </button>
        </div>
      )}
      {view === "add" && (
        <>
          <section className="install-hero panel">
            <span className="eyebrow">DAL PC AL RASPBERRY</span>
            <h2>I tuoi giochi, in un solo percorso.</h2>
            <p>
              Seleziona, controlla l’anteprima e avvia. Importazione, metadati e
              trasferimento verificato proseguono automaticamente.
            </p>
            <div className="install-steps">
              <span>01 · Seleziona</span>
              <span>02 · Controlla</span>
              <span>03 · Installa</span>
              <span>04 · Prova sulla console</span>
            </div>
            <div className="install-options">
              <label>
                Destinazione
                <select
                  aria-label="Raspberry di destinazione"
                  value={deviceId}
                  onChange={(e) => setDeviceId(e.target.value)}
                >
                  <option value="">Raspberry predefinito</option>
                  {summary.devices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.config.name} · {d.config.host}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Operazione
                <select
                  aria-label="Modalità installazione"
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                >
                  <option value="install">
                    Importa e installa sul Raspberry
                  </option>
                  <option value="local">
                    Importa soltanto nella libreria PC
                  </option>
                </select>
              </label>
            </div>
            <label className="checkline">
              <input
                type="checkbox"
                checked={recursive}
                onChange={(e) => setRecursive(e.target.checked)}
              />
              Includi le sottocartelle nella prossima selezione
            </label>
            <div
              className="install-drop"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                void droppedFiles(e.dataTransfer, recursive)
                  .then(setPicked)
                  .catch((err) => setError(String(err)));
              }}
            >
              <UploadCloud size={38} />
              <h3>Trascina qui file o cartelle</h3>
              <p>
                I BIN vanno selezionati insieme al CUE. I file originali restano
                invariati.
              </p>
              <div className="actions">
                <button onClick={() => fileInput.current?.click()}>
                  Seleziona file
                </button>
                <button onClick={() => folderInput.current?.click()}>
                  <FolderOpen size={16} />
                  Seleziona cartella
                </button>
              </div>
              <input
                hidden
                ref={fileInput}
                aria-label="File giochi"
                type="file"
                multiple
                onChange={(e) =>
                  setPicked(
                    selectedFiles(Array.from(e.target.files || []), recursive),
                  )
                }
              />
              <input
                hidden
                ref={folderInput}
                aria-label="Cartella giochi"
                type="file"
                multiple
                {...{ webkitdirectory: "" }}
                onChange={(e) =>
                  setPicked(
                    selectedFiles(Array.from(e.target.files || []), recursive),
                  )
                }
              />
            </div>
            <p className="muted">
              La selezione del browser crea una copia nell’archivio locale
              dell’app. Per file grandi già sul PC, usa le cartelle autorizzate
              qui sotto.
            </p>
            {picked.length > 0 && (
              <div className="install-selected">
                <strong>
                  {picked.length} file ·{" "}
                  {bytes(picked.reduce((sum, p) => sum + p.file.size, 0))}
                </strong>
                <p>
                  {picked
                    .slice(0, 4)
                    .map((p) => p.relative)
                    .join(" · ")}
                  {picked.length > 4 ? " …" : ""}
                </p>
                <button className="primary" disabled={!!busy} onClick={upload}>
                  {batch?.status === "draft"
                    ? "Riprendi upload e analizza"
                    : "Analizza selezione"}
                </button>
              </div>
            )}
            {busy.startsWith("Caricamento") && (
              <div role="status">
                <progress
                  value={uploadProgress.done}
                  max={uploadProgress.total || 1}
                />
                <p>
                  {uploadProgress.file} · {bytes(uploadProgress.done)} /{" "}
                  {bytes(uploadProgress.total)}
                </p>
                <button onClick={() => controller.current?.abort()}>
                  Interrompi upload
                </button>
              </div>
            )}
            <details className="local-picker">
              <summary>
                Usa le cartelle autorizzate sul PC · nessuna copia aggiuntiva
              </summary>
              <div className="actions">
                {roots.map((root) => (
                  <button key={root} onClick={() => browse(root)}>
                    {root}
                  </button>
                ))}
              </div>
              {!roots.length && (
                <p>
                  Configura una cartella in Avanzate → Impostazioni, oppure usa
                  Seleziona file.
                </p>
              )}
              {directory && (
                <>
                  <p className="path">{directory}</p>
                  <button
                    onClick={() =>
                      setLocalPaths((p) =>
                        Array.from(new Set([...p, directory])),
                      )
                    }
                  >
                    Seleziona questa cartella
                  </button>
                  <div className="source-list">
                    {sources.map((s) => (
                      <label key={s.path}>
                        <input
                          type="checkbox"
                          checked={localPaths.includes(s.path)}
                          onChange={(e) =>
                            setLocalPaths((p) =>
                              e.target.checked
                                ? [...p, s.path]
                                : p.filter((v) => v !== s.path),
                            )
                          }
                        />
                        <span>{s.name}</span>
                        {s.directory && (
                          <button onClick={() => browse(s.path)}>Apri</button>
                        )}
                      </label>
                    ))}
                  </div>
                </>
              )}
              {localPaths.length > 0 && (
                <button className="primary" disabled={!!busy} onClick={local}>
                  Analizza {localPaths.length} percorsi selezionati
                </button>
              )}
            </details>
          </section>
        </>
      )}
      <section className="install-summary">
        <div className="panel">
          <small>IN CODA / ANALISI</small>
          <strong>
            {(totals.ready || 0) +
              (totals.queued || 0) +
              (totals.preparing_sync || 0)}
          </strong>
        </div>
        <div className="panel">
          <small>DA VERIFICARE</small>
          <strong>{totals.awaiting_decision || 0}</strong>
        </div>
        <div className="panel">
          <small>TRASFERIMENTO / HASH</small>
          <strong>
            {(totals.transferring || 0) + (totals.verifying || 0)}
          </strong>
        </div>
        <div className="panel">
          <small>INSTALLATI</small>
          <strong>{totals.installed || 0}</strong>
        </div>
        <div className="panel">
          <small>ATTESA EMULATIONSTATION</small>
          <strong>{totals.pending_refresh || 0}</strong>
        </div>
        <div className="panel">
          <small>FALLITI</small>
          <strong>{totals.failed || 0}</strong>
        </div>
      </section>
      <p className="muted">
        <HardDrive size={16} />
        {device?.diagnostics.space
          ? `${bytes(device.diagnostics.space.free)} liberi · ${device.config.name} · ultima diagnostica`
          : "Lo spazio sul Raspberry verrà verificato durante il dry-run."}{" "}
        I contatori descrivono le operazioni, inclusi i tentativi ripetuti.
      </p>
      <div className="install-layout">
        <aside className="panel install-history">
          <h3>Installazioni</h3>
          <button
            onClick={() => {
              chooseBatch("");
              setPicked([]);
            }}
          >
            Nuova selezione
          </button>
          {summary.batches.map((b) => (
            <button
              className={batchId === b.id ? "active" : ""}
              key={b.id}
              onClick={() => chooseBatch(b.id)}
            >
              <strong>{new Date(b.created_at).toLocaleString("it-IT")}</strong>
              <span>
                {statusLabel[
                  b.control === "pause"
                    ? "paused"
                    : b.control === "cancel"
                      ? "cancelled"
                      : b.status
                ] || b.status}{" "}
                · {b.total} elementi
              </span>
            </button>
          ))}
          {!summary.batches.length && <p>Nessuna installazione avviata.</p>}
        </aside>
        <section className="panel install-results">
          {!batch ? (
            <div className="empty">
              <Gamepad2 size={40} />
              <h3>Una coda che ricorda il lavoro</h3>
              <p>
                Le operazioni restano disponibili dopo la chiusura del browser o
                il riavvio dell’app.
              </p>
            </div>
          ) : (
            <>
              <div className="section-heading">
                <h2>
                  {statusLabel[
                    batch.control === "pause"
                      ? "paused"
                      : batch.control === "cancel"
                        ? "cancelled"
                        : batch.status
                  ] || batch.status}
                </h2>
                <span>
                  {batch.mode === "local" ? "Solo PC" : "PC → Raspberry"}
                </span>
              </div>
              {batch.control !== "run" && (
                <p role="status">
                  {batch.control === "pause"
                    ? "Coda in pausa. L’operazione attiva si ferma al prossimo punto sicuro."
                    : "Coda annullata. I giochi già importati o pubblicati sono conservati."}
                </p>
              )}
              {batch.error.cause && (
                <div className="error">
                  {batch.error.cause}
                  <p>{batch.error.remedy}</p>
                </div>
              )}
              {batch.status === "scanning" && (
                <p>
                  <LoaderCircle className="spin" size={16} />
                  Analisi di {batch.progress.scanned_files || 0} /{" "}
                  {batch.progress.total_files || "…"} file
                </p>
              )}
              {batch.status === "draft" && (
                <p>
                  Upload incompleto. Riseleziona gli stessi file per riprendere:
                  i blocchi ricevuti vengono confrontati e non duplicati.
                </p>
              )}
              {!batch.authorized && batch.status === "preview" && (
                <div className="install-confirm">
                  <p>
                    {batch.counts.ready || 0} giochi pronti. I casi da
                    verificare resteranno in coda senza bloccare gli altri.
                  </p>
                  <label className="checkline">
                    <input
                      type="checkbox"
                      checked={rights}
                      onChange={(e) => setRights(e.target.checked)}
                    />
                    Confermo di poter utilizzare questi file. Autorizzo
                    importazione, immagini da fonti consentite e installazione
                    selezionata.
                  </label>
                  {batch.mode === "install" && (
                    <label className="checkline">
                      <input
                        type="checkbox"
                        checked={keepLocal}
                        onChange={(e) => setKeepLocal(e.target.checked)}
                      />
                      Se il Raspberry è offline, conserva l’importazione sul PC
                      e riprendi automaticamente.
                    </label>
                  )}
                  <button
                    className="primary"
                    disabled={!rights || !!busy}
                    onClick={() =>
                      perform("Avvio installazione", () =>
                        api(`/installations/${batch.id}/confirm`, "POST", {
                          confirmed: true,
                          rights_confirmed: true,
                          keep_local_when_offline: keepLocal,
                          enrich: true,
                        }),
                      )
                    }
                  >
                    {batch.mode === "local"
                      ? "Conferma importazione locale"
                      : "Installa automaticamente"}
                  </button>
                </div>
              )}
              {(batch.counts.pending_refresh || 0) > 0 && (
                <div className="install-notice">
                  <strong>Chiudi EmulationStation dalla console locale.</strong>
                  <p>
                    Le ROM sono verificate. Applicheremo automaticamente
                    metadati e raccolte quando risulta chiusa; riaprila
                    localmente quando questa coda non indica più metadati in
                    attesa.
                  </p>
                </div>
              )}
              <div className="actions">
                <button
                  onClick={() =>
                    control(batch.control === "pause" ? "resume" : "pause")
                  }
                >
                  {batch.control === "pause" ? "Riprendi" : "Pausa"}
                </button>
                <button onClick={() => control("retry")}>Riprova errori</button>
                <button onClick={() => control("cancel")}>Annulla coda</button>
                <select
                  aria-label="Filtro installazioni"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                >
                  <option value="">Tutti gli elementi della pagina</option>
                  <option value="awaiting_decision">Da verificare</option>
                  <option value="failed">Falliti</option>
                  <option value="installed">Installati</option>
                </select>
              </div>
              {batch.items
                .filter((i) => !filter || i.status === filter)
                .map((item) => (
                  <article className="install-item" key={item.id}>
                    <div className="install-thumb">
                      {item.cover_url ? (
                        <img src={item.cover_url} alt="" />
                      ) : (
                        <Gamepad2 size={26} />
                      )}
                    </div>
                    <div className="install-item-content">
                      <h3>{item.title}</h3>
                      <p>
                        {item.platform || "Piattaforma da identificare"} ·{" "}
                        {bytes(
                          item.candidate.size || item.identification.size || 0,
                        )}
                        {item.identification.duplicate &&
                          " · Già nella libreria: nessun duplicato creato"}
                      </p>
                      <strong className="install-state">
                        {statusLabel[item.status] || item.status}
                      </strong>
                      <p className="path">{item.source_key}</p>
                      {item.identification.basis && (
                        <p className="muted">{item.identification.basis}</p>
                      )}
                      <div className="install-evidence">
                        <span>
                          {item.pc_present ? "✓ PC" : "PC: non importato"}
                        </span>
                        <span>
                          {item.installed
                            ? "✓ File sul Raspberry verificati"
                            : "Raspberry: non verificato"}
                        </span>
                        <span>
                          {item.visibility === "operator_confirmed"
                            ? "✓ Visibile: conferma operatore"
                            : "Visibilità: da confermare localmente"}
                        </span>
                        <span>
                          {item.launched
                            ? "✓ Avvio già confermato"
                            : "Avvio: non verificato"}
                        </span>
                      </div>
                      {item.progress.sync?.file && (
                        <div>
                          <p>{item.progress.sync.file}</p>
                          {item.status === "verifying" ? (
                            <p>
                              Confronto SHA-256 del contenuto remoto in corso…
                            </p>
                          ) : (
                            <>
                              <progress
                                value={item.progress.sync.file_bytes || 0}
                                max={item.progress.sync.file_total || 1}
                              />
                              <small>
                                {bytes(item.progress.sync.bytes || 0)} /{" "}
                                {bytes(item.progress.sync.total || 0)}
                              </small>
                            </>
                          )}
                        </div>
                      )}
                      {item.progress.destination && (
                        <p className="muted">
                          Destinazione: {item.progress.destination}/
                          {item.platform} · Spazio rilevato:{" "}
                          {bytes(item.progress.free_bytes || 0)}
                        </p>
                      )}
                      {item.progress.preflight?.bios && (
                        <details>
                          <summary>
                            Core {item.progress.preflight.core} · Controllo BIOS
                          </summary>
                          {item.progress.preflight.bios.map((b) => (
                            <p key={b.name}>
                              {b.name}:{" "}
                              {b.verified
                                ? "disponibile, hash verificato"
                                : b.available
                                  ? "presente, hash non verificato"
                                  : "non presente (alternativa)"}
                            </p>
                          ))}
                        </details>
                      )}
                      {item.status === "awaiting_decision" && (
                        <div className="install-review">
                          <p>{item.identification.reason}</p>
                          <DecisionControls
                            item={item}
                            choose={(body) => {
                              void perform("Verifica identificazione", () =>
                                api(
                                  `/installations/items/${item.id}/decision`,
                                  "POST",
                                  body,
                                ),
                              );
                            }}
                          />
                          {item.identification.candidates?.map((c) => (
                            <details key={c.uid}>
                              <summary>
                                {c.title} · {c.core} · {c.matched_components}{" "}
                                componenti corrispondenti · {c.report.status}
                              </summary>
                              <ul>
                                {c.report.problems.map((p, index) => (
                                  <li key={index}>
                                    {p.set}/{p.file}: {p.reason}
                                  </li>
                                ))}
                              </ul>
                              <button
                                onClick={() =>
                                  perform("Verifica variante", () =>
                                    api(
                                      `/installations/items/${item.id}/decision`,
                                      "POST",
                                      {
                                        action: "choose",
                                        entry_uid: c.uid,
                                        archive_mode: c.mode,
                                      },
                                    ),
                                  )
                                }
                              >
                                Verifica questa variante
                              </button>
                            </details>
                          ))}
                          <button
                            onClick={() =>
                              perform("Esclusione elemento", () =>
                                api(
                                  `/installations/items/${item.id}/decision`,
                                  "POST",
                                  { action: "skip" },
                                ),
                              )
                            }
                          >
                            Salta questo elemento
                          </button>
                        </div>
                      )}
                      {item.error.cause && (
                        <div className="error">
                          <strong>
                            {item.error.phase}: {item.error.cause}
                          </strong>
                          <p>{item.error.remedy}</p>
                          <button
                            disabled={!!busy}
                            onClick={() =>
                              perform("Nuovo tentativo", () =>
                                api(
                                  `/installations/items/${item.id}/retry`,
                                  "POST",
                                ),
                              )
                            }
                          >
                            Riprova
                          </button>
                        </div>
                      )}
                      {item.warnings.length > 0 && (
                        <details>
                          <summary>Note sui metadati</summary>
                          {item.warnings.map((w, index) => (
                            <p key={index}>{w}</p>
                          ))}
                        </details>
                      )}
                      {item.status === "installed" &&
                        item.visibility !== "operator_confirmed" && (
                          <button
                            onClick={() =>
                              perform("Conferma visibilità", () =>
                                api(
                                  `/installations/items/${item.id}/visible`,
                                  "POST",
                                  { confirmed: true },
                                ),
                              )
                            }
                          >
                            <Check size={16} />
                            Lo vedo nel menu sulla console
                          </button>
                        )}
                    </div>
                  </article>
                ))}
              {batch.total > 40 && (
                <div className="actions">
                  <button
                    disabled={page === 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    Precedenti
                  </button>
                  <span>
                    Pagina {page} di {Math.ceil(batch.total / 40)}
                  </span>
                  <button
                    disabled={page * 40 >= batch.total}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Successivi
                  </button>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
