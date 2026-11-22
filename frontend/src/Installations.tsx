import { useCallback, useEffect, useRef, useState } from "react";
import {
  Check,
  ChevronDown,
  FolderOpen,
  Gamepad2,
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
export type Experience = {
  state: string;
  label: string;
  section: string;
  tone: string;
  phase: string;
  code: string;
  message: string;
  next_step: string;
  actions: string[];
  progress: {
    kind: "bytes" | "indeterminate" | "none" | "count";
    value?: number;
    total?: number;
  };
  files_verified: boolean;
  visibility: string;
  launched: boolean;
};
type ExperienceSummary = {
  identified: number;
  total: number;
  completed: number;
  active: number;
  intervention: number;
  blocked: number;
  operations: number;
  unresolved: number;
  scanning: boolean;
  current: (Experience & { id: string; batch_id: string; title: string })[];
  progress: Experience["progress"];
};
export function Progress({
  progress,
  label,
}: {
  progress: Experience["progress"];
  label: string;
}) {
  if (progress.kind === "none") return null;
  return (
    <div className="install-progress">
      <progress
        aria-label={label}
        {...(progress.kind === "indeterminate"
          ? {}
          : { value: progress.value || 0, max: progress.total || 1 })}
      />
      {progress.kind === "bytes" && (
        <small>
          {bytes(progress.value || 0)} / {bytes(progress.total || 0)}
        </small>
      )}
    </div>
  );
}
type Item = {
  id: string;
  experience: Experience;
  platform_label: string;
  companions?: Item[];
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
    variants?: { source: string; title: string }[];
    archive?: {
      original: string;
      extracted: boolean;
      members: number;
      expanded_bytes?: number;
      sha256?: string;
      contents?: string[];
      volumes?: string[];
      repacked_zip?: boolean;
    };
    associated_files?: string[];
    ignored_members?: { name: string; reason: string }[];
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
  cards: Item[];
  card_total: number;
  experience_summary: ExperienceSummary;
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
type Summary = {
  batches: Batch[];
  devices: Device[];
  experience_summary?: ExperienceSummary;
};
type Source = { name: string; path: string; directory: boolean };
type Picked = { file: File; relative: string };
export const statusLabel: Record<string, string> = {
  draft: "File da caricare",
  queued: "In attesa",
  scanning: "Analisi",
  identifying: "Riconoscimento",
  reanalyzing: "Rianalisi archivio",
  preview: "Anteprima pronta",
  ready: "Pronto",
  prepared: "Archivio preparato",
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

export default function Installations({
  view,
  onOpenLibrary,
}: {
  view: "add" | "queue";
  onOpenLibrary?: (id: number) => void;
}) {
  const [summary, setSummary] = useState<Summary>({ batches: [], devices: [] });
  const [batch, setBatch] = useState<Batch | null>(null);
  const [batchId, setBatchId] = useState(
    () => sessionStorage.getItem("rlm-installation-batch") || "",
  );
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
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("recent");
  const [technicalPage, setTechnicalPage] = useState(1);
  const [technicalItems, setTechnicalItems] = useState<Item[] | null>(null);
  const refreshing = useRef<Promise<void> | null>(null);
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const refresh = useCallback(() => {
    if (refreshing.current) return refreshing.current;
    const epoch = generation.current;
    const task = (async () => {
      const [result, detail] = await Promise.all([
        api<Summary>("/installations"),
        batchId
          ? api<Batch>(
              `/installations/${batchId}?page=${page}&page_size=40&section=${filter}&sort=${sort}`,
            )
          : Promise.resolve(null),
      ]);
      if (epoch !== generation.current) return;
      setSummary(result);
      setBatch(detail);
      setError((previous) =>
        previous.startsWith("Backend non disponibile:") ? "" : previous,
      );
    })();
    refreshing.current = task;
    void task
      .finally(() => {
        if (refreshing.current === task) refreshing.current = null;
      })
      .catch(() => {});
    return task;
  }, [batchId, page, filter, sort]);
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const epoch = ++generation.current;
    refreshing.current = null;
    const poll = async () => {
      try {
        await refresh();
      } catch (e) {
        if (alive)
          setError(
            `Backend non disponibile: ${String(e)}. La coda è conservata; riprovo automaticamente.`,
          );
      }
      if (alive)
        timer = setTimeout(() => void poll(), document.hidden ? 10000 : 2500);
    };
    void poll();
    return () => {
      alive = false;
      generation.current = epoch + 1;
      clearTimeout(timer);
    };
  }, [refresh]);
  useEffect(() => {
    sessionStorage.setItem("rlm-installation-batch", batchId);
  }, [batchId]);
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
    setTechnicalPage(1);
    setTechnicalItems(null);
    setFilter("all");
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
  const totals = summary.experience_summary;
  const activeJob = totals?.current[0];
  return (
    <div className="installations">
      <section
        className="panel install-overview"
        aria-label="Avanzamento installazioni"
      >
        <div className="section-heading">
          <strong>
            {totals?.active || totals?.scanning
              ? "Installazione in lavorazione"
              : "Stato delle installazioni"}
          </strong>
          <span>
            {totals?.operations || 0} operazioni · {totals?.identified || 0}{" "}
            giochi identificati · {totals?.total || 0} copie distinte
          </span>
        </div>
        <div className="install-counters" aria-live="polite">
          <span>
            <b>{totals?.completed || 0}</b> completati
          </span>
          <span>
            <b>{totals?.active || 0}</b> in corso
          </span>
          <span>
            <b>{totals?.intervention || 0}</b> richiedono intervento
          </span>
          <span>
            <b>{totals?.blocked || 0}</b> bloccati
          </span>
        </div>
        {busy === "Caricamento della selezione" ? (
          <>
            <p>Caricamento dei file sul PC · {uploadProgress.file}</p>
            <Progress
              progress={{
                kind: "bytes",
                value: uploadProgress.done,
                total: uploadProgress.total,
              }}
              label="Caricamento della selezione"
            />
          </>
        ) : (
          <>
            <p className="install-current">
              {activeJob
                ? `${activeJob.phase} · ${activeJob.title}`
                : totals?.scanning
                  ? "Analisi della selezione: il numero di giochi sarà noto al termine."
                  : `${totals?.completed || 0} di ${totals?.total || 0} copie con operazione completata`}
            </p>
            {totals && (
              <Progress
                progress={totals.progress}
                label="Avanzamento complessivo"
              />
            )}
            {activeJob?.progress.kind === "bytes" && (
              <Progress
                progress={activeJob.progress}
                label="Trasferimento corrente"
              />
            )}
          </>
        )}
        {(totals?.current.length || 0) > 1 && (
          <details>
            <summary>Operazioni concorrenti ({totals?.current.length})</summary>
            {totals?.current.map((current) => (
              <p key={current.id}>
                <button onClick={() => chooseBatch(current.batch_id)}>
                  {current.title} · {current.phase}
                </button>
              </p>
            ))}
          </details>
        )}
        {!!totals?.unresolved && (
          <small>
            {totals.unresolved} copie ancora da identificare: non vengono unite
            per somiglianza del titolo.
          </small>
        )}
      </section>
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
        <details className="install-selection" open={!batch}>
          <summary>Seleziona ZIP, RAR, 7z, file o cartelle</summary>
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
              <h3>Trascina ZIP, RAR, 7z, file o cartelle</h3>
              <p>
                Preparo automaticamente i giochi contenuti negli archivi,
                inclusi BIN/CUE. Per archivi suddivisi, seleziona tutti i
                volumi. Non serve estrarli: gli originali restano invariati.
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
        </details>
      )}
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
                · {b.experience_summary?.total || 0} giochi ·{" "}
                {b.experience_summary?.operations || 0} operazioni
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
                <details className="install-notice">
                  <summary>
                    La selezione si è fermata. Mostra la causa e le indicazioni.
                  </summary>
                  {batch.error.cause}
                  <p>{batch.error.remedy}</p>
                </details>
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
              <div className="actions install-batch-controls">
                {batch.control !== "run" && (
                  <button onClick={() => control("resume")}>Riprendi</button>
                )}
                {batch.experience_summary.active > 0 &&
                  batch.control === "run" && (
                    <>
                      <button onClick={() => control("pause")}>Pausa</button>
                      <button onClick={() => control("cancel")}>
                        Annulla coda
                      </button>
                    </>
                  )}
                <label>
                  Ordina{" "}
                  <select
                    aria-label="Ordina installazioni"
                    value={sort}
                    onChange={(e) => {
                      setSort(e.target.value);
                      setPage(1);
                    }}
                  >
                    <option value="recent">Più recenti</option>
                    <option value="title">Titolo</option>
                    <option value="status">Stato</option>
                  </select>
                </label>
              </div>
              <nav className="install-tabs" aria-label="Sezioni installazioni">
                {[
                  ["active", "In corso"],
                  ["attention", "Serve intervento"],
                  ["completed", "Completati"],
                  ["all", "Tutti"],
                ].map(([key, label]) => (
                  <button
                    key={key}
                    aria-current={filter === key ? "page" : undefined}
                    onClick={() => {
                      setFilter(key);
                      setPage(1);
                    }}
                  >
                    {label}
                  </button>
                ))}
              </nav>
              <p className="muted">
                {batch.card_total} schede · {batch.experience_summary.total}{" "}
                copie distinte in questa selezione ·{" "}
                {batch.experience_summary.operations} operazioni
              </p>
              {batch.cards.map((item) => (
                <article
                  className={`install-item tone-${item.experience.tone}`}
                  key={item.id}
                >
                  <details className="install-card">
                    <summary className="install-card-summary">
                      <span className="install-thumb">
                        {item.cover_url ? (
                          <img src={item.cover_url} alt="" />
                        ) : (
                          <Gamepad2 size={22} />
                        )}
                      </span>
                      <span className="install-card-title">
                        <h3>{item.title}</h3>
                        <span>
                          {item.platform_label || "Console da identificare"}
                        </span>
                      </span>
                      <span className="install-card-status">
                        <strong>{item.experience.label}</strong>
                        {item.experience.state === "working" && (
                          <small>{item.experience.phase}</small>
                        )}
                        {item.experience.state === "console_update" && (
                          <small>
                            File verificati · aggiornamento titoli in attesa
                          </small>
                        )}
                      </span>
                      <ChevronDown className="install-chevron" size={18} />
                      {item.experience.state === "working" && (
                        <Progress
                          progress={item.experience.progress}
                          label={`Avanzamento ${item.title}`}
                        />
                      )}
                    </summary>
                    <div className="install-item-content">
                      <div className="install-guidance">
                        <strong>{item.experience.message}</strong>
                        <p>{item.experience.next_step}</p>
                      </div>
                      <div className="actions">
                        {view === "add" &&
                          item.experience.actions.includes("replace") && (
                            <button
                              onClick={() => {
                                chooseBatch("");
                                setPicked([]);
                                fileInput.current?.click();
                              }}
                            >
                              Seleziona una copia corretta
                            </button>
                          )}
                        {item.experience.actions.includes("library") &&
                          item.game_id && (
                            <button
                              onClick={() => onOpenLibrary?.(item.game_id!)}
                            >
                              Apri nella libreria
                            </button>
                          )}
                        {item.experience.actions.includes("pause") && (
                          <button onClick={() => control("pause")}>
                            Pausa
                          </button>
                        )}
                        {item.experience.actions.includes("cancel") && (
                          <button onClick={() => control("cancel")}>
                            Annulla
                          </button>
                        )}
                        {item.experience.actions.includes("resume") && (
                          <button onClick={() => control("resume")}>
                            Riprendi
                          </button>
                        )}
                        {item.experience.actions.includes("retry") && (
                          <button
                            disabled={!!busy}
                            onClick={() =>
                              perform("Nuovo piano verificato", () =>
                                api(
                                  `/installations/items/${item.id}/retry`,
                                  "POST",
                                ),
                              )
                            }
                          >
                            {item.experience.code === "metadata_changed"
                              ? "Aggiorna piano"
                              : item.experience.code === "metadata_review"
                                ? "Aggiorna metadati"
                                : "Riprova"}
                          </button>
                        )}
                      </div>
                      {item.experience.actions.includes("metadata_review") && (
                        <button
                          onClick={() =>
                            perform("Segnalazione metadati", () =>
                              api(
                                `/installations/items/${item.id}/visible`,
                                "POST",
                                { confirmed: true, metadata_review: true },
                              ),
                            )
                          }
                        >
                          Lo vedo, ma titolo o immagine sono da correggere
                        </button>
                      )}
                      {item.experience.actions.includes("resolve") && (
                        <h4>Risolvi problema</h4>
                      )}
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
                        <details>
                          <summary>
                            Ultimo trasferimento · dati diagnostici
                          </summary>
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
                        </details>
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
                      {item.identification.archive && (
                        <details>
                          <summary>
                            Mostra dettagli archivio ·{" "}
                            {item.identification.archive.members} membri
                          </summary>
                          <p className="path">
                            Originale: {item.identification.archive.original}
                          </p>
                          <p>
                            {item.identification.archive.extracted
                              ? "File preparati automaticamente; originale conservato"
                              : "Archivio originale conservato; il set viene verificato prima dell’installazione"}
                          </p>
                          {item.identification.archive.repacked_zip && (
                            <p>
                              Set verificato tramite DAT e preparato in ZIP per
                              il core.
                            </p>
                          )}
                          {!!item.identification.archive.volumes?.length && (
                            <p>
                              Volumi:{" "}
                              {item.identification.archive.volumes.join(", ")}
                            </p>
                          )}
                          {item.identification.archive.expanded_bytes !==
                            undefined && (
                            <p>
                              Dimensione preparata:{" "}
                              {bytes(
                                item.identification.archive.expanded_bytes,
                              )}
                            </p>
                          )}
                          {item.identification.archive.contents?.map((name) => (
                            <p className="path" key={name}>
                              {name}
                            </p>
                          ))}
                          {item.identification.ignored_members?.map((m) => (
                            <p key={m.name}>
                              {m.name}: {m.reason}
                            </p>
                          ))}
                          {item.identification.associated_files?.length ? (
                            <p>
                              File associati rilevati:{" "}
                              {item.identification.associated_files.join(", ")}
                            </p>
                          ) : null}
                        </details>
                      )}
                      {item.identification.kind === "archive_container" && (
                        <p>{item.identification.reason}</p>
                      )}
                      {item.experience.actions.includes("reanalyze") && (
                        <button
                          disabled={!!busy}
                          onClick={() =>
                            perform("Rianalisi", () =>
                              api(
                                `/installations/items/${item.id}/reanalyze`,
                                "POST",
                              ),
                            )
                          }
                        >
                          Rianalizza
                        </button>
                      )}
                      {item.status === "awaiting_decision" && (
                        <div className="install-review">
                          <p>{item.identification.reason}</p>
                          {item.identification.variants?.map((variant) => (
                            <button
                              key={variant.source}
                              disabled={!!busy}
                              onClick={() =>
                                perform("Selezione versione", () =>
                                  api(
                                    `/installations/items/${item.id}/decision`,
                                    "POST",
                                    {
                                      action: "choose",
                                      variant_source: variant.source,
                                    },
                                  ),
                                )
                              }
                            >
                              Installa {variant.title}
                            </button>
                          ))}
                          {item.experience.code === "identity" && (
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
                          )}
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
                                disabled={
                                  !item.experience.actions.includes(
                                    "resolve",
                                  ) || c.report.status !== "complete"
                                }
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
                      {item.experience.actions.includes("visible") && (
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
                      <details>
                        <summary>Diagnostica completa</summary>
                        <pre className="install-json">
                          {JSON.stringify(item, null, 2)}
                        </pre>
                      </details>
                    </div>
                  </details>
                </article>
              ))}
              {!batch.card_total && <p>Nessun gioco in questa sezione.</p>}
              <details className="install-accessories">
                <summary>
                  Archivi, file accessori e cronologia tecnica ({batch.total}{" "}
                  elementi)
                </summary>
                <pre className="install-json">
                  {JSON.stringify(technicalItems || batch.items, null, 2)}
                </pre>
                {batch.total > 40 && (
                  <div className="actions">
                    <button
                      disabled={technicalPage === 1 || !!busy}
                      onClick={() =>
                        perform("Cronologia tecnica", async () => {
                          const next = technicalPage - 1;
                          const result = await api<Batch>(
                            `/installations/${batch.id}?page=${next}&page_size=40`,
                          );
                          setTechnicalItems(result.items);
                          setTechnicalPage(next);
                        })
                      }
                    >
                      File precedenti
                    </button>
                    <span>
                      File · pagina {technicalPage} di{" "}
                      {Math.ceil(batch.total / 40)}
                    </span>
                    <button
                      disabled={technicalPage * 40 >= batch.total || !!busy}
                      onClick={() =>
                        perform("Cronologia tecnica", async () => {
                          const next = technicalPage + 1;
                          const result = await api<Batch>(
                            `/installations/${batch.id}?page=${next}&page_size=40`,
                          );
                          setTechnicalItems(result.items);
                          setTechnicalPage(next);
                        })
                      }
                    >
                      Altri file
                    </button>
                  </div>
                )}
              </details>
              {batch.card_total > 40 && (
                <div className="actions">
                  <button
                    disabled={page === 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    Precedenti
                  </button>
                  <span>
                    Pagina {page} di {Math.ceil(batch.card_total / 40)}
                  </span>
                  <button
                    disabled={page * 40 >= batch.card_total}
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
