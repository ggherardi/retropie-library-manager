import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  ArrowRight,
  Database,
  Gamepad2,
  Heart,
  ShieldCheck,
  X,
} from "lucide-react";
import { api, bytes, type Game } from "./api";
import {
  intel,
  count,
  stateLabel,
  saveReport,
  type Summary,
  type Source,
  type Entry,
  type EntryDetail,
  type Run,
  type Device,
  type Insight,
  type Validation,
} from "./intelligence-api";

export type IntelligenceView =
  "Piattaforme" | "Arcade" | "Neo Geo" | "Cataloghi DAT" | "Raccolte";
type Tab = "catalog" | "owned" | "imports" | "profiles";
type Owned = Game & { insight: Insight | null; validation_status: string };
const collections = [
  ["all", "Tutti"],
  ["owned", "Posseduti"],
  ["arcade", "Arcade"],
  ["neogeo", "Neo Geo"],
  ["multiplayer", "Multiplayer"],
  ["favorites", "Preferiti"],
  ["tested", "Test riusciti sul Raspberry"],
  ["missing", "Dipendenze mancanti"],
  ["unsynced", "Non ancora sincronizzati"],
  ["preferred", "Varianti preferite"],
];
const active = (status: string) =>
  ["running", "queued", "cancelling"].includes(status);

export default function Intelligence({
  view,
  platforms,
  onSync,
  onImport,
}: {
  view: IntelligenceView;
  platforms: Record<string, string>;
  onSync: (ids: number[]) => void;
  onImport: () => void;
}) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [tab, setTab] = useState<Tab>(
    view === "Cataloghi DAT"
      ? "imports"
      : view === "Raccolte"
        ? "owned"
        : "catalog",
  );
  const [q, setQ] = useState("");
  const [platform, setPlatform] = useState("");
  const [source, setSource] = useState("");
  const [system, setSystem] = useState("");
  const [genre, setGenre] = useState("");
  const [parents, setParents] = useState(false);
  const [kind, setKind] = useState("game");
  const [collection, setCollection] = useState(
    view === "Neo Geo" ? "neogeo" : view === "Arcade" ? "arcade" : "all",
  );
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [owned, setOwned] = useState<Owned[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [mode, setMode] = useState("split");
  const [detail, setDetail] = useState<EntryDetail | null>(null);
  const [gameId, setGameId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [matching, setMatching] = useState<Run | null>(null);
  const refresh = useCallback(async () => {
    const [s, list, history, pi] = await Promise.all([
      intel<Summary>("/summary"),
      intel<Source[]>("/sources"),
      intel<Run[]>("/runs"),
      api<Device[]>("/devices"),
    ]);
    setSummary(s);
    setSources(list);
    setRuns(history);
    setDevices(pi);
  }, []);
  useEffect(() => {
    let mounted = true;
    const tick = () => {
      if (mounted) void refresh().catch((e) => setError(String(e)));
    };
    tick();
    const timer = setInterval(tick, 2500);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, [refresh]);
  const completed = runs
    .filter((r) => !active(r.status))
    .map((r) => r.id + r.status)
    .join(",");
  useEffect(() => {
    let live = true;
    const timer = setTimeout(() => {
      const promise =
        tab === "owned"
          ? intel<{ items: Owned[]; total: number }>(
              `/owned?${new URLSearchParams({ q, platform, genre, collection, page: String(page) })}`,
            ).then((r) => {
              if (live) {
                setOwned(r.items);
                setTotal(r.total);
              }
            })
          : intel<{ items: Entry[]; total: number }>(
              `/search?page=${page}`,
              "POST",
              {
                q,
                platform,
                genre,
                collection,
                source_id: source,
                system,
                parents_only: parents,
                kind,
              },
            ).then((r) => {
              if (live) {
                setEntries(r.items);
                setTotal(r.total);
              }
            });
      promise
        .catch((e) => {
          if (live) setError(String(e));
        })
        .finally(() => {
          if (live) setLoading(false);
        });
    }, 180);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [
    tab,
    q,
    platform,
    genre,
    collection,
    page,
    source,
    system,
    parents,
    kind,
    revision,
    completed,
  ]);
  async function action(operation: () => Promise<unknown>, message = "") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await operation();
      setNotice(message);
      setRevision((v) => v + 1);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  const queue = (path: string, body: unknown) =>
    action(
      () => intel(path, "POST", body),
      "Operazione avviata. Segui il progresso nel pannello attività.",
    );
  function filter(change: () => void) {
    setLoading(true);
    change();
    setPage(1);
    setSelected([]);
  }
  const loadDetail = (uid: string) =>
    action(async () => setDetail(await intel<EntryDetail>("/entries/" + uid)));
  const latestMatch = runs.find(
    (r) => r.kind === "catalog_matching" && r.status === "completed",
  );
  return (
    <div className="intelligence">
      {error && (
        <div className="message error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="message success" role="status">
          {notice}
        </div>
      )}
      {summary && (
        <>
          <div className="intelligence-stats">
            {[
              [summary.catalog_games, "Voci gioco nei DAT"],
              [summary.unique_families, "Famiglie per catalogo"],
              [summary.present_files, "File locali presenti"],
              [summary.authorized_downloads, "Download autorizzati"],
              [summary.validated_games, "Set validati"],
              [summary.tested_games, "Test riusciti · operatore"],
            ].map(([n, label]) => (
              <div key={label}>
                <strong>{count(Number(n))}</strong>
                <span>{label}</span>
              </div>
            ))}
          </div>
          <p className="intelligence-note">
            {summary.family_scope}. {count(summary.clones)} cloni ·{" "}
            {count(summary.bios_records)} record BIOS ·{" "}
            {count(summary.local_files)} elementi locali registrati
            {summary.missing_files > 0 &&
              ` · ${summary.missing_files} file mancanti`}
            . La validazione dei set non certifica prestazioni o avvio sul
            Raspberry.
          </p>
          {view === "Piattaforme" && (
            <div className="platform-matrix">
              {summary.platforms.map((p) => (
                <button
                  key={p.id}
                  className={
                    platform === p.id
                      ? "platform-tile selected"
                      : "platform-tile"
                  }
                  onClick={() =>
                    filter(() => {
                      setPlatform(p.id);
                      setCollection("all");
                      setTab("catalog");
                    })
                  }
                >
                  <Gamepad2 size={20} />
                  <strong>{p.name}</strong>
                  <small>
                    {count(p.catalog)} metadati · {count(p.local)} locali
                  </small>
                </button>
              ))}
            </div>
          )}
        </>
      )}
      {view === "Neo Geo" && (
        <div className="intel-banner">
          <ShieldCheck size={28} />
          <div>
            <strong>Neo Geo · MVS / AES</strong>
            <p>
              Valida il set con il DAT del tuo FBNeo e verifica il BIOS. Importa
              manualmente soltanto file ottenuti legittimamente. La modalità
              MVS/AES registrata qui descrive la preferenza; le opzioni del core
              si impostano sulla console.
            </p>
            <button onClick={onImport}>Importazione manuale ROM / BIOS</button>
          </div>
        </div>
      )}
      <div
        className="mode-switch intel-tabs"
        role="tablist"
        aria-label="Library intelligence"
      >
        {(
          [
            ["catalog", "Esplora metadati"],
            ["owned", "File e raccolte"],
            ["imports", "Importazione DAT"],
            ["profiles", "Core e BIOS"],
          ] as [Tab, string][]
        ).map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            className={tab === id ? "primary" : ""}
            onClick={() => filter(() => setTab(id))}
          >
            {label}
          </button>
        ))}
      </div>
      {(tab === "catalog" || tab === "owned") && (
        <>
          <div className="panel intel-filters">
            <label className="wide">
              Ricerca {tab === "catalog" ? "nei metadati" : "nei file locali"}
              <input
                aria-label="Cerca nei cataloghi massivi"
                value={q}
                onChange={(e) => filter(() => setQ(e.target.value))}
                placeholder="Titolo, set, produttore…"
              />
            </label>
            <label>
              Piattaforma
              <select
                value={platform}
                onChange={(e) => filter(() => setPlatform(e.target.value))}
              >
                <option value="">Tutte le piattaforme</option>
                {Object.entries(platforms).map(([id, name]) => (
                  <option key={id} value={id}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Raccolta
              <select
                value={collection}
                onChange={(e) => filter(() => setCollection(e.target.value))}
              >
                {collections
                  .filter(
                    ([id]) =>
                      tab === "catalog" || !["preferred", "owned"].includes(id),
                  )
                  .map(([id, label]) => (
                    <option key={id} value={id}>
                      {label}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Genere
              <input
                value={genre}
                onChange={(e) => filter(() => setGenre(e.target.value))}
                placeholder="Genere esatto, se disponibile"
              />
            </label>
            {tab === "catalog" && (
              <>
                <label>
                  Catalogo DAT
                  <select
                    value={source}
                    onChange={(e) => filter(() => setSource(e.target.value))}
                  >
                    <option value="">Tutti i cataloghi</option>
                    {sources.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Sistema arcade
                  <select
                    value={system}
                    onChange={(e) => filter(() => setSystem(e.target.value))}
                  >
                    <option value="">Tutti i sistemi</option>
                    {["Neo Geo", "CPS-1", "CPS-2", "CPS-3"].map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Tipo di record
                  <select
                    value={kind}
                    onChange={(e) => filter(() => setKind(e.target.value))}
                  >
                    <option value="game">Giochi</option>
                    <option value="bios">BIOS (solo metadati)</option>
                    <option value="device">Dispositivi</option>
                    <option value="">Tutti</option>
                  </select>
                </label>
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={parents}
                    onChange={(e) => filter(() => setParents(e.target.checked))}
                  />
                  Solo parent
                </label>
              </>
            )}
          </div>
          <div className="section-heading">
            <h2>
              {count(total)} {tab === "catalog" ? "record" : "elementi locali"}
            </h2>
            <span>Pagina {page} · fino a 36 risultati</span>
          </div>
          {tab === "catalog" ? (
            <div className="intel-catalog">
              {entries.map((e) => (
                <button
                  className="intel-entry"
                  key={e.uid}
                  onClick={() => void loadDetail(e.uid)}
                >
                  <div className="entry-symbol">
                    <Gamepad2 size={25} />
                    <span>{e.platform}</span>
                  </div>
                  <div>
                    <strong>{e.title}</strong>
                    <p>
                      <code>{e.name}</code> · {e.year || "Anno non noto"} ·{" "}
                      {e.manufacturer || "Produttore non noto"}
                    </p>
                    <div className="intel-badges">
                      <span>{e.system || e.platform}</span>
                      <span>
                        {e.parent
                          ? `Clone di ${e.parent}`
                          : "Parent / indipendente"}
                      </span>
                      <span>
                        {e.owned_game_ids.length
                          ? "File associato"
                          : "Solo metadati"}
                      </span>
                      {e.players > 1 && <span>{e.players} giocatori</span>}
                    </div>
                  </div>
                  <ArrowRight size={18} />
                </button>
              ))}
            </div>
          ) : (
            <>
              <div className="selection-bar">
                <button
                  onClick={() =>
                    setSelected([
                      ...new Set([...selected, ...owned.map((g) => g.id)]),
                    ])
                  }
                >
                  Seleziona pagina
                </button>
                <button onClick={() => setSelected([])}>
                  Azzera selezione
                </button>
                <span>{selected.length} selezionati</span>
                <button
                  className="primary"
                  disabled={!selected.length}
                  onClick={() => onSync(selected)}
                >
                  Prepara sincronizzazione
                </button>
              </div>
              <div className="intel-catalog">
                {owned.map((g) => (
                  <div className="intel-entry owned" key={g.id}>
                    <input
                      aria-label={`Seleziona ${g.title}`}
                      type="checkbox"
                      checked={selected.includes(g.id)}
                      onChange={(e) =>
                        setSelected((ids) =>
                          e.target.checked
                            ? [...ids, g.id]
                            : ids.filter((id) => id !== g.id),
                        )
                      }
                    />
                    <button
                      className="entry-main"
                      onClick={() => setGameId(g.id)}
                    >
                      <strong>{g.title}</strong>
                      <p>
                        {platforms[g.platform]} · {bytes(g.size)}
                      </p>
                      <div className="intel-badges">
                        <span>{stateLabel(g.validation_status)}</span>
                        <span>
                          {stateLabel(g.insight?.test_status || "untested")}
                        </span>
                      </div>
                    </button>
                    <button
                      aria-label={`Preferito ${g.title}`}
                      onClick={() =>
                        void action(() =>
                          api(`/games/${g.id}/favorite`, "PATCH", {
                            favorite: !g.favorite,
                          }),
                        )
                      }
                    >
                      <Heart
                        size={16}
                        fill={g.favorite ? "currentColor" : "none"}
                      />
                    </button>
                  </div>
                ))}
              </div>
              <div className="panel validation-tools">
                <h3>Verifica i set selezionati</h3>
                <p>
                  Gli archivi rimangono intatti. La verifica confronta i
                  componenti con il catalogo scelto e segnala dipendenze o hash
                  diversi.
                </p>
                <div className="intel-filters">
                  <label>
                    DAT per la validazione
                    <select
                      value={source}
                      onChange={(e) => setSource(e.target.value)}
                    >
                      <option value="">Scegli un catalogo</option>
                      {sources.map((s) => (
                        <option value={s.id} key={s.id}>
                          {s.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Organizzazione del set
                    <select
                      value={mode}
                      onChange={(e) => setMode(e.target.value)}
                    >
                      {["split", "merged", "non-merged", "full-non-merged"].map(
                        (m) => (
                          <option key={m}>{m}</option>
                        ),
                      )}
                    </select>
                  </label>
                </div>
                <div className="button-row">
                  <button
                    disabled={busy || !selected.length || !source}
                    onClick={() =>
                      void queue("/validate", {
                        game_ids: selected,
                        source_id: source,
                        mode,
                      })
                    }
                  >
                    Valida archivi selezionati
                  </button>
                  <button
                    disabled={busy || !selected.length || !source}
                    onClick={() =>
                      void queue("/metadata", {
                        game_ids: selected,
                        source_id: source,
                        apply: false,
                      })
                    }
                  >
                    Anteprima metadati
                  </button>
                  {latestMatch && (
                    <button onClick={() => setMatching(latestMatch)}>
                      Apri anteprima associazioni
                    </button>
                  )}
                </div>
              </div>
            </>
          )}
          {loading && <p role="status">Caricamento risultati…</p>}
          {!total && !loading && (
            <div className="empty-state">
              <Database size={30} />
              <h3>Nessun risultato in questa vista</h3>
              <p>
                Importa un catalogo DAT per esplorare i metadati, oppure
                aggiungi file locali ottenuti legittimamente.
              </p>
            </div>
          )}
          <div className="pagination">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Precedente
            </button>
            <span>
              {page} / {Math.max(1, Math.ceil(total / 36))}
            </span>
            <button
              disabled={page * 36 >= total}
              onClick={() => setPage((p) => p + 1)}
            >
              Successiva
            </button>
          </div>
        </>
      )}
      {tab === "imports" && (
        <CatalogImports
          sources={sources}
          devices={devices}
          platforms={platforms}
          busy={busy}
          queue={queue}
        />
      )}
      {tab === "profiles" && (
        <CoreProfiles
          devices={devices}
          sources={sources}
          busy={busy}
          queue={queue}
          action={action}
        />
      )}
      <section className="panel intel-activity">
        <div className="section-heading">
          <h2>Attività e report</h2>
          <span>Ultime 30 operazioni</span>
        </div>
        {runs.slice(0, 10).map((r) => (
          <div className="intel-run" key={r.id}>
            <div>
              <strong>
                {{
                  catalog_import: "Catalogazione",
                  arcade_validation: "Validazione archivi",
                  core_audit: "Rilevamento Raspberry",
                  catalog_matching: "Associazione metadati",
                }[r.kind] || r.kind}
              </strong>
              <span>
                {stateLabel(r.status)} ·{" "}
                {new Date(r.created_at).toLocaleString("it-IT")}
              </span>
              {active(r.status) && (
                <p>
                  {r.progress.phase}{" "}
                  {r.progress.records
                    ? `${count(r.progress.records)} record`
                    : ""}
                  {r.progress.total
                    ? `${r.progress.done || 0} / ${r.progress.total}`
                    : ""}
                  {r.progress.total_bytes
                    ? `${bytes(r.progress.bytes || 0)} / ${bytes(r.progress.total_bytes)}`
                    : ""}
                </p>
              )}
              {r.error && <p className="error-text">{r.error}</p>}
            </div>
            {active(r.status) ? (
              <button
                disabled={r.status === "cancelling"}
                onClick={() =>
                  void action(() => intel(`/runs/${r.id}/cancel`, "POST"))
                }
              >
                Annulla
              </button>
            ) : (
              <button onClick={() => saveReport(r, `report-${r.id}.json`)}>
                Report JSON
              </button>
            )}
          </div>
        ))}
        {!runs.length && (
          <p>Le importazioni, le verifiche e i report compariranno qui.</p>
        )}
      </section>
      {detail && (
        <Modal title={detail.title} onClose={() => setDetail(null)}>
          <div className="intel-badges">
            <span>Solo metadati · nessun download ROM</span>
            <span>{detail.kind}</span>
          </div>
          <dl className="intel-details">
            {Object.entries({
              "Nome tecnico": detail.name,
              Sistema: detail.system || detail.platform,
              Produttore: detail.manufacturer,
              Anno: detail.year,
              Giocatori: detail.players || "Non noto",
              Orientamento: detail.orientation,
              Controlli: detail.controls,
              Parent: detail.parent || "Indipendente",
              "ROM / BIOS di riferimento": detail.romof || "Nessuno dichiarato",
              Core: detail.source.config.core || "Da verificare",
              "Versione DAT": detail.source.config.version,
              "Compatibilità dichiarata DAT":
                detail.details.declared_status || "Non dichiarata",
              "Test sul Raspberry": "Non deducibile dal catalogo",
            }).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{String(value || "Non noto")}</dd>
              </div>
            ))}
          </dl>
          {detail.system === "CPS-3" && (
            <div className="message">
              CPS-3: prestazioni e compatibilità da verificare sul Raspberry Pi
              3 B+.
            </div>
          )}
          <h3>Varianti della famiglia</h3>
          <div className="variant-list">
            {detail.variants.map((v) => (
              <div key={v.uid}>
                <button onClick={() => void loadDetail(v.uid)}>
                  {v.title} <code>{v.name}</code>
                </button>
                <button
                  disabled={detail.preferred_uid === v.uid}
                  onClick={() =>
                    void action(async () => {
                      await intel("/preferred", "POST", { uid: v.uid });
                      setDetail({ ...detail, preferred_uid: v.uid });
                    })
                  }
                >
                  {detail.preferred_uid === v.uid
                    ? "Preferita"
                    : "Scegli versione"}
                </button>
              </div>
            ))}
          </div>
          <details>
            <summary>{detail.components.length} componenti attesi</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Nome</th>
                    <th>Dimensione</th>
                    <th>CRC / SHA1</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.components.slice(0, 500).map((c, i) => (
                    <tr key={i}>
                      <td>{c.name}</td>
                      <td>{bytes(c.size)}</td>
                      <td>
                        <code>{c.sha1 || c.crc || "Hash assente"}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          <label>
            Associa manualmente a un file arcade
            <select
              defaultValue=""
              onChange={(e) => {
                if (e.target.value)
                  void queue("/validate", {
                    source_id: detail.source.id,
                    game_ids: [Number(e.target.value)],
                    mode,
                    entry_uid: detail.uid,
                  });
              }}
              onFocus={() => {
                void intel<{ items: Owned[] }>(
                  "/owned?collection=arcade&page_size=100",
                )
                  .then((r) => setOwned(r.items))
                  .catch((e) => setError(String(e)));
              }}
            >
              <option value="">
                Scegli un file locale (primi 100) · verifica obbligatoria
              </option>
              {owned
                .filter((g) =>
                  ["arcade", "neogeo", "fba", "mame-libretro"].includes(
                    g.platform,
                  ),
                )
                .map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.title}
                  </option>
                ))}
            </select>
          </label>
          <p>
            Organizzazione selezionata: {mode}. Per librerie più grandi usa la
            validazione massiva per nome tecnico in File e raccolte.
          </p>
          <button
            onClick={() => saveReport(detail, `${detail.name}-manifest.json`)}
          >
            Esporta scheda metadati
          </button>
        </Modal>
      )}
      {gameId !== null && (
        <GameEvidence
          gameId={gameId}
          devices={devices}
          onClose={() => {
            setGameId(null);
            setRevision((v) => v + 1);
            void refresh();
          }}
        />
      )}
      {matching && (
        <Modal
          title="Anteprima associazioni conservative"
          onClose={() => setMatching(null)}
        >
          <p>
            Vengono riempiti soltanto campi vuoti o titoli ancora uguali al nome
            del file, dopo una validazione DAT. I campi modificati manualmente
            sono conservati.
          </p>
          <pre className="report-preview">
            {JSON.stringify(matching.result, null, 2)}
          </pre>
          <button
            disabled={busy || !selected.length || !source}
            onClick={() => {
              void queue("/metadata", {
                source_id: source,
                game_ids: selected,
                apply: true,
              });
              setMatching(null);
            }}
          >
            Applica alla selezione corrente dopo nuova verifica
          </button>
        </Modal>
      )}
    </div>
  );
}

type Queue = (path: string, body: unknown) => Promise<void>;
type Action = (
  operation: () => Promise<unknown>,
  message?: string,
) => Promise<void>;
function CatalogImports({
  sources,
  devices,
  platforms,
  busy,
  queue,
}: {
  sources: Source[];
  devices: Device[];
  platforms: Record<string, string>;
  busy: boolean;
  queue: Queue;
}) {
  const [form, setForm] = useState({
    source_id: "",
    name: "",
    path: "",
    format: "auto",
    platform: "arcade",
    core: "",
    version: "",
    source_url: "",
    revision: "",
  });
  const [device, setDevice] = useState("");
  const change = (key: string, value: string) =>
    setForm((f) => ({ ...f, [key]: value }));
  return (
    <>
      <section className="panel">
        <h2>Cataloghi ufficiali dei core</h2>
        <p>
          Acquisisce esclusivamente metadati con verifica dell’hash Git. Il DAT
          FBNeo della revisione installata richiede un rilevamento SSH in sola
          lettura.
        </p>
        <label>
          Raspberry per FBNeo
          <select value={device} onChange={(e) => setDevice(e.target.value)}>
            <option value="">Seleziona dispositivo</option>
            {devices.map((d) => (
              <option key={d.id} value={d.id}>
                {d.config.name}
              </option>
            ))}
          </select>
        </label>
        <div className="button-row">
          <button
            disabled={busy}
            onClick={() =>
              void queue("/official-catalogs", { provider: "mame2003" })
            }
          >
            Importa DAT MAME 0.78
          </button>
          <button
            disabled={busy || !device}
            onClick={() =>
              void queue("/official-catalogs", {
                provider: "fbneo-installed",
                device_id: device,
              })
            }
          >
            Importa DAT FBNeo installato
          </button>
          <button
            disabled={busy}
            onClick={() =>
              void queue("/official-catalogs", { provider: "fbneo-current" })
            }
          >
            FBNeo attuale · solo esplorazione
          </button>
        </div>
      </section>
      <form
        className="panel"
        onSubmit={(e) => {
          e.preventDefault();
          void queue("/imports", form);
        }}
      >
        <h2>Importa DAT / XML / JSON / CSV</h2>
        <p>
          Il file deve trovarsi in una sorgente autorizzata nelle Impostazioni,
          oppure nella cartella dati catalogs. Riutilizza lo stesso ID per
          aggiornare un catalogo. Annullamenti ed errori conservano la versione
          precedente.
        </p>
        <div className="intel-filters">
          <label>
            ID catalogo
            <input
              required
              pattern="[a-zA-Z0-9_-]{1,80}"
              value={form.source_id}
              onChange={(e) => change("source_id", e.target.value)}
              placeholder="es. archivio-mame078"
            />
          </label>
          <label>
            Nome catalogo
            <input
              required
              value={form.name}
              onChange={(e) => change("name", e.target.value)}
            />
          </label>
          <label className="wide">
            Percorso del manifest
            <input
              required
              value={form.path}
              onChange={(e) => change("path", e.target.value)}
              placeholder="C:\Cataloghi\manifest.xml"
            />
          </label>
          <label>
            Formato
            <select
              value={form.format}
              onChange={(e) => change("format", e.target.value)}
            >
              {["auto", "xml", "dat", "json", "csv"].map((f) => (
                <option key={f}>{f}</option>
              ))}
            </select>
          </label>
          <label>
            Piattaforma predefinita
            <select
              value={form.platform}
              onChange={(e) => change("platform", e.target.value)}
            >
              {Object.entries(platforms).map(([id, label]) => (
                <option value={id} key={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Core del DAT
            <select
              value={form.core}
              onChange={(e) => change("core", e.target.value)}
            >
              <option value="">Non specificato</option>
              <option>lr-mame2003</option>
              <option>lr-fbneo</option>
            </select>
          </label>
          <label>
            Versione del ROM set
            <input
              value={form.version}
              onChange={(e) => change("version", e.target.value)}
              placeholder="0.78 oppure versione DAT"
            />
          </label>
          <label>
            URL originale
            <input
              type="url"
              value={form.source_url}
              onChange={(e) => change("source_url", e.target.value)}
            />
          </label>
          <label>
            Revisione Git (se nota)
            <input
              value={form.revision}
              onChange={(e) => change("revision", e.target.value)}
            />
          </label>
        </div>
        <button className="primary" disabled={busy}>
          Avvia importazione catalogo
        </button>
      </form>
      <section className="panel">
        <h2>Cataloghi disponibili</h2>
        {sources.map((s) => (
          <div className="intel-run" key={s.id}>
            <div>
              <strong>
                {s.name} · {count(s.count)}
              </strong>
              <span>
                {s.id} · {s.config.core || "Core non specificato"} ·{" "}
                {s.config.version || "Versione non dichiarata"}
              </span>
              <code>{s.sha256}</code>
            </div>
          </div>
        ))}
        {!sources.length && <p>Nessun DAT importato.</p>}
      </section>
    </>
  );
}

function CoreProfiles({
  devices,
  sources,
  busy,
  queue,
  action,
}: {
  devices: Device[];
  sources: Source[];
  busy: boolean;
  queue: Queue;
  action: Action;
}) {
  const [device, setDevice] = useState("");
  const [core, setCore] = useState("lr-fbneo");
  const [platform, setPlatform] = useState("neogeo");
  const [source, setSource] = useState("");
  const [evidence, setEvidence] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const current = devices.find((d) => d.id === device);
  const audit = current?.diagnostics.arcade;
  return (
    <>
      <section className="panel">
        <h2>Core realmente installati</h2>
        <p>
          Legge versione e hash dei core, configurazioni, capacità e presenza
          del BIOS. Non installa emulatori e non riavvia servizi o
          EmulationStation.
        </p>
        <label>
          Dispositivo
          <select value={device} onChange={(e) => setDevice(e.target.value)}>
            <option value="">Seleziona Raspberry</option>
            {devices.map((d) => (
              <option value={d.id} key={d.id}>
                {d.config.name} · {d.config.host}
              </option>
            ))}
          </select>
        </label>
        <button
          disabled={busy || !device}
          className="primary"
          onClick={() => void queue(`/devices/${device}/audit`, {})}
        >
          Rileva core e BIOS · sola lettura
        </button>
        {audit && (
          <>
            <p>
              Ultima lettura:{" "}
              {new Date(audit.checked_at).toLocaleString("it-IT")} ·{" "}
              {bytes(audit.space.free)} liberi su {bytes(audit.space.total)}
            </p>
            <div className="provider-grid">
              {Object.entries(audit.cores).map(([id, c]) => (
                <div className="provider-card" key={id}>
                  <strong>{id}</strong>
                  <p>
                    {c.installed
                      ? c.version || "Versione non rilevata"
                      : "Non installato"}
                  </p>
                  <code>{c.sha256}</code>
                  {c.error && <p>{c.error}</p>}
                </div>
              ))}
            </div>
            <h3>BIOS Neo Geo rilevati</h3>
            {audit.bios_inventory.length ? (
              audit.bios_inventory.map((b) => (
                <p key={b.path}>
                  {b.path} · {bytes(b.size)} · presenza rilevata; i componenti
                  vengono verificati nel dry-run.
                </p>
              ))
            ) : (
              <div className="message">
                Nessun BIOS Neo Geo trovato nelle posizioni controllate. Se
                necessario, importa manualmente un BIOS ottenuto legittimamente.
                Nessun BIOS viene scaricato.
              </div>
            )}
            <h3>Sessione EmulationStation</h3>
            {audit.emulationstation_sessions.length ? (
              audit.emulationstation_sessions.map((s) => (
                <p key={s.pid}>
                  PID {s.pid} · TTY_NR={s.tty_nr} ·{" "}
                  {s.valid_local_session
                    ? "Sessione locale valida rilevata"
                    : "Terminale locale non valido: non avviare giochi da questa sessione"}
                </p>
              ))
            ) : (
              <p>Nessuna sessione attiva rilevata.</p>
            )}
            <details>
              <summary>Core e configurazioni rilevati</summary>
              <pre className="report-preview">
                {JSON.stringify(
                  { installed: audit.installed_cores, configs: audit.configs },
                  null,
                  2,
                )}
              </pre>
            </details>
          </>
        )}
      </section>
      <section className="panel">
        <h2>Preferenza core per sistema</h2>
        <p>
          La preferenza viene salvata localmente. Prima del trasferimento si
          verifica che corrisponda al default o all’override del gioco sul
          Raspberry. Eventuali modifiche di runcommand vanno effettuate nella
          sessione locale.
        </p>
        <div className="intel-filters">
          <label>
            Sistema
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
            >
              {["neogeo", "arcade", "fba", "mame-libretro"].map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </label>
          <label>
            Core preferito
            <select value={core} onChange={(e) => setCore(e.target.value)}>
              <option>lr-fbneo</option>
              <option>lr-mame2003</option>
            </select>
          </label>
        </div>
        <button
          disabled={busy || !device}
          onClick={() =>
            void action(
              () =>
                intel("/core-preferences", "POST", {
                  device_id: device,
                  platform,
                  core,
                  confirmed: true,
                }),
              "Preferenza locale salvata.",
            )
          }
        >
          Salva preferenza locale
        </button>
      </section>
      <section className="panel">
        <h2>Associazione documentata DAT / core</h2>
        <p>
          MAME 2003 richiede 0.78. Per FBNeo usa il DAT della revisione
          rilevata. Se la revisione non è incorporata nel core, registra una
          prova di corrispondenza: l’associazione viene fissata agli hash del
          DAT e del binario, senza trasformarla in un test di gioco.
        </p>
        <label>
          DAT da associare
          <select value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="">Scegli DAT</option>
            {sources
              .filter((s) => s.config.core === core)
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
          </select>
        </label>
        <label>
          Prova della corrispondenza
          <textarea
            minLength={12}
            value={evidence}
            onChange={(e) => setEvidence(e.target.value)}
            placeholder="Build, origine del DAT e riferimento verificabile"
          />
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          />
          Confermo la corrispondenza documentata, non solo un numero di versione
          simile.
        </label>
        <button
          disabled={
            busy || !device || !source || !confirmed || evidence.length < 12
          }
          onClick={() =>
            void action(
              () =>
                intel("/bindings", "POST", {
                  device_id: device,
                  source_id: source,
                  core,
                  evidence,
                  confirmed: true,
                }),
              "Associazione salvata agli hash rilevati.",
            )
          }
        >
          Registra associazione
        </button>
      </section>
    </>
  );
}

function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section
        className="modal intel-modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="section-heading">
          <h2>{title}</h2>
          <button aria-label="Chiudi dettaglio" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}

function GameEvidence({
  gameId,
  devices,
  onClose,
}: {
  gameId: number;
  devices: Device[];
  onClose: () => void;
}) {
  const [data, setData] = useState<{
    game: Game;
    insight: Insight | null;
    validation: Validation | null;
    sync: unknown[];
  } | null>(null);
  const [form, setForm] = useState({
    preferred_core: "",
    machine_mode: "unknown",
    test_status: "untested",
    device_id: "",
    evidence: "",
    screenshot_path: "",
    media_rights_confirmed: false,
  });
  const [error, setError] = useState("");
  useEffect(() => {
    void intel<typeof data>(`/games/${gameId}`)
      .then((d) => {
        setData(d);
        if (d?.insight) {
          const i = d.insight;
          setForm({
            preferred_core: i.preferred_core,
            machine_mode: i.machine_mode,
            test_status: i.test_status,
            device_id: i.test_evidence.device_id || "",
            evidence: i.test_evidence.note || "",
            screenshot_path: i.screenshot_path,
            media_rights_confirmed: false,
          });
        }
      })
      .catch((e) => setError(String(e)));
  }, [gameId]);
  const change = (key: string, value: string | boolean) =>
    setForm((f) => ({ ...f, [key]: value }));
  return (
    <Modal title={data?.game.title || "Dettaglio file"} onClose={onClose}>
      {error && (
        <div className="message error" role="alert">
          {error}
        </div>
      )}
      {data && (
        <>
          <div className="intel-badges">
            <span>{stateLabel(data.validation?.status || "unvalidated")}</span>
            <span>{stateLabel(data.insight?.test_status || "untested")}</span>
            <span>
              {data.sync.length
                ? "Sincronizzazione registrata"
                : "Nessuna sincronizzazione registrata"}
            </span>
          </div>
          <p>
            <code>{data.game.local_path}</code>
          </p>
          <p>
            SHA-256 <code>{data.game.sha256}</code>
          </p>
          {data.validation && (
            <section>
              <p>
                DAT:{" "}
                {data.validation.report.source_version ||
                  "Versione non dichiarata"}{" "}
                · {data.validation.report.core || "Core da verificare"} ·{" "}
                {data.validation.mode}
              </p>
              <p>
                Compatibilità con il dispositivo: da verificare nel dry-run.{" "}
                {data.validation.report.launch_note}
              </p>
              <p>
                BIOS richiesti:{" "}
                {data.validation.report.bios.join(", ") || "Nessuno dichiarato"}
              </p>
              {data.validation.report.problems.slice(0, 50).map((p, i) => (
                <p className="error-text" key={i}>
                  {p.set} / {p.file}: {p.reason}
                </p>
              ))}
              <button
                onClick={() =>
                  saveReport(data.validation, `validation-${gameId}.json`)
                }
              >
                Scarica report di validazione
              </button>
            </section>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void intel(`/games/${gameId}`, "PUT", {
                ...form,
                confirmed: true,
              })
                .then(onClose)
                .catch((e) => setError(String(e)));
            }}
          >
            <div className="intel-filters">
              {["arcade", "neogeo", "mame-libretro", "fba"].includes(
                data.game.platform,
              ) && (
                <label>
                  Core preferito per questo gioco
                  <select
                    value={form.preferred_core}
                    onChange={(e) => change("preferred_core", e.target.value)}
                  >
                    <option value="">Usa preferenza del sistema / DAT</option>
                    <option>lr-fbneo</option>
                    <option>lr-mame2003</option>
                  </select>
                </label>
              )}
              {["arcade", "neogeo", "mame-libretro", "fba"].includes(
                data.game.platform,
              ) && (
                <label>
                  Modalità Neo Geo
                  <select
                    value={form.machine_mode}
                    onChange={(e) => change("machine_mode", e.target.value)}
                  >
                    <option value="unknown">Non specificata</option>
                    <option>MVS</option>
                    <option>AES</option>
                  </select>
                </label>
              )}
              <label>
                Esito test effettivo
                <select
                  value={form.test_status}
                  onChange={(e) => change("test_status", e.target.value)}
                >
                  <option value="untested">Mai testato</option>
                  <option value="passed">Avviato correttamente</option>
                  <option value="failed">Test non riuscito</option>
                </select>
              </label>
              <label>
                Raspberry del test
                <select
                  value={form.device_id}
                  onChange={(e) => change("device_id", e.target.value)}
                >
                  <option value="">Scegli dispositivo</option>
                  {devices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.config.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              Prova / osservazioni del test
              <textarea
                value={form.evidence}
                onChange={(e) => change("evidence", e.target.value)}
                placeholder="Data, sessione di gioco, controller, risultati e problemi osservati"
              />
            </label>
            <p>
              Il test è una dichiarazione dell’operatore associata al
              dispositivo e all’hash del file, distinta dalla verifica
              automatica degli archivi.
            </p>
            <label>
              Screenshot locale autorizzato
              <input
                value={form.screenshot_path}
                onChange={(e) => change("screenshot_path", e.target.value)}
                placeholder="Percorso PNG/JPG/WebP in una sorgente autorizzata"
              />
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={form.media_rights_confirmed}
                onChange={(e) =>
                  change("media_rights_confirmed", e.target.checked)
                }
              />
              Confermo di poter utilizzare lo screenshot indicato.
            </label>
            {data.insight?.screenshot_path && (
              <img
                className="game-screenshot"
                src={`/api/intelligence/games/${gameId}/screenshot`}
                alt="Screenshot registrato del gioco"
              />
            )}
            <button className="primary">Salva evidenze e preferenze</button>
          </form>
        </>
      )}
    </Modal>
  );
}
