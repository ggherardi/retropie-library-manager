import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine,
  ExternalLink,
  Gamepad2,
  RefreshCw,
  X,
} from "lucide-react";
import { api, bytes, waitForJob, type Job } from "./api";
import { saveReport } from "./intelligence-api";

type Filters = {
  q: string;
  platforms: string[];
  sources: string[];
  licenses: string[];
  genre: string;
  available_only: boolean;
};
type Config = {
  target_bytes: number;
  reserved_bytes: number;
  filesystem_margin_percent: number;
  concurrency: number;
  automatic_filters: Filters;
  automatic_max_bytes: number;
  exclude_duplicates: boolean;
};
type Source = {
  id: string;
  name: string;
  status: string;
  message: string;
  count?: number;
  url?: string;
  updated_at?: string;
};
type Entry = {
  id: string;
  title: string;
  platform: string;
  author: string | null;
  year: number | null;
  genre: string | null;
  description: string | null;
  license: string | null;
  size: number | null;
  source_url: string;
  downloadable: boolean;
  available: boolean;
  reason: string;
  state: string;
  queue_status: string | null;
  cover_available: boolean;
  payload: { evidence: { url: string; assets_license?: string } };
};
type Storage = {
  library_bytes: number;
  pending_bytes: number;
  selected_bytes: number;
  target_bytes: number;
  usable_bytes: number;
  reserved_bytes: number;
  estimated_export_bytes: number;
  disk_free_bytes: number;
  warnings: string[];
};
type Plan = {
  id: string;
  count: number;
  files: number;
  bytes: number;
  concurrency: number;
  can_confirm: boolean;
  skipped: Record<string, number>;
  entries: { id: string; title: string }[];
  storage: Storage;
};
type Enrichment = {
  matches: {
    game_id: number;
    title: string;
    changes: Record<string, unknown>;
    cover_available: boolean;
    cover_error: string | null;
  }[];
  unresolved: { game_id: number; reason: string }[];
  applied: boolean;
};
type Download = {
  id: string;
  status: string;
  received: number;
  total: number;
  attempts: number;
  error: string;
  sha256: string | null;
  game_id: number | null;
  snapshot: Entry;
};
const emptyFilters: Filters = {
  q: "",
  platforms: [],
  sources: [],
  licenses: [],
  genre: "",
  available_only: false,
};
const labels: Record<string, string> = {
  imported: "Importato",
  downloaded: "Scaricato",
  available: "Disponibile",
  unsupported: "Non supportato",
  queued: "In coda",
  running: "Download in corso",
  verifying: "Verifica integrità",
  retry_wait: "Attesa retry",
  paused: "In pausa",
  cancelled: "Annullato",
  failed: "Errore",
  ready: "Aggiornato",
  refreshing: "Aggiornamento",
  idle: "Da aggiornare",
  error: "Errore provider",
  link_only: "Pagina originale",
};

function sourceLink(url: string) {
  return /^https?:\/\//i.test(url);
}

export default function Discovery({
  view,
  platforms,
  onDownloads,
  onChanged,
}: {
  view: "discovery" | "downloads";
  platforms: Record<string, string>;
  onDownloads: () => void;
  onChanged: () => Promise<void>;
}) {
  const dialog = useRef<HTMLElement>(null);
  const importedCount = useRef(0);
  const [sources, setSources] = useState<Source[]>([]);
  const [facets, setFacets] = useState<{
    licenses: string[];
    genres: string[];
  }>({ licenses: [], genres: [] });
  const [config, setConfig] = useState<Config | null>(null);
  const [storage, setStorage] = useState<Storage | null>(null);
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("title");
  const [selected, setSelected] = useState<string[]>([]);
  const [allFiltered, setAllFiltered] = useState(false);
  const [mode, setMode] = useState<"manual" | "automatic">("manual");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [enrichment, setEnrichment] = useState<Enrichment | null>(null);
  const [downloads, setDownloads] = useState<Download[]>([]);
  const [downloadTotal, setDownloadTotal] = useState(0);
  const [downloadPage, setDownloadPage] = useState(1);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);

  const refresh = useCallback(async () => {
    const [providers, options, space, queue] = await Promise.all([
      api<Source[]>("/discovery/providers"),
      api<typeof facets>("/discovery/facets"),
      api<Storage>("/acquisition/storage"),
      api<{ items: Download[]; counts: Record<string, number>; total: number }>(
        `/downloads?page=${downloadPage}`,
      ),
    ]);
    setSources(providers);
    setFacets(options);
    setStorage(space);
    setDownloads(queue.items);
    setCounts(queue.counts);
    setDownloadTotal(queue.total);
  }, [downloadPage]);
  useEffect(() => {
    api<Config>("/acquisition/settings")
      .then(setConfig)
      .catch((e) => setError(String(e)));
  }, []);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        if (active) await refresh();
      } catch (e) {
        if (active) setError(String(e));
      }
      if (active) timer = setTimeout(poll, 1500);
    }
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [refresh]);
  useEffect(() => {
    const count = counts.imported || 0;
    if (count !== importedCount.current) {
      importedCount.current = count;
      onChanged().catch((e) => setError(String(e)));
    }
  }, [counts.imported, onChanged]);
  useEffect(() => {
    if (!plan || !dialog.current) return;
    const previous = document.activeElement as HTMLElement | null;
    dialog.current.focus();
    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape") setPlan(null);
      if (event.key !== "Tab") return;
      const controls = Array.from(
        dialog.current?.querySelectorAll<HTMLElement>(
          "button:not(:disabled), a[href], summary, input, select, textarea",
        ) || [],
      ).filter((element) => element.offsetParent !== null);
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (
        event.shiftKey &&
        (document.activeElement === first ||
          document.activeElement === dialog.current)
      ) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      previous?.focus();
    };
  }, [plan]);
  const sourceRevision = sources
    .map((s) => `${s.id}:${s.updated_at ?? ""}`)
    .join("|");
  useEffect(() => {
    if (view !== "discovery") return;
    let active = true;
    const timer = setTimeout(() => {
      setLoading(true);
      api<{ items: Entry[]; total: number }>(
        `/discovery/search?page=${page}&sort=${sort}`,
        "POST",
        filters,
      )
        .then((result) => {
          if (active) {
            setEntries(result.items);
            setTotal(result.total);
          }
        })
        .catch((e) => {
          if (active) setError(String(e));
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 200);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [
    view,
    filters,
    page,
    sort,
    sourceRevision,
    refreshVersion,
    counts.imported,
  ]);

  async function action(label: string, operation: () => Promise<void>) {
    setBusy(label);
    setError("");
    setNotice("");
    try {
      await operation();
      await refresh();
      await onChanged();
      setRefreshVersion((v) => v + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }
  function filter(update: Partial<Filters>) {
    setFilters({ ...filters, ...update });
    setPage(1);
    setAllFiltered(false);
    setSelected([]);
    setPlan(null);
  }
  function toggle(id: string) {
    setAllFiltered(false);
    setSelected(
      selected.includes(id)
        ? selected.filter((v) => v !== id)
        : [...selected, id],
    );
  }
  async function enrich(apply: boolean) {
    const queued = await api<Job>("/metadata/enrich", "POST", {
      apply,
      covers: true,
      game_ids: apply ? enrichment?.matches.map((m) => m.game_id) : [],
    });
    const result = await waitForJob<Enrichment>(queued.id, () =>
      setBusy("Confronto degli hash e metadati in corso"),
    );
    setEnrichment(result.result);
    if (apply)
      setNotice(
        "Arricchimento completato. I campi già compilati sono stati conservati.",
      );
  }
  function multi(values: string[], value: string) {
    return values.includes(value)
      ? values.filter((v) => v !== value)
      : [...values, value];
  }
  const configForm = config && (
    <details className="panel">
      <summary>Capacità RetroPie e regole automatiche</summary>
      <div className="form-grid">
        <label>
          Capacità nominale microSD · GB
          <input
            type="number"
            min={1}
            value={config.target_bytes / 1e9}
            onChange={(e) =>
              setConfig({
                ...config,
                target_bytes: Math.round(Number(e.target.value) * 1e9),
              })
            }
          />
        </label>
        <label>
          Riserva sistema operativo · GB
          <input
            type="number"
            min={0}
            step={0.5}
            value={config.reserved_bytes / 1e9}
            onChange={(e) =>
              setConfig({
                ...config,
                reserved_bytes: Math.round(Number(e.target.value) * 1e9),
              })
            }
          />
        </label>
        <label>
          Margine filesystem · %
          <input
            type="number"
            min={0}
            max={30}
            value={config.filesystem_margin_percent}
            onChange={(e) =>
              setConfig({
                ...config,
                filesystem_margin_percent: Number(e.target.value),
              })
            }
          />
        </label>
        <label>
          Download simultanei
          <input
            type="number"
            min={1}
            max={8}
            value={config.concurrency}
            onChange={(e) =>
              setConfig({ ...config, concurrency: Number(e.target.value) })
            }
          />
        </label>
        <label>
          Budget per esecuzione automatica · GB
          <input
            type="number"
            min={0.001}
            step={0.1}
            value={config.automatic_max_bytes / 1e9}
            onChange={(e) =>
              setConfig({
                ...config,
                automatic_max_bytes: Math.round(Number(e.target.value) * 1e9),
              })
            }
          />
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={config.exclude_duplicates}
            onChange={(e) =>
              setConfig({ ...config, exclude_duplicates: e.target.checked })
            }
          />
          Escludi duplicati dalla selezione
        </label>
      </div>
      <fieldset>
        <legend>Piattaforme automatiche</legend>
        <div className="check-grid">
          {Object.entries(platforms).map(([id, name]) => (
            <label className="checkbox-label" key={id}>
              <input
                type="checkbox"
                checked={config.automatic_filters.platforms.includes(id)}
                onChange={() =>
                  setConfig({
                    ...config,
                    automatic_filters: {
                      ...config.automatic_filters,
                      platforms: multi(config.automatic_filters.platforms, id),
                    },
                  })
                }
              />
              {name}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend>Fonti automatiche autorizzate</legend>
        <div className="check-grid">
          {sources
            .filter((s) => s.status !== "link_only")
            .map((s) => (
              <label className="checkbox-label" key={s.id}>
                <input
                  type="checkbox"
                  checked={config.automatic_filters.sources.includes(s.id)}
                  onChange={() =>
                    setConfig({
                      ...config,
                      automatic_filters: {
                        ...config.automatic_filters,
                        sources: multi(config.automatic_filters.sources, s.id),
                      },
                    })
                  }
                />
                {s.name}
              </label>
            ))}
        </div>
      </fieldset>
      <label>
        Licenze ammesse · selezione multipla
        <select
          multiple
          size={Math.min(6, Math.max(2, facets.licenses.length))}
          value={config.automatic_filters.licenses}
          onChange={(e) =>
            setConfig({
              ...config,
              automatic_filters: {
                ...config.automatic_filters,
                licenses: Array.from(e.target.selectedOptions, (o) => o.value),
              },
            })
          }
        >
          {facets.licenses.map((l) => (
            <option key={l}>{l}</option>
          ))}
        </select>
      </label>
      <button
        disabled={!!busy}
        onClick={() =>
          void action("Salvataggio configurazione", async () => {
            await api("/acquisition/settings", "PUT", config);
            setNotice("Configurazione acquisizione salvata.");
          })
        }
      >
        Salva configurazione
      </button>
    </details>
  );

  return (
    <>
      {error && (
        <div className="message error" role="alert">
          {error}
          <button
            aria-label="Chiudi errore Discovery"
            onClick={() => setError("")}
          >
            <X size={16} />
          </button>
        </div>
      )}
      {busy && (
        <div className="message" role="status">
          {busy}
        </div>
      )}
      {notice && (
        <div className="message success" role="status">
          {notice}
        </div>
      )}
      {storage && (
        <section className="stat-grid">
          <div className="stat">
            <div>Libreria</div>
            <strong>{bytes(storage.library_bytes)}</strong>
          </div>
          <div className="stat">
            <div>In coda / riservato</div>
            <strong>{bytes(storage.pending_bytes)}</strong>
          </div>
          <div className="stat">
            <div>Capacità RetroPie utile</div>
            <strong>{bytes(storage.usable_bytes)}</strong>
          </div>
          <div className="stat">
            <div>Importazioni completate</div>
            <strong>{counts.imported || 0}</strong>
          </div>
        </section>
      )}
      {storage?.warnings.map((w) => (
        <div className="message error" role="alert" key={w}>
          {w}
        </div>
      ))}
      {view === "discovery" && (
        <>
          <details className="panel" open={total === 0}>
            <summary>Stato dei provider</summary>
            <div className="provider-grid">
              {sources.map((s) => (
                <article key={s.id} className="provider-card">
                  <strong>{s.name}</strong>
                  <span className="status">{labels[s.status] || s.status}</span>
                  <p>
                    {s.message || "Aggiorna il catalogo per cercare giochi."}
                  </p>
                  {s.count !== undefined && (
                    <p>{s.count} giochi nel catalogo locale</p>
                  )}
                  {s.url ? (
                    <a href={s.url} target="_blank" rel="noreferrer">
                      Apri fonte originale <ExternalLink size={13} />
                    </a>
                  ) : (
                    !s.id.startsWith("manifest-") && (
                      <button
                        disabled={s.status === "refreshing" || !!busy}
                        onClick={() =>
                          void action("Avvio aggiornamento", async () => {
                            await api(
                              `/discovery/providers/${s.id}/refresh`,
                              "POST",
                            );
                          })
                        }
                      >
                        <RefreshCw size={15} />
                        Aggiorna {s.id}
                      </button>
                    )
                  )}
                </article>
              ))}
            </div>
          </details>
          <div className="mode-switch">
            <button
              className={mode === "manual" ? "primary" : ""}
              onClick={() => {
                setMode("manual");
                setPlan(null);
              }}
            >
              Selezione manuale
            </button>
            <button
              className={mode === "automatic" ? "primary" : ""}
              onClick={() => {
                setMode("automatic");
                setPlan(null);
              }}
            >
              Selezione automatica
            </button>
          </div>
          {configForm}
          {mode === "manual" ? (
            <>
              <div className="discovery-filters">
                <label>
                  Cerca giochi
                  <input
                    value={filters.q}
                    onChange={(e) => filter({ q: e.target.value })}
                    placeholder="Titolo…"
                  />
                </label>
                <label>
                  Piattaforma
                  <select
                    value={filters.platforms[0] || ""}
                    onChange={(e) =>
                      filter({
                        platforms: e.target.value ? [e.target.value] : [],
                      })
                    }
                  >
                    <option value="">Tutte</option>
                    {Object.entries(platforms).map(([id, name]) => (
                      <option value={id} key={id}>
                        {name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Fonte
                  <select
                    value={filters.sources[0] || ""}
                    onChange={(e) =>
                      filter({
                        sources: e.target.value ? [e.target.value] : [],
                      })
                    }
                  >
                    <option value="">Tutte</option>
                    {sources
                      .filter((s) => s.status !== "link_only")
                      .map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))}
                  </select>
                </label>
                <label>
                  Licenza
                  <select
                    value={filters.licenses[0] || ""}
                    onChange={(e) =>
                      filter({
                        licenses: e.target.value ? [e.target.value] : [],
                      })
                    }
                  >
                    <option value="">Tutte</option>
                    {facets.licenses.map((l) => (
                      <option key={l}>{l}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Genere
                  <select
                    value={filters.genre}
                    onChange={(e) => filter({ genre: e.target.value })}
                  >
                    <option value="">Tutti</option>
                    {facets.genres.map((g) => (
                      <option key={g}>{g}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Ordina
                  <select
                    value={sort}
                    onChange={(e) => {
                      setSort(e.target.value);
                      setPage(1);
                    }}
                  >
                    <option value="title">Titolo A–Z</option>
                    <option value="title_desc">Titolo Z–A</option>
                    <option value="size">Dimensione</option>
                    <option value="year">Anno recente</option>
                  </select>
                </label>
              </div>
              <div className="selection-bar">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={filters.available_only}
                    onChange={(e) =>
                      filter({ available_only: e.target.checked })
                    }
                  />
                  Solo download autorizzati e supportati
                </label>
                <span>{total} risultati</span>
                <button
                  onClick={() => {
                    setAllFiltered(true);
                    setSelected([]);
                  }}
                >
                  Seleziona tutti i risultati filtrati
                </button>
                <button
                  onClick={() => {
                    setAllFiltered(false);
                    setSelected([]);
                  }}
                >
                  Azzera
                </button>
              </div>
              {loading ? (
                <p role="status">Caricamento catalogo…</p>
              ) : entries.length ? (
                <div className="game-grid discovery-grid">
                  {entries.map((entry) => (
                    <article className="game" key={entry.id}>
                      <div className={`cover console-${entry.platform}`}>
                        {entry.cover_available ? (
                          <img
                            loading="lazy"
                            src={`/api/discovery/${entry.id}/cover`}
                            alt={`Immagine di ${entry.title}`}
                            onError={(e) => {
                              e.currentTarget.style.display = "none";
                            }}
                          />
                        ) : (
                          <Gamepad2 size={48} strokeWidth={1} />
                        )}
                        <label className="select-game">
                          <input
                            type="checkbox"
                            aria-label={`Seleziona download ${entry.title}`}
                            checked={allFiltered || selected.includes(entry.id)}
                            disabled={!entry.downloadable || !entry.available}
                            onChange={() => toggle(entry.id)}
                          />
                        </label>
                        <span className="discovery-state">
                          {labels[entry.state]}
                        </span>
                      </div>
                      <div className="discovery-info">
                        <div className="eyebrow">
                          {platforms[entry.platform] ||
                            "Piattaforma sconosciuta"}
                        </div>
                        <h3>{entry.title}</h3>
                        <p>
                          {entry.author || "Autore sconosciuto"} ·{" "}
                          {entry.year || "Anno sconosciuto"}
                        </p>
                        <p>
                          {entry.genre || "Genere sconosciuto"} ·{" "}
                          {entry.size === null
                            ? "Dimensione sconosciuta"
                            : bytes(entry.size)}
                        </p>
                        <p>{entry.license || "Licenza sconosciuta"}</p>
                        {entry.queue_status && (
                          <p className="success-text">
                            {labels[entry.queue_status]}
                          </p>
                        )}
                        <details>
                          <summary>Descrizione e condizioni</summary>
                          <p>
                            {entry.description ||
                              "Descrizione non disponibile."}
                          </p>
                          {entry.reason && <p>{entry.reason}</p>}
                          <p>
                            Licenza asset ·{" "}
                            {entry.payload.evidence.assets_license ||
                              "Sconosciuta"}
                          </p>
                          {sourceLink(entry.payload.evidence.url) && (
                            <a
                              href={entry.payload.evidence.url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Dichiarazione della fonte
                            </a>
                          )}
                        </details>
                        {sourceLink(entry.source_url) && (
                          <a
                            href={entry.source_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Fonte originale <ExternalLink size={13} />
                          </a>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="empty">
                  <Gamepad2 size={40} />
                  <h2>Nessun titolo per questi filtri</h2>
                  <p>
                    Aggiorna un provider o aggiungi un manifest nelle Sorgenti e
                    download.
                  </p>
                </div>
              )}
              {total > 24 && (
                <div className="pagination">
                  <button
                    disabled={page === 1}
                    onClick={() => setPage(page - 1)}
                  >
                    Precedente
                  </button>
                  <span>
                    {page} / {Math.ceil(total / 24)}
                  </span>
                  <button
                    disabled={page * 24 >= total}
                    onClick={() => setPage(page + 1)}
                  >
                    Successiva
                  </button>
                </div>
              )}
            </>
          ) : (
            <section className="panel">
              <h2>Acquisizione secondo le tue regole</h2>
              <p>
                Apri la configurazione per scegliere piattaforme, fonti, licenze
                e budget. Il riepilogo verrà calcolato sul catalogo locale
                aggiornato.
              </p>
              <p>Ogni esecuzione richiede una conferma esplicita.</p>
            </section>
          )}
          <div className="acquisition-action">
            <span>
              {mode === "manual"
                ? allFiltered
                  ? `${total} risultati da valutare`
                  : `${selected.length} titoli selezionati`
                : "Selezione secondo le regole salvate"}
            </span>
            <button
              className="primary"
              disabled={
                !!busy ||
                (mode === "manual" && !allFiltered && !selected.length)
              }
              onClick={() =>
                void action("Preparazione riepilogo", async () => {
                  if (mode === "automatic" && config)
                    await api("/acquisition/settings", "PUT", config);
                  setPlan(
                    await api<Plan>("/acquisition/plans", "POST", {
                      mode,
                      ids: selected,
                      all_filtered: allFiltered,
                      filters,
                    }),
                  );
                })
              }
            >
              <ArrowDownToLine size={17} />
              Prepara riepilogo
            </button>
          </div>
          <section className="panel">
            <h2>Arricchisci la libreria importata</h2>
            <p className="muted">
              Confronto tramite hash verificati. Le corrispondenze ambigue
              vengono segnalate. I campi già compilati mantengono le tue
              correzioni.
            </p>
            <button
              disabled={!!busy}
              onClick={() =>
                void action("Analisi metadati", () => enrich(false))
              }
            >
              Anteprima arricchimento
            </button>
            {enrichment && (
              <>
                <p>
                  {enrichment.matches.length} corrispondenze certe ·{" "}
                  {enrichment.unresolved.length} giochi da verificare
                </p>
                <details>
                  <summary>Esamina corrispondenze e segnalazioni</summary>
                  <pre>{JSON.stringify(enrichment, null, 2)}</pre>
                </details>
                {!enrichment.applied && (
                  <button
                    disabled={!!busy || !enrichment.matches.length}
                    onClick={() =>
                      void action("Arricchimento", () => enrich(true))
                    }
                  >
                    Applica metadati e copertine autorizzate
                  </button>
                )}
              </>
            )}
          </section>
        </>
      )}
      {view === "downloads" && (
        <>
          {configForm}
          <section className="panel">
            <h2>Download Manager</h2>
            <button
              onClick={() =>
                void action("Report acquisizioni", async () =>
                  saveReport(
                    await api("/downloads/report"),
                    "report-acquisizioni.json",
                  ),
                )
              }
            >
              Esporta report dei file acquisiti
            </button>
            <p className="muted">
              La coda è salvata sul computer. La ripresa usa HTTP Range quando
              supportato, altrimenti ricomincia il trasferimento.
            </p>
            {downloads.length ? (
              downloads.map((task) => (
                <article className="queue-item" key={task.id}>
                  <div className="queue-heading">
                    <strong>{task.snapshot.title}</strong>
                    <span className={`status ${task.status}`}>
                      {labels[task.status]}
                    </span>
                  </div>
                  <progress
                    aria-label={`Avanzamento ${task.snapshot.title}`}
                    value={task.received}
                    max={task.total || 1}
                  />
                  <div className="queue-meta">
                    <span>
                      {bytes(task.received)} / {bytes(task.total)} · Tentativo{" "}
                      {task.attempts}
                    </span>
                    <span>
                      {Math.min(
                        100,
                        Math.round((task.received / task.total) * 100),
                      )}
                      %
                    </span>
                  </div>
                  {task.error && <p className="error-text">{task.error}</p>}
                  <div className="button-row">
                    {[
                      "queued",
                      "running",
                      "verifying",
                      "retry_wait",
                      "downloaded",
                    ].includes(task.status) && (
                      <button
                        disabled={!!busy}
                        onClick={() =>
                          void action("Pausa", async () => {
                            await api(`/downloads/${task.id}/control`, "POST", {
                              action: "pause",
                            });
                          })
                        }
                      >
                        Pausa
                      </button>
                    )}
                    {task.status === "paused" && (
                      <button
                        disabled={!!busy}
                        onClick={() =>
                          void action("Ripresa", async () => {
                            await api(`/downloads/${task.id}/control`, "POST", {
                              action: "resume",
                            });
                          })
                        }
                      >
                        Riprendi
                      </button>
                    )}
                    {["failed", "cancelled"].includes(task.status) && (
                      <button
                        disabled={!!busy}
                        onClick={() =>
                          void action("Retry", async () => {
                            await api(`/downloads/${task.id}/control`, "POST", {
                              action: "retry",
                            });
                          })
                        }
                      >
                        Riprova
                      </button>
                    )}
                    {!["imported", "cancelled"].includes(task.status) && (
                      <button
                        disabled={!!busy}
                        onClick={() =>
                          void action("Annullamento", async () => {
                            await api(`/downloads/${task.id}/control`, "POST", {
                              action: "cancel",
                            });
                          })
                        }
                      >
                        Annulla
                      </button>
                    )}
                  </div>
                  {task.sha256 && (
                    <details>
                      <summary>Integrità e autorizzazione</summary>
                      <p className="path">SHA-256 · {task.sha256}</p>
                      <p>{task.snapshot.license}</p>
                      {sourceLink(task.snapshot.payload.evidence.url) && (
                        <a
                          href={task.snapshot.payload.evidence.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Prova dell'autorizzazione
                        </a>
                      )}
                    </details>
                  )}
                </article>
              ))
            ) : (
              <div className="empty">
                <ArrowDownToLine />
                <p>La coda è vuota. Seleziona i titoli in Game Discovery.</p>
              </div>
            )}
            {downloadTotal > 50 && (
              <div className="pagination">
                <button
                  disabled={downloadPage === 1}
                  onClick={() => setDownloadPage(downloadPage - 1)}
                >
                  Precedente
                </button>
                <span>{downloadPage}</span>
                <button
                  disabled={downloadPage * 50 >= downloadTotal}
                  onClick={() => setDownloadPage(downloadPage + 1)}
                >
                  Successiva
                </button>
              </div>
            )}
          </section>
        </>
      )}
      {plan && (
        <div className="modal-backdrop">
          <section
            ref={dialog}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-labelledby="plan-title"
            className="modal"
          >
            <button
              className="modal-close"
              aria-label="Chiudi riepilogo"
              onClick={() => setPlan(null)}
            >
              <X />
            </button>
            <h2 id="plan-title">Conferma acquisizione</h2>
            <p>
              {plan.count} giochi · {plan.files} file · {bytes(plan.bytes)}
            </p>
            <p>
              {plan.concurrency} download simultanei. Ogni file sarà verificato
              e importato nella libreria.
            </p>
            <p>
              Esportazione stimata complessiva ·{" "}
              {bytes(plan.storage.estimated_export_bytes)} /{" "}
              {bytes(plan.storage.usable_bytes)} utili
            </p>
            <p>
              Esclusi · {plan.skipped.unsupported} non supportati,{" "}
              {plan.skipped.duplicate} duplicati, {plan.skipped.queued} già in
              coda, {plan.skipped.budget} oltre budget
            </p>
            {plan.storage.warnings.map((w) => (
              <p className="error-text" key={w}>
                {w}
              </p>
            ))}
            <details>
              <summary>Titoli inclusi</summary>
              <ul>
                {plan.entries.map((e) => (
                  <li key={e.id}>{e.title}</li>
                ))}
              </ul>
            </details>
            <button
              className="primary"
              disabled={!!busy || !plan.can_confirm}
              onClick={() =>
                void action("Conferma della coda", async () => {
                  await api(`/acquisition/plans/${plan.id}/confirm`, "POST", {
                    confirmed: true,
                  });
                  setPlan(null);
                  setSelected([]);
                  setAllFiltered(false);
                  onDownloads();
                })
              }
            >
              Conferma e avvia {plan.count} download
            </button>
          </section>
        </div>
      )}
    </>
  );
}
