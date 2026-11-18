import Devices from "./Devices";
import Installations from "./Installations";
import "./installations.css";
import Collections, { type CollectionView } from "./Collections";
import Intelligence, { type IntelligenceView } from "./Intelligence";
import Discovery from "./Discovery";
import { useCallback, useEffect, useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  Check,
  Disc3,
  FolderInput,
  Gamepad2,
  Grid2X2,
  HardDrive,
  Heart,
  LayoutDashboard,
  Library,
  List,
  LoaderCircle,
  Search,
  Settings2,
  X,
} from "lucide-react";
import {
  api,
  bytes,
  waitForJob,
  type Candidate,
  type ExportResult,
  type Game,
  type Job,
  type Provider,
  type ScanResult,
  type Settings,
} from "./api";

type Page =
  | "Aggiungi giochi"
  | "La mia libreria"
  | "Installazioni"
  | CollectionView
  | IntelligenceView
  | "Dispositivi"
  | "Sincronizzazione"
  | "Game Discovery"
  | "Download Manager"
  | "Dashboard"
  | "Catalogo"
  | "Preferiti"
  | "Importazione"
  | "Sorgenti e download"
  | "Esportazione"
  | "Impostazioni";
type Stats = {
  games: number;
  bytes: number;
  favorites: number;
  platforms: Record<string, number>;
};
const navigation = [
  { label: "Aggiungi giochi", icon: FolderInput },
  { label: "La mia libreria", icon: Library },
  { label: "Grandi Classici", icon: Heart },
  { label: "Da Recuperare", icon: Search },
  { label: "Installazioni", icon: HardDrive },
  { label: "Dashboard", icon: LayoutDashboard },
  { label: "Collezione Completa", icon: Library },
  { label: "Qualità e media", icon: Grid2X2 },
  { label: "Piattaforme", icon: Gamepad2 },
  { label: "Arcade", icon: Disc3 },
  { label: "Neo Geo", icon: Gamepad2 },
  { label: "Cataloghi DAT", icon: Library },
  { label: "Raccolte", icon: Heart },
  { label: "Catalogo", icon: Library },
  { label: "Game Discovery", icon: Search },
  { label: "Download Manager", icon: ArrowDownToLine },
  { label: "Preferiti", icon: Heart },
  { label: "Importazione", icon: FolderInput },
  { label: "Sorgenti e download", icon: ArrowDownToLine },
  { label: "Esportazione", icon: HardDrive },
  { label: "Dispositivi", icon: HardDrive },
  { label: "Sincronizzazione", icon: ArrowDownToLine },
  { label: "Impostazioni", icon: Settings2 },
] as const;

export default function App() {
  const [page, setPage] = useState<Page>("Aggiungi giochi");
  const [collectionTransfer, setCollectionTransfer] = useState(false);
  const [platforms, setPlatforms] = useState<Record<string, string>>({});
  const [stats, setStats] = useState<Stats>({
    games: 0,
    bytes: 0,
    favorites: 0,
    platforms: {},
  });
  const [games, setGames] = useState<Game[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [platform, setPlatform] = useState("");
  const [region, setRegion] = useState("");
  const [genre, setGenre] = useState("");
  const [list, setList] = useState(false);
  const [number, setNumber] = useState(1);
  const [selected, setSelected] = useState<number[]>([]);
  const [detail, setDetail] = useState<Game | null>(null);
  const [settings, setSettings] = useState<Settings>({
    import_roots: [],
    export_root: "",
  });
  const [providers, setProviders] = useState<Provider[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [loading, setLoading] = useState(false);
  const [scanRoot, setScanRoot] = useState("");
  const [scanPlatform, setScanPlatform] = useState("");
  const [preview, setPreview] = useState<ScanResult | null>(null);
  const [scanId, setScanId] = useState("");
  const [activeScan, setActiveScan] = useState("");
  const [importIds, setImportIds] = useState<number[]>([]);
  const [previewPage, setPreviewPage] = useState(1);
  const [license, setLicense] = useState("Da verificare");
  const [provenance, setProvenance] = useState("Importazione locale");
  const [providerJson, setProviderJson] = useState("");
  const [exportResult, setExportResult] = useState<ExportResult | null>(null);

  const refresh = useCallback(async () => {
    const [s, p, config, sources, history] = await Promise.all([
      api<Stats>("/stats"),
      api<Record<string, string>>("/platforms"),
      api<Settings>("/settings"),
      api<Provider[]>("/providers"),
      api<Job[]>("/jobs"),
    ]);
    setStats(s);
    setPlatforms(p);
    setSettings(config);
    setProviders(sources);
    setJobs(history);
  }, []);
  useEffect(() => {
    refresh().catch((e) => setError(String(e)));
  }, [refresh]);
  const loadGames = useCallback(async () => {
    const params = new URLSearchParams({
      q: query,
      platform,
      region,
      genre,
      page: String(number),
      favorite: String(page === "Preferiti"),
    });
    return api<{ items: Game[]; total: number }>(`/games?${params}`);
  }, [query, platform, region, genre, number, page]);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      setLoading(true);
      loadGames()
        .then((result) => {
          if (active) {
            setGames(result.items);
            setTotal(result.total);
          }
        })
        .catch((e) => {
          if (active) setError(String(e));
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 180);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [loadGames, stats]);

  function navigate(next: Page) {
    if (next !== "Sincronizzazione") setCollectionTransfer(false);
    setPage(next);
    setNumber(1);
    setError("");
    setNotice("");
  }
  async function action(label: string, operation: () => Promise<void>) {
    setBusy(label);
    setError("");
    setNotice("");
    try {
      await operation();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }
  async function job<T>(
    path: string,
    body: unknown,
    label: string,
  ): Promise<Job<T>> {
    const queued = await api<Job>(path, "POST", body);
    if (path === "/imports/scan") setActiveScan(queued.id);
    return waitForJob<T>(queued.id, (status, progress) =>
      setBusy(
        `${label} · ${status === "queued" ? "in coda" : "in corso"}${progress ? ` · ${progress.scanned_files || 0} / ${progress.total_files || "…"} file` : ""}`,
      ),
    ).finally(() => setActiveScan(""));
  }
  function toggle(ids: number[], id: number) {
    return ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id];
  }
  async function favorite(game: Game) {
    await action("Aggiornamento", async () => {
      await api(`/games/${game.id}/favorite`, "PATCH", {
        favorite: !game.favorite,
      });
      if (detail?.id === game.id)
        setDetail({ ...game, favorite: !game.favorite });
    });
  }
  function startScan() {
    void action("Scansione", async () => {
      const result = await job<ScanResult>(
        "/imports/scan",
        { root: scanRoot, platform: scanPlatform || null },
        "Scansione",
      );
      setPreview(result.result);
      setScanId(result.id);
      setPreviewPage(1);
      setImportIds(
        result.result.candidates.filter((c) => !c.duplicate).map((c) => c.id),
      );
    });
  }
  function renderGame(game: Game) {
    return (
      <article className={`game ${list ? "game-row" : ""}`} key={game.id}>
        <div className={`cover console-${game.platform}`}>
          {game.cover_path ? (
            <img
              src={`/api/games/${game.id}/cover`}
              alt={`Copertina di ${game.title}`}
              loading="lazy"
            />
          ) : (
            <>
              <Gamepad2 size={52} strokeWidth={1} />
              <span>{platforms[game.platform]}</span>
            </>
          )}
          <label className="select-game">
            <input
              type="checkbox"
              aria-label={`Seleziona ${game.title}`}
              checked={selected.includes(game.id)}
              onChange={() => {
                setSelected(toggle(selected, game.id));
                setExportResult(null);
              }}
            />
          </label>
          <button
            className={`favorite ${game.favorite ? "is-favorite" : ""}`}
            aria-label={`Preferito ${game.title}`}
            onClick={() => void favorite(game)}
            disabled={!!busy}
          >
            <Heart size={17} fill={game.favorite ? "currentColor" : "none"} />
          </button>
        </div>
        <button
          className="game-info"
          onClick={() =>
            void action("Caricamento dettaglio", async () => {
              setDetail(await api<Game>(`/games/${game.id}`));
            })
          }
        >
          <span className="eyebrow">{platforms[game.platform]}</span>
          <h3>{game.title}</h3>
          <span className="muted">
            {game.region} <span>·</span> {bytes(game.size)} <span>·</span>{" "}
            {game.format.toUpperCase()}
          </span>
        </button>
      </article>
    );
  }
  const catalog = (
    <>
      <div className="toolbar">
        <label className="search">
          <Search size={18} />
          <input
            aria-label="Cerca nella libreria"
            placeholder="Cerca nella tua libreria…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setNumber(1);
            }}
          />
        </label>
        <select
          aria-label="Filtra console"
          value={platform}
          onChange={(e) => {
            setPlatform(e.target.value);
            setNumber(1);
          }}
        >
          <option value="">Tutte le console</option>
          {Object.entries(platforms).map(([id, title]) => (
            <option value={id} key={id}>
              {title}
            </option>
          ))}
        </select>
        <div className="view-switch">
          <button
            aria-label="Vista griglia"
            className={!list ? "active" : ""}
            onClick={() => setList(false)}
          >
            <Grid2X2 size={18} />
          </button>
          <button
            aria-label="Vista lista"
            className={list ? "active" : ""}
            onClick={() => setList(true)}
          >
            <List size={19} />
          </button>
        </div>
      </div>
      <div className="filter-row">
        <input
          aria-label="Filtra regione"
          placeholder="Regione"
          value={region}
          onChange={(e) => {
            setRegion(e.target.value);
            setNumber(1);
          }}
        />
        <input
          aria-label="Filtra genere"
          placeholder="Genere"
          value={genre}
          onChange={(e) => {
            setGenre(e.target.value);
            setNumber(1);
          }}
        />
        <span className="muted">{total.toLocaleString("it-IT")} giochi</span>
        {selected.length > 0 && (
          <button onClick={() => navigate("Esportazione")}>
            {selected.length} selezionati <ArrowRight size={15} />
          </button>
        )}
      </div>
      {selected.length > 0 && (
        <button onClick={() => navigate("Sincronizzazione")}>
          Sincronizza sul Raspberry ({selected.length})
        </button>
      )}
      {loading ? (
        <div className="empty">
          <LoaderCircle className="spin" />
          Caricamento catalogo…
        </div>
      ) : games.length ? (
        <div className={list ? "game-list" : "game-grid"}>
          {games.map(renderGame)}
        </div>
      ) : (
        <div className="empty">
          <Library size={44} strokeWidth={1} />
          <h2>
            {stats.games
              ? "Nessun gioco corrisponde ai filtri"
              : "La tua collezione inizia qui"}
          </h2>
          <p>
            Importa una cartella per organizzare giochi, dischi e preferiti.
          </p>
          <button className="primary" onClick={() => navigate("Importazione")}>
            <FolderInput size={18} />
            Importa giochi
          </button>
        </div>
      )}
      {total > 36 && (
        <div className="pagination">
          <button disabled={number === 1} onClick={() => setNumber(number - 1)}>
            Precedente
          </button>
          <span>
            {number} / {Math.ceil(total / 36)}
          </span>
          <button
            disabled={number * 36 >= total}
            onClick={() => setNumber(number + 1)}
          >
            Successiva
          </button>
        </div>
      )}
    </>
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate("Dashboard");
          }}
        >
          <div className="brand-icon">
            <Gamepad2 />
          </div>
          <div>
            RetroPie<span>LIBRARY MANAGER</span>
          </div>
        </a>
        <div className="nav-label">LA TUA LIBRERIA</div>
        <nav>
          {navigation.slice(0, 5).map(({ label, icon: Icon }) => (
            <button
              key={label}
              className={page === label ? "nav-item active" : "nav-item"}
              onClick={() => navigate(label)}
            >
              <Icon size={19} />
              {label}
              {label === "Preferiti" && stats.favorites > 0 && (
                <small>{stats.favorites}</small>
              )}
            </button>
          ))}
          <details className="advanced-navigation">
            <summary>Avanzate</summary>
            {navigation.slice(5).map(({ label, icon: Icon }) => (
              <button
                key={label}
                className={page === label ? "nav-item active" : "nav-item"}
                onClick={() => navigate(label)}
              >
                <Icon size={19} />
                {label}
              </button>
            ))}
          </details>
        </nav>
        <div className="sidebar-footer">
          <span className="online-dot" />
          Libreria locale<span>RetroPie · Raspberry Pi 3 B+</span>
        </div>
      </aside>
      <main>
        <div className="topbar">
          <span>Il tuo archivio. Pronto a giocare.</span>
          <span className="local-badge">
            <span className="online-dot" />
            Locale
          </span>
        </div>
        <div className="content">
          <header className="page-header">
            <div>
              <div className="eyebrow">RETROPIE LIBRARY MANAGER</div>
              <h1>{page}</h1>
              <p>
                {page === "Aggiungi giochi"
                  ? "Seleziona i file e lascia proseguire l’installazione."
                  : page === "Installazioni"
                    ? "Coda persistente, verifiche e risultati sul Raspberry."
                    : [
                          "Grandi Classici",
                          "La mia libreria",
                          "Collezione Completa",
                          "Da Recuperare",
                          "Qualità e media",
                        ].includes(page)
                      ? "Copie locali, riferimenti ai classici e metadati verificabili."
                      : page === "Dashboard"
                        ? "Tutta la tua passione, in un solo posto."
                        : page === "Catalogo"
                          ? "Esplora e organizza la tua collezione."
                          : page === "Preferiti"
                            ? "I giochi a cui torni sempre."
                            : page === "Importazione"
                              ? "Aggiungi la tua collezione, una cartella alla volta."
                              : page === "Esportazione"
                                ? "Prepara la prossima sessione sul tuo Raspberry Pi."
                                : page === "Impostazioni"
                                  ? "Le cartelle e le preferenze della tua libreria."
                                  : page === "Dispositivi"
                                    ? "Collega il tuo Raspberry e controllane lo stato."
                                    : page === "Sincronizzazione"
                                      ? "Confronta la libreria e trasferisci i giochi sul Raspberry."
                                      : page === "Download Manager"
                                        ? "Segui avanzamento, verifiche e importazioni della tua coda."
                                        : [
                                              "Piattaforme",
                                              "Arcade",
                                              "Neo Geo",
                                              "Cataloghi DAT",
                                              "Raccolte",
                                            ].includes(page)
                                          ? "Cataloghi, file posseduti e compatibilità: ogni dato con la sua evidenza."
                                          : "Gestisci i cataloghi di giochi distribuibili legalmente."}
              </p>
            </div>
            {["Dashboard", "Catalogo", "Preferiti"].includes(page) && (
              <button
                className="primary"
                onClick={() => navigate("Aggiungi giochi")}
              >
                <FolderInput size={18} />
                Importa giochi
              </button>
            )}
          </header>
          {error && (
            <div className="message error" role="alert">
              {error}
              <button aria-label="Chiudi errore" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div className="message success" role="status">
              <Check size={18} />
              {notice}
            </div>
          )}
          {busy && (
            <div className="message" role="status">
              <LoaderCircle className="spin" size={18} />
              {busy}
              {activeScan && (
                <button
                  onClick={() =>
                    void api(`/jobs/${activeScan}/cancel`, "POST").catch((e) =>
                      setError(String(e)),
                    )
                  }
                >
                  Annulla scansione
                </button>
              )}
            </div>
          )}
          {page === "Dashboard" && (
            <>
              <section className="stat-grid">
                {[
                  {
                    label: "Giochi in libreria",
                    value: stats.games.toLocaleString("it-IT"),
                    icon: Gamepad2,
                  },
                  {
                    label: "Console",
                    value: Object.keys(stats.platforms).length,
                    icon: Disc3,
                  },
                  {
                    label: "Spazio occupato",
                    value: bytes(stats.bytes),
                    icon: HardDrive,
                  },
                  { label: "Preferiti", value: stats.favorites, icon: Heart },
                ].map((s) => (
                  <div className="stat" key={s.label}>
                    <s.icon size={20} />
                    <div>{s.label}</div>
                    <strong>{s.value}</strong>
                  </div>
                ))}
              </section>
              <section className="hero">
                <div>
                  <div className="eyebrow">DALLA LIBRERIA AL RASPBERRY PI</div>
                  <h2>
                    La prossima partita
                    <br />
                    parte da qui.
                  </h2>
                  <p>
                    Ritrova i tuoi classici. Organizza la collezione.
                    <br />
                    Prepara la tua selezione per RetroPie.
                  </p>
                  <button
                    onClick={() =>
                      navigate(stats.games ? "Catalogo" : "Importazione")
                    }
                  >
                    {stats.games
                      ? "Esplora il catalogo"
                      : "Aggiungi la prima cartella"}
                    <ArrowRight size={18} />
                  </button>
                </div>
                <div className="hero-art">
                  <div className="orbit orbit-one" />
                  <div className="orbit orbit-two" />
                  <Gamepad2 size={150} strokeWidth={0.8} />
                </div>
              </section>
              <div className="section-title">
                <h2>Le tue console</h2>
                <span className="muted">10 sistemi supportati</span>
              </div>
              <section className="platform-grid">
                {Object.entries(platforms).map(([id, title]) => (
                  <button
                    key={id}
                    className="platform-card"
                    onClick={() => {
                      setPlatform(id);
                      navigate("Catalogo");
                    }}
                  >
                    <div className={`platform-icon console-${id}`}>
                      <Gamepad2 size={22} />
                    </div>
                    <div>
                      <strong>{title}</strong>
                      <span>{stats.platforms[id] || 0} giochi</span>
                    </div>
                    <ArrowRight size={16} />
                  </button>
                ))}
              </section>
              <div className="section-title">
                <h2>Attività recenti</h2>
              </div>
              <div className="panel">
                {jobs.length ? (
                  jobs.slice(0, 5).map((j) => (
                    <div className="activity" key={j.id}>
                      <span>
                        {
                          (
                            {
                              scan: "Scansione",
                              import: "Importazione",
                              export: "Esportazione",
                              download: "Download",
                              diagnostics: "Diagnostica Raspberry",
                              metadata: "Arricchimento metadati",
                            } as Record<string, string>
                          )[j.kind]
                        }
                      </span>
                      <span className={`status ${j.status}`}>
                        {{
                          completed: "Completata",
                          failed: "Fallita",
                          queued: "In coda",
                          running: "In corso",
                        }[j.status] ?? j.status}
                      </span>
                    </div>
                  ))
                ) : (
                  <p className="muted">
                    Le tue importazioni ed esportazioni appariranno qui.
                  </p>
                )}
              </div>
            </>
          )}
          {[
            "Piattaforme",
            "Arcade",
            "Neo Geo",
            "Cataloghi DAT",
            "Raccolte",
          ].includes(page) && (
            <Intelligence
              key={page}
              view={page as IntelligenceView}
              platforms={platforms}
              onImport={() => navigate("Importazione")}
              onSync={(ids) => {
                setSelected(ids);
                navigate("Sincronizzazione");
              }}
            />
          )}
          {(page === "Catalogo" || page === "Preferiti") && catalog}
          {(page === "Aggiungi giochi" || page === "Installazioni") && (
            <Installations
              view={page === "Aggiungi giochi" ? "add" : "queue"}
            />
          )}
          {[
            "La mia libreria",
            "Grandi Classici",
            "Collezione Completa",
            "Da Recuperare",
            "Qualità e media",
          ].includes(page) && (
            <Collections
              key={page}
              view={
                page === "La mia libreria"
                  ? "Collezione Completa"
                  : (page as CollectionView)
              }
              platforms={platforms}
              onImport={() => navigate("Aggiungi giochi")}
              onSync={(ids) => {
                setSelected(ids);
                setCollectionTransfer(true);
                navigate("Sincronizzazione");
              }}
            />
          )}
          {(page === "Game Discovery" || page === "Download Manager") && (
            <Discovery
              view={page === "Game Discovery" ? "discovery" : "downloads"}
              platforms={platforms}
              onDownloads={() => navigate("Download Manager")}
              onChanged={refresh}
            />
          )}
          {(page === "Dispositivi" || page === "Sincronizzazione") && (
            <Devices
              view={page === "Dispositivi" ? "devices" : "sync"}
              withCollection={collectionTransfer}
              selected={selected}
              onSelect={setSelected}
              onCatalog={() => navigate("Catalogo")}
            />
          )}
          {page === "Importazione" && (
            <>
              <section className="panel">
                <h2>Scansiona una cartella</h2>
                <p className="muted">
                  Aggiungi le cartelle autorizzate nelle Impostazioni. I file
                  originali vengono letti e verificati.
                </p>
                <div className="form-grid">
                  <label>
                    Cartella da scansionare
                    <input
                      placeholder="C:\Giochi"
                      value={scanRoot}
                      onChange={(e) => setScanRoot(e.target.value)}
                      list="roots"
                    />
                    <datalist id="roots">
                      {settings.import_roots.map((r) => (
                        <option value={r} key={r} />
                      ))}
                    </datalist>
                  </label>
                  <label>
                    Console per i formati ambigui
                    <select
                      value={scanPlatform}
                      onChange={(e) => setScanPlatform(e.target.value)}
                    >
                      <option value="">Rilevamento automatico</option>
                      {Object.entries(platforms).map(([id, name]) => (
                        <option value={id} key={id}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <button
                  className="primary"
                  disabled={!!busy || !scanRoot}
                  onClick={startScan}
                >
                  <Search size={18} />
                  Avvia scansione
                </button>
              </section>
              {preview && (
                <section className="panel">
                  <h2>Anteprima importazione</h2>
                  <p>
                    {preview.scanned_files} file esaminati ·{" "}
                    {preview.candidates.length} giochi ·{" "}
                    {preview.candidates.filter((c) => c.duplicate).length}{" "}
                    duplicati
                  </p>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>
                            <input
                              type="checkbox"
                              aria-label="Seleziona tutti i candidati"
                              checked={
                                importIds.length > 0 &&
                                importIds.length ===
                                  preview.candidates.filter((c) => !c.duplicate)
                                    .length
                              }
                              onChange={(e) =>
                                setImportIds(
                                  e.target.checked
                                    ? preview.candidates
                                        .filter((c) => !c.duplicate)
                                        .map((c) => c.id)
                                    : [],
                                )
                              }
                            />
                          </th>
                          <th>Titolo</th>
                          <th>Console</th>
                          <th>Dimensione</th>
                          <th>Stato</th>
                        </tr>
                      </thead>
                      <tbody>
                        {preview.candidates
                          .slice((previewPage - 1) * 100, previewPage * 100)
                          .map((c: Candidate) => (
                            <tr key={c.id}>
                              <td>
                                <input
                                  aria-label={`Importa ${c.title}`}
                                  type="checkbox"
                                  disabled={c.duplicate}
                                  checked={importIds.includes(c.id)}
                                  onChange={() =>
                                    setImportIds(toggle(importIds, c.id))
                                  }
                                />
                              </td>
                              <td>
                                {c.title}
                                <small>
                                  {c.files.length} file · {c.format}
                                </small>
                              </td>
                              <td>{platforms[c.platform]}</td>
                              <td>{bytes(c.size)}</td>
                              <td>
                                <span className="status">
                                  {c.duplicate ? "Duplicato" : "Pronto"}
                                </span>
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                  {preview.candidates.length > 100 && (
                    <div className="pagination">
                      <button
                        disabled={previewPage === 1}
                        onClick={() => setPreviewPage(previewPage - 1)}
                      >
                        Precedente
                      </button>
                      <span>{previewPage}</span>
                      <button
                        disabled={
                          previewPage * 100 >= preview.candidates.length
                        }
                        onClick={() => setPreviewPage(previewPage + 1)}
                      >
                        Successiva
                      </button>
                    </div>
                  )}
                  {preview.warnings.length > 0 && (
                    <details>
                      <summary>{preview.warnings.length} segnalazioni</summary>
                      {preview.warnings.map((w, i) => (
                        <p key={i}>{w}</p>
                      ))}
                    </details>
                  )}
                  <div className="form-grid">
                    <label>
                      Provenienza
                      <input
                        value={provenance}
                        onChange={(e) => setProvenance(e.target.value)}
                      />
                    </label>
                    <label>
                      Licenza / diritto d'uso
                      <input
                        value={license}
                        onChange={(e) => setLicense(e.target.value)}
                      />
                    </label>
                  </div>
                  <button
                    className="primary"
                    disabled={!!busy || !importIds.length}
                    onClick={() =>
                      void action("Importazione", async () => {
                        const result = await job<{
                          imported: number;
                          skipped: number;
                        }>(
                          `/imports/${scanId}/commit`,
                          { candidate_ids: importIds, provenance, license },
                          "Importazione",
                        );
                        setNotice(
                          `${result.result.imported} giochi importati, ${result.result.skipped} duplicati saltati.`,
                        );
                        setPreview(null);
                      })
                    }
                  >
                    Importa {importIds.length} giochi
                  </button>
                </section>
              )}
              <section className="panel">
                <h2>Anteprime salvate</h2>
                {jobs
                  .filter((j) => j.kind === "scan" && j.status === "completed")
                  .map((j) => (
                    <button
                      key={j.id}
                      className="history-button"
                      onClick={() =>
                        void action("Caricamento anteprima", async () => {
                          const saved = await api<Job<ScanResult>>(
                            `/jobs/${j.id}`,
                          );
                          setScanId(j.id);
                          setPreview(saved.result);
                          setImportIds(
                            saved.result.candidates
                              .filter((c) => !c.duplicate)
                              .map((c) => c.id),
                          );
                          setPreviewPage(1);
                        })
                      }
                    >
                      Apri anteprima {j.id.slice(0, 8)}
                      <ArrowRight size={16} />
                    </button>
                  ))}
              </section>
            </>
          )}
          {page === "Impostazioni" && (
            <section className="panel settings-panel">
              <h2>Cartelle locali</h2>
              <label>
                Sorgenti autorizzate · un percorso per riga
                <textarea
                  rows={5}
                  value={settings.import_roots.join("\n")}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      import_roots: e.target.value.split("\n"),
                    })
                  }
                  placeholder="C:\Giochi"
                />
              </label>
              <label>
                Cartella di destinazione delle esportazioni
                <input
                  value={settings.export_root}
                  onChange={(e) =>
                    setSettings({ ...settings, export_root: e.target.value })
                  }
                  placeholder="C:\Esportazioni"
                />
              </label>
              <p className="muted">
                Le cartelle devono esistere. Le esportazioni vengono create in
                sottocartelle dedicate.
              </p>
              <button
                className="primary"
                disabled={!!busy}
                onClick={() =>
                  void action("Salvataggio", async () => {
                    await api("/settings", "PUT", {
                      import_roots: settings.import_roots.filter((r) =>
                        r.trim(),
                      ),
                      export_root: settings.export_root,
                    });
                    setNotice("Impostazioni salvate.");
                  })
                }
              >
                Salva impostazioni
              </button>
              <hr />
              <h3>Archivio locale</h3>
              <p className="path">{settings.data_dir}</p>
              <p className="muted">
                Database, log e download verificati risiedono su questo
                computer.
              </p>
            </section>
          )}
          {page === "Esportazione" && (
            <button onClick={() => navigate("Sincronizzazione")}>
              Sincronizza questa selezione sul Raspberry
            </button>
          )}
          {page === "Esportazione" && (
            <section className="panel">
              <h2>Prepara la selezione</h2>
              <p>{selected.length} giochi selezionati nel catalogo.</p>
              <p className="path">
                Destinazione ·{" "}
                {settings.export_root ||
                  "Configura una cartella nelle Impostazioni"}
              </p>
              <div className="button-row">
                <button onClick={() => navigate("Catalogo")}>
                  Scegli giochi
                </button>
                <button
                  disabled={!!busy || !selected.length}
                  onClick={() => {
                    setSelected([]);
                    setExportResult(null);
                  }}
                >
                  Svuota selezione
                </button>
                <button
                  className="primary"
                  disabled={!!busy || !selected.length || !settings.export_root}
                  onClick={() =>
                    void action("Verifica esportazione", async () => {
                      const result = await job<ExportResult>(
                        "/exports",
                        { game_ids: selected, dry_run: true },
                        "Verifica",
                      );
                      setExportResult(result.result);
                    })
                  }
                >
                  Calcola spazio · dry-run
                </button>
              </div>
              {exportResult && (
                <div className="export-result">
                  <div className="stat-grid">
                    <div className="stat">
                      <div>Spazio necessario</div>
                      <strong>{bytes(exportResult.required_bytes)}</strong>
                    </div>
                    <div className="stat">
                      <div>Spazio disponibile</div>
                      <strong>{bytes(exportResult.free_bytes)}</strong>
                    </div>
                  </div>
                  {exportResult.target_capacity && (
                    <p
                      className={
                        exportResult.target_capacity.selection_fits_target
                          ? "muted"
                          : "error-text"
                      }
                    >
                      Capacità RetroPie utile ·{" "}
                      {bytes(exportResult.target_capacity.usable_bytes)}
                      {!exportResult.target_capacity.selection_fits_target &&
                        " — Attenzione, la selezione supera la capacità target."}
                    </p>
                  )}
                  <p className="success-text">
                    {exportResult.dry_run
                      ? "Integrità verificata. La selezione è pronta per essere copiata."
                      : `Esportazione completata in ${exportResult.destination}`}
                  </p>
                  <details>
                    <summary>Manifest dell'esportazione</summary>
                    <pre>{JSON.stringify(exportResult.manifest, null, 2)}</pre>
                  </details>
                  <button
                    disabled={!!busy}
                    className="primary"
                    onClick={() =>
                      void action("Esportazione", async () => {
                        const result = await job<ExportResult>(
                          "/exports",
                          { game_ids: selected, dry_run: false },
                          "Esportazione",
                        );
                        setExportResult(result.result);
                        setNotice("Esportazione completata e verificata.");
                      })
                    }
                  >
                    <HardDrive size={18} />
                    Copia la selezione
                  </button>
                </div>
              )}
            </section>
          )}
          {page === "Sorgenti e download" && (
            <>
              <section className="panel">
                <h2>Cataloghi autorizzati</h2>
                <p className="muted">
                  Importa un manifest JSON di un distributore autorizzato. Ogni
                  voce richiede licenza, URL dei diritti, dimensione e hash
                  SHA-256. Verifica la fonte prima di aggiungerla.
                </p>
                <label>
                  Manifest del provider
                  <textarea
                    rows={6}
                    value={providerJson}
                    onChange={(e) => setProviderJson(e.target.value)}
                    placeholder={
                      '{"id":"autore", "name":"Catalogo autore", "entries":[]}'
                    }
                  />
                </label>
                <button
                  className="primary"
                  disabled={!!busy || !providerJson}
                  onClick={() =>
                    void action("Salvataggio provider", async () => {
                      const value = JSON.parse(providerJson) as Provider;
                      await api(
                        `/providers/${encodeURIComponent(value.id)}`,
                        "PUT",
                        value,
                      );
                      setNotice("Provider salvato.");
                      setProviderJson("");
                    })
                  }
                >
                  Aggiungi / aggiorna catalogo
                </button>
              </section>
              {providers.map((p) => (
                <section className="panel" key={p.id}>
                  <h2>{p.name}</h2>
                  {p.entries.length ? (
                    p.entries.map((e) => (
                      <div className="download-row" key={e.id}>
                        <div>
                          <strong>{e.title}</strong>
                          <p>
                            {platforms[e.platform]} · {bytes(e.size)} ·{" "}
                            {e.license}
                          </p>
                          {e.rights_url.startsWith("https://") && (
                            <a
                              href={e.rights_url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Fonte e autorizzazione
                            </a>
                          )}
                        </div>
                        <button
                          disabled={!!busy}
                          onClick={() => navigate("Game Discovery")}
                        >
                          <ArrowDownToLine size={17} />
                          Apri in Discovery
                        </button>
                      </div>
                    ))
                  ) : (
                    <p className="muted">Il catalogo è vuoto.</p>
                  )}
                </section>
              ))}
            </>
          )}
        </div>
        <footer>
          RetroPie Library Manager{" "}
          <span>Incremento 6 · Essential Classics</span>
        </footer>
      </main>
      {detail && (
        <div
          className="modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget) setDetail(null);
          }}
        >
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="detail-title"
          >
            <button
              className="modal-close"
              aria-label="Chiudi dettaglio"
              onClick={() => setDetail(null)}
            >
              <X />
            </button>
            <div className="eyebrow">{platforms[detail.platform]}</div>
            <h2 id="detail-title">Dettaglio gioco</h2>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void action("Salvataggio gioco", async () => {
                  const {
                    title,
                    author,
                    publisher,
                    region,
                    year,
                    genre,
                    description,
                    favorite,
                    provenance,
                    license,
                    cover_path,
                  } = detail;
                  await api(`/games/${detail.id}`, "PUT", {
                    title,
                    author,
                    publisher,
                    region,
                    year,
                    genre,
                    description,
                    favorite,
                    provenance,
                    license,
                    cover_path,
                  });
                  setNotice("Gioco aggiornato.");
                  setDetail(null);
                });
              }}
            >
              <label>
                Titolo
                <input
                  required
                  maxLength={300}
                  value={detail.title}
                  onChange={(e) =>
                    setDetail({ ...detail, title: e.target.value })
                  }
                />
              </label>
              <div className="form-grid">
                <label>
                  Regione
                  <input
                    value={detail.region}
                    onChange={(e) =>
                      setDetail({ ...detail, region: e.target.value })
                    }
                  />
                </label>
                <label>
                  Anno
                  <input
                    type="number"
                    min={1970}
                    max={2100}
                    value={detail.year ?? ""}
                    onChange={(e) =>
                      setDetail({
                        ...detail,
                        year: e.target.value ? Number(e.target.value) : null,
                      })
                    }
                  />
                </label>
              </div>
              <label>
                Autore
                <input
                  value={detail.author || ""}
                  onChange={(e) =>
                    setDetail({ ...detail, author: e.target.value })
                  }
                />
              </label>
              <label>
                Publisher
                <input
                  value={detail.publisher || ""}
                  onChange={(e) =>
                    setDetail({ ...detail, publisher: e.target.value })
                  }
                />
              </label>
              <label>
                Genere
                <input
                  value={detail.genre}
                  onChange={(e) =>
                    setDetail({ ...detail, genre: e.target.value })
                  }
                />
              </label>
              <label>
                Descrizione
                <textarea
                  rows={3}
                  value={detail.description}
                  onChange={(e) =>
                    setDetail({ ...detail, description: e.target.value })
                  }
                />
              </label>
              <label>
                Percorso copertina · PNG, JPG, WebP
                <input
                  value={detail.cover_path}
                  onChange={(e) =>
                    setDetail({ ...detail, cover_path: e.target.value })
                  }
                />
              </label>
              <div className="form-grid">
                <label>
                  Provenienza
                  <input
                    value={detail.provenance}
                    onChange={(e) =>
                      setDetail({ ...detail, provenance: e.target.value })
                    }
                  />
                </label>
                <label>
                  Licenza
                  <input
                    required
                    value={detail.license}
                    onChange={(e) =>
                      setDetail({ ...detail, license: e.target.value })
                    }
                  />
                </label>
              </div>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={detail.favorite}
                  onChange={(e) =>
                    setDetail({ ...detail, favorite: e.target.checked })
                  }
                />
                Preferito
              </label>
              <details>
                <summary>File e integrità · {bytes(detail.size)}</summary>
                <p className="path">{detail.local_path}</p>
                <p className="path">SHA-256 · {detail.sha256}</p>
                {detail.files.map((f) => (
                  <p className="path" key={f.path}>
                    {f.relative} · {bytes(f.size)}
                    <br />
                    {f.sha256}
                  </p>
                ))}
              </details>
              <button className="primary" disabled={!!busy} type="submit">
                Salva modifiche
              </button>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
