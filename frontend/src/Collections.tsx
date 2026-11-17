import { useCallback, useEffect, useState } from "react";
import {
  BookOpen,
  Gamepad2,
  Heart,
  ImageIcon,
  Library,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { api, type Game } from "./api";
import "./collections.css";

export type CollectionView =
  | "Grandi Classici"
  | "Collezione Completa"
  | "Da Recuperare"
  | "Qualità e media";
type Owned = Game & {
  classic_id: string | null;
  in_classics: boolean;
  membership: string;
  position: number;
  availability: string;
  compatibility: string;
  synchronized: boolean;
  test_status: string;
  metadata_status: string;
  metadata_note: string;
  cover_available: boolean;
  screenshot_available: boolean;
};
type Classic = {
  id: string;
  title: string;
  platform: string;
  genre: string;
  year: number | null;
  present: boolean;
  compatibility: string;
  details: {
    selection_reason: string;
    developer: string | null;
    publisher: string | null;
    sources: { url: string; revision?: string }[];
    identifiers: { source: string; name: string; serial?: string }[];
    official_sources: { url: string; name: string }[];
  };
};
type Summary = {
  catalogued: number;
  present_classics: number;
  missing_classics: number;
  collection_games: number;
  games: number;
  covers: number;
  screenshots: number;
  review_needed: number;
  fields: Record<string, { count: number; percent: number }>;
};
type Candidate = {
  id: string;
  game_id: number;
  title: string;
  kind: string;
  recommended: boolean;
  match_basis: string;
  asset: { license: string; source_url: string };
};
type MediaPlan = {
  id: string;
  candidates: Candidate[];
  unresolved: { game_id: number; reason: string }[];
};
type Run<T> = { id: string; status: string; error: string; result: T };

export function chooseCandidate(
  current: string[],
  candidate: Candidate,
  candidates: Candidate[],
  checked: boolean,
) {
  const siblings = new Set(
    candidates
      .filter(
        (c) => c.game_id === candidate.game_id && c.kind === candidate.kind,
      )
      .map((c) => c.id),
  );
  return checked
    ? [...current.filter((id) => !siblings.has(id)), candidate.id]
    : current.filter((id) => id !== candidate.id);
}

async function waitRun<T>(id: string): Promise<T> {
  for (let n = 0; n < 600; n++) {
    const run = await api<Run<T>>(`/intelligence/runs/${id}`);
    if (run.status === "completed") return run.result;
    if (["failed", "cancelled"].includes(run.status))
      throw new Error(run.error);
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("Operazione ancora in corso: controlla la cronologia.");
}
const labels: Record<string, string> = {
  title: "Titolo",
  genre: "Genere",
  year: "Anno",
  author: "Sviluppatore",
  publisher: "Publisher",
  description: "Descrizione",
  cover_available: "Copertina",
  screenshot_available: "Screenshot",
  unverified: "Da verificare",
  verified: "Verificati",
  review: "Da revisionare",
  validated_set: "Set DAT completo",
  incomplete: "Set incompleto",
  untested: "Non testato",
  passed: "Test riuscito",
  failed: "Test fallito",
  present: "File presenti",
  missing_file: "File mancanti",
};

function Placeholder({ title, platform }: { title: string; platform: string }) {
  return (
    <div
      className="collection-placeholder"
      aria-label={`Immagine mancante per ${title}`}
    >
      <Gamepad2 size={38} strokeWidth={1} />
      <strong>{title}</strong>
      <span>{platform}</span>
    </div>
  );
}

export default function Collections({
  view,
  platforms,
  onImport,
  onSync,
}: {
  view: CollectionView;
  platforms: Record<string, string>;
  onImport: () => void;
  onSync: (ids: number[]) => void;
}) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [items, setItems] = useState<Owned[]>([]);
  const [classics, setClassics] = useState<Classic[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [filters, setFilters] = useState({
    platform: "",
    genre: "",
    availability: "",
    compatibility: "",
    synced: "",
    test_status: "",
    metadata_status: "",
    sort: "title",
    favorite: "false",
  });
  const [detail, setDetail] = useState<Owned | null>(null);
  const [classicDetail, setClassicDetail] = useState<Classic | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [mediaPlan, setMediaPlan] = useState<MediaPlan | null>(null);
  const [selectedMedia, setSelectedMedia] = useState<string[]>([]);
  const [replaceMedia, setReplaceMedia] = useState(false);
  const [classicQuery, setClassicQuery] = useState("");
  const [matches, setMatches] = useState<Classic[]>([]);
  const [classicId, setClassicId] = useState("");
  const [identity, setIdentity] = useState(false);
  const [reviewNote, setReviewNote] = useState("");
  const [localMedia, setLocalMedia] = useState({
    kind: "cover",
    path: "",
    source: "",
    license: "",
    confirmed: false,
  });
  const missing = view === "Da Recuperare";
  const reload = useCallback(async () => {
    const params = new URLSearchParams({
      ...filters,
      q,
      page: String(page),
      view: view === "Grandi Classici" ? "classics" : "all",
    });
    const [s, data] = await Promise.all([
      api<Summary>("/collections/summary"),
      missing
        ? api<{ items: Classic[]; total: number }>(
            `/collections/classics?${params}`,
          )
        : api<{ items: Owned[]; total: number }>(
            `/collections/owned?${params}`,
          ),
    ]);
    setSummary(s);
    setTotal(data.total);
    if (missing) setClassics(data.items as Classic[]);
    else setItems(data.items as Owned[]);
  }, [filters, q, page, missing, view]);
  useEffect(() => {
    const timer = setTimeout(() => {
      reload().catch((e) => setError(String(e)));
    }, 180);
    return () => clearTimeout(timer);
  }, [reload]);
  async function action(label: string, operation: () => Promise<void>) {
    setBusy(label);
    setError("");
    try {
      await operation();
      await reload();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy("");
    }
  }
  function filter(key: keyof typeof filters, value: string) {
    setFilters((old) => ({ ...old, [key]: value }));
    setPage(1);
  }
  async function curate(game: Owned, mode: string, position = game.position) {
    await api(`/collections/games/${game.id}`, "PUT", { mode, position });
    setDetail(null);
  }
  async function previewMedia() {
    const run = await api<{ id: string }>("/media/plans", "POST", {
      game_ids: [],
      replace_existing: replaceMedia,
    });
    const plan = await waitRun<MediaPlan>(run.id);
    setMediaPlan(plan);
    setSelectedMedia(
      plan.candidates.filter((c) => c.recommended).map((c) => c.id),
    );
  }
  async function syncAll() {
    const ids: number[] = [];
    for (let p = 1; ; p++) {
      const result = await api<{ items: Owned[]; total: number }>(
        `/collections/owned?page=${p}&page_size=100&availability=present`,
      );
      ids.push(...result.items.map((x) => x.id));
      if (p * 100 >= result.total) break;
    }
    if (ids.length) onSync(ids);
    else setNotice("Nessuna copia locale da sincronizzare.");
  }
  function open(game: Owned) {
    setDetail(game);
    setReviewNote(game.metadata_note);
    setClassicQuery(game.title);
    setMatches([]);
    setClassicId("");
    setIdentity(false);
  }

  return (
    <section className="collections-hub">
      <div className="collection-hero">
        <div>
          <span className="eyebrow">
            ESSENTIAL CLASSICS · LA TUA COLLEZIONE
          </span>
          <h2>
            {view === "Grandi Classici"
              ? "I giochi che scegli di ricordare."
              : view === "Da Recuperare"
                ? "Il prossimo capitolo della tua collezione."
                : view === "Qualità e media"
                  ? "Ogni gioco, presentato al meglio."
                  : "Tutta la tua storia, in un solo posto."}
          </h2>
          <p>
            {missing
              ? "Un catalogo curato di riferimenti. Questi titoli non risultano nella tua libreria: importa una copia locale e verifica la sua identità."
              : view === "Grandi Classici"
                ? "Solo copie locali: selezione automatica per identificativi verificati e scelte manuali. La raccolta completa rimane sempre accessibile."
                : "Classici e homebrew, con disponibilità, metadati e prove di test distinti."}
          </p>
        </div>
        <Library size={56} strokeWidth={1} />
      </div>
      {error && (
        <div role="alert" className="error-banner">
          {error}
        </div>
      )}
      {notice && (
        <div role="status" className="notice">
          {notice}
        </div>
      )}
      {busy && <p role="status">{busy}…</p>}
      {summary && (
        <div className="collection-stats">
          {[
            ["Classici catalogati", summary.catalogued],
            ["Classici presenti", summary.present_classics],
            ["Da recuperare", summary.missing_classics],
            ["Copertine", `${summary.covers}/${summary.games}`],
            ["Screenshot", `${summary.screenshots}/${summary.games}`],
          ].map(([name, value]) => (
            <div key={name}>
              <span>{name}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      )}
      <div className="button-row collection-actions">
        <button
          disabled={!!busy}
          onClick={() =>
            action("Verifica delle identità", async () => {
              const run = await api<{ id: string }>(
                "/collections/match",
                "POST",
              );
              const result = await waitRun<{
                matched: unknown[];
                unresolved: unknown[];
              }>(run.id);
              setNotice(
                `${result.matched.length} copie identificate tramite hash/DAT; ${result.unresolved.length} senza associazione automatica.`,
              );
            })
          }
        >
          <Sparkles size={16} /> Riconosci classici
        </button>
        <button onClick={onImport}>
          <BookOpen size={16} /> Importa copia locale
        </button>
        <button
          disabled={!!busy}
          onClick={() => action("Preparazione selezione", syncAll)}
        >
          Sincronizza libreria e raccolta
        </button>
      </div>
      {view === "Qualità e media" && summary && (
        <>
          <div className="quality-grid">
            {Object.entries(summary.fields).map(([field, value]) => (
              <div key={field}>
                <span>{labels[field]}</span>
                <strong>{value.percent}%</strong>
                <progress max="100" value={value.percent} />
                <small>
                  {value.count} su {summary.games}
                </small>
              </div>
            ))}
          </div>
          <p>
            {summary.review_needed} giochi da verificare o completare. Un campo
            vuoto indica un dato sconosciuto; un trasferimento non è una prova
            di avvio.
          </p>
          <div className="media-toolbar">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={replaceMedia}
                onChange={(e) => setReplaceMedia(e.target.checked)}
              />{" "}
              Includi immagini già associate per correggerle
            </label>
            <button
              className="primary"
              disabled={!!busy}
              onClick={() => action("Ricerca media autorizzati", previewMedia)}
            >
              <ImageIcon size={17} /> Trova media autorizzati
            </button>
          </div>
          <p className="muted">
            Provider GBDev, GBADev, NESDev e fonti homebrew revisionate: solo immagini con licenza degli
            asset esplicita e identità della ROM verificata. Aggiorna le fonti
            in Game Discovery per cercare nuove immagini.
          </p>
        </>
      )}
      <div className="collection-filters">
        <label className="search-box">
          <Search size={17} />
          <input
            aria-label="Cerca nelle collezioni"
            placeholder="Cerca un titolo…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <select
          aria-label="Console collezioni"
          value={filters.platform}
          onChange={(e) => filter("platform", e.target.value)}
        >
          <option value="">Tutte le console</option>
          {Object.entries(platforms).map(([id, name]) => (
            <option key={id} value={id}>
              {name}
            </option>
          ))}
        </select>
        {!missing && (
          <>
            <input
              aria-label="Genere collezioni"
              placeholder="Genere"
              value={filters.genre}
              onChange={(e) => filter("genre", e.target.value)}
            />
            <select
              aria-label="Ordina collezioni"
              value={filters.sort}
              onChange={(e) => filter("sort", e.target.value)}
            >
              <option value="title">Titolo</option>
              <option value="year">Anno</option>
              <option value="manual">Ordine manuale</option>
              <option value="favorites">Preferiti prima</option>
            </select>
            <select
              aria-label="Disponibilità"
              value={filters.availability}
              onChange={(e) => filter("availability", e.target.value)}
            >
              <option value="">Disponibilità: tutte</option>
              <option value="present">File presenti</option>
              <option value="missing_file">File mancanti</option>
            </select>
            <select
              aria-label="Compatibilità"
              value={filters.compatibility}
              onChange={(e) => filter("compatibility", e.target.value)}
            >
              <option value="">Compatibilità: tutte</option>
              <option value="validated_set">Set DAT completo</option>
              <option value="incomplete">Set incompleto</option>
              <option value="unverified">Da verificare</option>
            </select>
            <select
              aria-label="Sincronizzazione"
              value={filters.synced}
              onChange={(e) => filter("synced", e.target.value)}
            >
              <option value="">Sincronizzazione: tutte</option>
              <option value="yes">Sincronizzati</option>
              <option value="no">Non sincronizzati</option>
            </select>
            <select
              aria-label="Test Raspberry"
              value={filters.test_status}
              onChange={(e) => filter("test_status", e.target.value)}
            >
              <option value="">Test Raspberry: tutti</option>
              <option value="passed">Test riuscito</option>
              <option value="failed">Test fallito</option>
              <option value="untested">Non testato</option>
            </select>
            <select
              aria-label="Verifica metadati"
              value={filters.metadata_status}
              onChange={(e) => filter("metadata_status", e.target.value)}
            >
              <option value="">Metadati: tutti</option>
              <option value="unverified">Da verificare</option>
              <option value="review">Da revisionare</option>
              <option value="verified">Verificati</option>
            </select>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={filters.favorite === "true"}
                onChange={(e) => filter("favorite", String(e.target.checked))}
              />{" "}
              Solo preferiti
            </label>
          </>
        )}
      </div>
      <p className="muted">
        {total.toLocaleString("it-IT")}{" "}
        {missing ? "titoli da recuperare" : "copie in libreria"}
      </p>
      <div className="collection-grid">
        {missing
          ? classics.map((game) => (
              <article className="collection-card" key={game.id}>
                <button
                  className="collection-art"
                  onClick={() => setClassicDetail(game)}
                >
                  <Placeholder
                    title={game.title}
                    platform={platforms[game.platform] || game.platform}
                  />
                </button>
                <div className="collection-card-body">
                  <span className="collection-chip missing">
                    Da recuperare · non installato
                  </span>
                  <h3>{game.title}</h3>
                  <p>
                    {platforms[game.platform]} ·{" "}
                    {game.year ?? "Anno sconosciuto"}
                  </p>
                  <small>{game.genre || "Genere sconosciuto"}</small>
                  <button onClick={() => setClassicDetail(game)}>
                    Fonti e dettagli
                  </button>
                </div>
              </article>
            ))
          : items.map((game) => (
              <article className="collection-card" key={game.id}>
                <button className="collection-art" onClick={() => open(game)}>
                  {game.cover_available ? (
                    <img
                      loading="lazy"
                      src={`/api/media/games/${game.id}/cover`}
                      alt={`Copertina di ${game.title}`}
                    />
                  ) : (
                    <Placeholder
                      title={game.title}
                      platform={platforms[game.platform] || game.platform}
                    />
                  )}
                </button>
                <div className="collection-card-body">
                  <div className="collection-card-top">
                    <span className="collection-chip">
                      {game.in_classics ? "Grandi Classici" : "Libreria"}
                    </span>
                    <button
                      aria-label={`Preferito ${game.title}`}
                      aria-pressed={game.favorite}
                      onClick={() =>
                        action("Salvataggio preferito", async () => {
                          await api(`/games/${game.id}/favorite`, "PATCH", {
                            favorite: !game.favorite,
                          });
                        })
                      }
                    >
                      <Heart
                        size={17}
                        fill={game.favorite ? "currentColor" : "none"}
                      />
                    </button>
                  </div>
                  <h3>
                    <button onClick={() => open(game)}>{game.title}</button>
                  </h3>
                  <p>
                    {platforms[game.platform]} ·{" "}
                    {game.year ?? "Anno sconosciuto"}
                  </p>
                  <small>{game.genre || "Genere sconosciuto"}</small>
                  <div className="collection-status">
                    <span>{labels[game.availability]}</span>
                    <span>
                      {game.synchronized ? "Sincronizzato" : "Da sincronizzare"}
                    </span>
                    <span>{labels[game.test_status] || game.test_status}</span>
                  </div>
                </div>
              </article>
            ))}
      </div>
      {total === 0 && (
        <div className="empty">
          <Library size={40} />
          <h3>
            {view === "Grandi Classici"
              ? "La raccolta aspetta i tuoi classici"
              : "Nessun risultato"}
          </h3>
          <p>
            {view === "Grandi Classici"
              ? "Riconosci le copie presenti oppure aggiungi manualmente un gioco dalla Collezione Completa."
              : "Modifica i filtri o importa una copia locale."}
          </p>
        </div>
      )}
      {total > 36 && (
        <div className="pagination">
          <button disabled={page === 1} onClick={() => setPage(page - 1)}>
            Precedente
          </button>
          <span>
            {page} / {Math.ceil(total / 36)}
          </span>
          <button
            disabled={page * 36 >= total}
            onClick={() => setPage(page + 1)}
          >
            Successiva
          </button>
        </div>
      )}
      {classicDetail && (
        <div className="modal-backdrop">
          <section
            className="modal collection-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Dettaglio classico"
          >
            <button
              className="close"
              aria-label="Chiudi dettaglio classico"
              onClick={() => setClassicDetail(null)}
            >
              <X />
            </button>
            <h2>{classicDetail.title}</h2>
            <p>
              {platforms[classicDetail.platform]} ·{" "}
              {classicDetail.year ?? "Anno sconosciuto"} ·{" "}
              {classicDetail.genre || "Genere sconosciuto"}
            </p>
            <p>
              <strong>Non presente nella libreria.</strong> Disponibilità di una
              ROM autorizzata non verificata. Importa una copia locale
              legittimamente acquisita.
            </p>
            <p>
              {classicDetail.compatibility}. Per arcade e Neo Geo servono il set
              corretto e le dipendenze BIOS.
            </p>
            <p>{classicDetail.details.selection_reason}</p>
            <dl>
              <dt>Sviluppatore</dt>
              <dd>{classicDetail.details.developer || "Sconosciuto"}</dd>
              <dt>Publisher</dt>
              <dd>{classicDetail.details.publisher || "Sconosciuto"}</dd>
            </dl>
            <h3>Identificatori e fonti</h3>
            <p>
              {classicDetail.details.identifiers
                .slice(0, 4)
                .map((i) => i.serial || i.name)
                .join(" · ")}
            </p>
            {classicDetail.details.sources.map((s, i) => (
              <p key={s.url}>
                <a href={s.url} target="_blank" rel="noreferrer">
                  Fonte metadati {i + 1} · revisione {s.revision?.slice(0, 8)}
                </a>
              </p>
            ))}
            {classicDetail.details.official_sources.map((s) => (
              <p key={s.url}>
                <a href={s.url} target="_blank" rel="noreferrer">
                  {s.name}
                </a>
              </p>
            ))}
            <button className="primary" onClick={onImport}>
              Importa copia locale
            </button>
          </section>
        </div>
      )}
      {detail && (
        <div className="modal-backdrop">
          <section
            className="modal collection-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Dettaglio gioco collezione"
          >
            <button
              className="close"
              aria-label="Chiudi dettaglio gioco"
              onClick={() => setDetail(null)}
            >
              <X />
            </button>
            <h2>{detail.title}</h2>
            <div className="detail-media">
              {detail.cover_available ? (
                <img
                  src={`/api/media/games/${detail.id}/cover`}
                  alt="Copertina"
                />
              ) : (
                <Placeholder
                  title={detail.title}
                  platform="Copertina mancante"
                />
              )}
              {detail.screenshot_available ? (
                <img
                  src={`/api/media/games/${detail.id}/screenshot`}
                  alt="Screenshot"
                />
              ) : (
                <Placeholder
                  title={detail.title}
                  platform="Screenshot mancante"
                />
              )}
            </div>
            <p>
              {platforms[detail.platform]} · {detail.year ?? "Anno sconosciuto"}{" "}
              · {detail.genre || "Genere sconosciuto"}
            </p>
            <p>{detail.description || "Descrizione sconosciuta"}</p>
            <p>
              Sviluppatore: {detail.author || "sconosciuto"} · Publisher:{" "}
              {detail.publisher || "sconosciuto"}
            </p>
            <p>
              Metadati: {labels[detail.metadata_status]} ·{" "}
              {labels[detail.compatibility]} ·{" "}
              {labels[detail.test_status] || detail.test_status}
            </p>
            <div className="button-row">
              <button
                disabled={!!busy}
                onClick={() =>
                  action("Aggiornamento raccolta", () =>
                    curate(detail, detail.in_classics ? "exclude" : "include"),
                  )
                }
              >
                {detail.in_classics
                  ? "Rimuovi dai Grandi Classici"
                  : "Aggiungi ai Grandi Classici"}
              </button>
              <button
                onClick={() =>
                  action("Selezione automatica", () => curate(detail, "auto"))
                }
              >
                Usa selezione automatica
              </button>
            </div>
            <label>
              Posizione nella raccolta
              <input
                type="number"
                min="0"
                max="1000000"
                value={detail.position}
                onChange={(e) =>
                  setDetail({ ...detail, position: Number(e.target.value) })
                }
              />
            </label>
            <button
              onClick={() =>
                action("Salvataggio ordine", () =>
                  curate(detail, detail.membership, detail.position),
                )
              }
            >
              Salva ordine
            </button>
            <details>
              <summary>Identifica una copia del catalogo classici</summary>
              <p>
                Il nome simile non basta: verifica edizione, piattaforma e
                riferimenti prima di confermare.
              </p>
              <input
                aria-label="Cerca identità classico"
                value={classicQuery}
                onChange={(e) => setClassicQuery(e.target.value)}
              />
              <button
                onClick={() =>
                  action("Ricerca classico", async () => {
                    const result = await api<{ items: Classic[] }>(
                      `/collections/classics?missing=false&q=${encodeURIComponent(classicQuery)}&page_size=100`,
                    );
                    setMatches(result.items);
                  })
                }
              >
                Cerca riferimenti
              </button>
              <select
                aria-label="Identità classico"
                value={classicId}
                onChange={(e) => setClassicId(e.target.value)}
              >
                <option value="">Scegli il titolo verificato</option>
                {matches.map((x) => (
                  <option value={x.id} key={x.id}>
                    {x.title} · {platforms[x.platform]}
                  </option>
                ))}
              </select>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={identity}
                  onChange={(e) => setIdentity(e.target.checked)}
                />{" "}
                Ho verificato l'identità della mia copia
              </label>
              <button
                disabled={!identity || !classicId}
                onClick={() =>
                  action("Associazione identità", async () => {
                    await api(`/collections/games/${detail.id}`, "PUT", {
                      mode: "include",
                      classic_id: classicId,
                      identity_confirmed: true,
                      position: detail.position,
                    });
                    setDetail(null);
                  })
                }
              >
                Associa classico
              </button>
            </details>
            <details>
              <summary>Verifica dei metadati</summary>
              <textarea
                aria-label="Prova verifica metadati"
                placeholder="Fonte e controlli effettuati"
                value={reviewNote}
                onChange={(e) => setReviewNote(e.target.value)}
              />
              <button
                disabled={reviewNote.length < 12}
                onClick={() =>
                  action("Registrazione verifica", async () => {
                    await api(`/collections/games/${detail.id}/review`, "PUT", {
                      status: "verified",
                      note: reviewNote,
                    });
                    setDetail(null);
                  })
                }
              >
                Segna metadati verificati
              </button>
              <button
                onClick={() =>
                  action("Revisione metadati", async () => {
                    await api(`/collections/games/${detail.id}/review`, "PUT", {
                      status: "review",
                      note: reviewNote,
                    });
                    setDetail(null);
                  })
                }
              >
                Da revisionare
              </button>
            </details>
            <details>
              <summary>Correggi copertina o screenshot</summary>
              <p>
                Usa un'immagine della stessa edizione da una cartella di
                importazione configurata. La precedente associazione resta nella
                cronologia.
              </p>
              <select
                aria-label="Tipo immagine locale"
                value={localMedia.kind}
                onChange={(e) =>
                  setLocalMedia({ ...localMedia, kind: e.target.value })
                }
              >
                <option value="cover">Copertina</option>
                <option value="screenshot">Screenshot</option>
              </select>
              {(
                [
                  ["path", "Percorso immagine"],
                  ["source", "Fonte immagine"],
                  ["license", "Licenza immagine"],
                ] as const
              ).map(([key, label]) => (
                <label key={key}>
                  {label}
                  <input
                    aria-label={label}
                    value={localMedia[key]}
                    onChange={(e) =>
                      setLocalMedia({ ...localMedia, [key]: e.target.value })
                    }
                  />
                </label>
              ))}
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={localMedia.confirmed}
                  onChange={(e) =>
                    setLocalMedia({
                      ...localMedia,
                      confirmed: e.target.checked,
                    })
                  }
                />{" "}
                Confermo identità del gioco e diritto di utilizzo dell'immagine
              </label>
              <button
                disabled={!localMedia.confirmed || !!busy}
                onClick={() =>
                  action("Associazione immagine", async () => {
                    await api(`/media/games/${detail.id}/local`, "POST", {
                      kind: localMedia.kind,
                      path: localMedia.path,
                      source: localMedia.source,
                      license: localMedia.license,
                      rights_confirmed: true,
                      identity_confirmed: true,
                    });
                    setDetail(null);
                  })
                }
              >
                Usa immagine locale
              </button>
            </details>
          </section>
        </div>
      )}
      {mediaPlan && (
        <div className="modal-backdrop">
          <section
            className="modal collection-dialog media-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Anteprima media"
          >
            <button
              className="close"
              aria-label="Chiudi anteprima media"
              onClick={() => setMediaPlan(null)}
            >
              <X />
            </button>
            <h2>Anteprima associazioni</h2>
            <p>
              {mediaPlan.candidates.length} immagini candidate. Seleziona una
              copertina e uno screenshot per gioco; nessuna associazione basata
              soltanto sul titolo.
            </p>
            <div className="media-preview-grid">
              {mediaPlan.candidates.map((c) => (
                <label key={c.id} className="media-candidate">
                  <img
                    loading="lazy"
                    src={`/api/media/plans/${mediaPlan.id}/candidates/${c.id}/image`}
                    alt={`${c.kind} di ${c.title}`}
                  />
                  <strong>{c.title}</strong>
                  <span>
                    {c.kind === "cover" ? "Copertina" : "Screenshot"} ·{" "}
                    {c.asset.license}
                  </span>
                  <small>{c.match_basis}</small>
                  <input
                    type="checkbox"
                    aria-label={`Seleziona ${c.kind} ${c.title}`}
                    checked={selectedMedia.includes(c.id)}
                    onChange={(e) =>
                      setSelectedMedia(
                        chooseCandidate(
                          selectedMedia,
                          c,
                          mediaPlan.candidates,
                          e.target.checked,
                        ),
                      )
                    }
                  />
                </label>
              ))}
            </div>
            <details>
              <summary>
                {mediaPlan.unresolved.length} giochi senza associazione certa
              </summary>
              {mediaPlan.unresolved.map((x) => (
                <p key={x.game_id}>
                  Gioco {x.game_id}: {x.reason}
                </p>
              ))}
            </details>
            <button
              className="primary"
              disabled={!!busy || !selectedMedia.length}
              onClick={() =>
                action("Acquisizione media", async () => {
                  const run = await api<{ id: string }>(
                    `/media/plans/${mediaPlan.id}/confirm`,
                    "POST",
                    { confirmed: true, candidate_ids: selectedMedia },
                  );
                  const result = await waitRun<{
                    applied: unknown[];
                    failed: { error: string }[];
                  }>(run.id);
                  setNotice(
                    `${result.applied.length} immagini associate; ${result.failed.length} fallite. ${result.failed.map((x) => x.error).join("; ")}`,
                  );
                  setMediaPlan(null);
                })
              }
            >
              Conferma {selectedMedia.length} associazioni autorizzate
            </button>
          </section>
        </div>
      )}
    </section>
  );
}
