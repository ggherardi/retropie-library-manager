import { useCallback, useEffect, useState } from "react";
import {
  Cable,
  Check,
  CircleAlert,
  LoaderCircle,
  RefreshCw,
  Server,
  ShieldCheck,
} from "lucide-react";
import { api, bytes, waitForJob, type Game, type Job } from "./api";

type Config = {
  name: string;
  host: string;
  port: number;
  username: string;
  rom_root: string;
  bios_root: string;
  safety_bytes: number;
  chd_confirmed: boolean;
  is_default?: boolean;
};
type Diagnostic = {
  model?: string;
  hostname?: string;
  os?: string;
  retropie_version?: string;
  emulationstation_version?: string;
  ip?: string;
  uptime_seconds?: number;
  temperature_c?: number;
  ram_total?: number;
  ram_available?: number;
  space?: { total: number; free: number };
  directories?: Record<
    string,
    { path: string; exists: boolean; readable: boolean; writable: boolean }
  >;
  ssh_service?: string;
  es_running?: boolean;
  es_root?: string;
  systems_config?: string;
  psx_emulator_config?: string;
};
type Device = {
  id: string;
  config: Config;
  fingerprint: string;
  is_default: boolean;
  status: string;
  diagnostics: Diagnostic;
  error: string;
};
type SyncFile = {
  path: string;
  size: number;
  state: string;
  kind: string;
  game_id?: number;
};
type Plan = {
  groups: { id: number; title: string; path: string; files: SyncFile[] }[];
  media: SyncFile[];
  gamelists: SyncFile[];
  required_bytes: number;
  free_bytes: number;
  safety_bytes: number;
  warnings: string[];
  blocked: string[];
  can_sync: boolean;
};
type Run = {
  id: string;
  device_id: string;
  status: string;
  error: string;
  created_at: string;
  plan: Plan;
  progress: {
    file?: string;
    file_bytes?: number;
    file_total?: number;
    bytes?: number;
    total?: number;
    attempt?: number;
  };
  report: {
    transferred_bytes?: number;
    skipped_files?: number;
    metadata_deferred?: boolean;
    backups?: string[];
    gamelists?: { path: string; status: string }[];
    space_after?: { free: number };
  };
};
const defaults: Config = {
  name: "",
  host: "",
  port: 22,
  username: "pi",
  rom_root: "/home/pi/RetroPie/roms",
  bios_root: "/home/pi/RetroPie/BIOS",
  safety_bytes: 1e9,
  chd_confirmed: false,
};
const labels: Record<string, string> = {
  unknown: "Da verificare",
  online: "Online",
  offline: "Non connesso",
  preparing: "Confronto in corso",
  preview: "Anteprima pronta",
  queued: "In coda",
  running: "Trasferimento in corso",
  retry_wait: "Attesa nuovo tentativo",
  cancelling: "Annullamento in corso",
  cancelled: "Annullata",
  failed: "Errore",
  completed: "Completata",
  new: "Nuovo",
  present: "Già presente",
  modified: "Differente",
  update: "Aggiornamento",
  updated: "Aggiornato",
  deferred: "Rinviato",
};
const active = ["preparing", "queued", "running", "retry_wait", "cancelling"];

export default function Devices({
  view,
  selected,
  onSelect,
  onCatalog,
}: {
  view: "devices" | "sync";
  selected: number[];
  onSelect: (ids: number[]) => void;
  onCatalog: () => void;
}) {
  const [devices, setDevices] = useState<Device[]>([]);
  const [deviceId, setDeviceId] = useState("");
  const [form, setForm] = useState<Config>(defaults);
  const [editing, setEditing] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [removing, setRemoving] = useState("");
  const [identity, setIdentity] = useState<{
    fingerprint: string;
    previously_trusted: boolean;
  } | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [games, setGames] = useState<Game[]>([]);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [metadata, setMetadata] = useState(true);
  const [covers, setCovers] = useState(false);
  const [rights, setRights] = useState(false);
  const [mediaRights, setMediaRights] = useState(false);
  const [run, setRun] = useState<Run | null>(null);
  const [history, setHistory] = useState<Run[]>([]);
  const loadDevices = useCallback(async () => {
    const values = await api<Device[]>("/devices");
    setDevices(values);
    setDeviceId((current) =>
      values.some((d) => d.id === current)
        ? current
        : values.find((d) => d.is_default)?.id || values[0]?.id || "",
    );
  }, []);
  useEffect(() => {
    loadDevices().catch((e) => setError(String(e)));
  }, [loadDevices]);
  useEffect(() => {
    let live = true;
    const timer = setTimeout(() => {
      api<{ items: Game[]; total: number }>(
        `/games?q=${encodeURIComponent(query)}&page=${page}&page_size=24`,
      )
        .then((data) => {
          if (live) {
            setGames(data.items);
            setTotal(data.total);
          }
        })
        .catch((e) => setError(String(e)));
    }, 180);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [query, page]);
  useEffect(() => {
    api<Run[]>("/sync/runs")
      .then(setHistory)
      .catch((e) => setError(String(e)));
  }, [view]);
  const running = Boolean(run && active.includes(run.status));
  useEffect(() => {
    if (!run || !active.includes(run.status)) return;
    let alive = true;
    const id = run.id;
    const timer = setInterval(() => {
      api<Run>(`/sync/runs/${id}`)
        .then((value) => {
          if (alive) {
            setRun(value);
            if (!active.includes(value.status)) {
              loadDevices().catch((e) => setError(String(e)));
              api<Run[]>("/sync/runs")
                .then(setHistory)
                .catch((e) => setError(String(e)));
            }
          }
        })
        .catch((e) => setError(String(e)));
    }, 800);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [run, loadDevices]);
  const device = devices.find((d) => d.id === deviceId);
  async function action(label: string, task: () => Promise<void>) {
    setBusy(label);
    setError("");
    setNotice("");
    try {
      await task();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy("");
    }
  }
  function field(key: keyof Config, value: string | number | boolean) {
    setForm({ ...form, [key]: value });
  }
  async function preview() {
    const result = await api<{ id: string }>("/sync/plans", "POST", {
      device_id: deviceId,
      game_ids: selected,
      metadata,
      covers,
    });
    setRun(await api<Run>(`/sync/runs/${result.id}`));
    setRights(false);
    setMediaRights(false);
  }
  const diagnostic = device?.diagnostics;
  const status = (value: string) => (
    <span
      className={`status ${value === "online" || value === "completed" ? "completed" : value === "failed" || value === "offline" ? "failed" : ""}`}
    >
      {labels[value] || value}
    </span>
  );
  return (
    <div className="devices-page">
      {error && (
        <div className="message error" role="alert">
          <CircleAlert size={18} />
          {error}
        </div>
      )}
      {notice && (
        <div className="message success" role="status">
          <Check size={18} />
          {notice}
        </div>
      )}
      {busy && (
        <p role="status">
          <LoaderCircle className="spin" size={18} /> {busy}
        </p>
      )}
      {view === "devices" ? (
        <>
          <div className="section-heading">
            <div>
              <h2>I tuoi Raspberry Pi</h2>
              <p className="muted">
                Connessioni, identità SSH e salute del dispositivo.
              </p>
            </div>
            <button
              className="primary"
              onClick={() => {
                setForm({ ...defaults });
                setEditing(null);
                setFormOpen(true);
              }}
            >
              Aggiungi dispositivo
            </button>
          </div>
          <div className="device-grid">
            {devices.map((d) => (
              <button
                key={d.id}
                className={`panel device-card ${d.id === deviceId ? "selected" : ""}`}
                onClick={() => {
                  setDeviceId(d.id);
                  setIdentity(null);
                  setRemoving("");
                }}
              >
                <Server size={24} />
                <strong>{d.config.name}</strong>
                <span>
                  {d.config.host}:{d.config.port}
                </span>
                {status(d.status)}
                {d.is_default && <small>Predefinito</small>}
              </button>
            ))}
          </div>
          {!devices.length && (
            <section className="panel empty">
              <Cable />
              <h3>Nessun dispositivo configurato</h3>
              <p>
                Aggiungi il Raspberry e verifica la sua identità prima di
                connetterti.
              </p>
            </section>
          )}
          {formOpen && (
            <form
              className="panel"
              onSubmit={(e) => {
                e.preventDefault();
                void action("Salvataggio dispositivo", async () => {
                  if (editing) await api(`/devices/${editing}`, "PUT", form);
                  else {
                    const d = await api<{ id: string }>(
                      "/devices",
                      "POST",
                      form,
                    );
                    setDeviceId(d.id);
                  }
                  setFormOpen(false);
                  await loadDevices();
                });
              }}
            >
              <h3>{editing ? "Modifica dispositivo" : "Nuovo dispositivo"}</h3>
              <div className="form-grid">
                <label>
                  Nome descrittivo
                  <input
                    required
                    maxLength={100}
                    value={form.name}
                    onChange={(e) => field("name", e.target.value)}
                  />
                </label>
                <label>
                  Hostname o IP
                  <input
                    required
                    placeholder="retropie"
                    value={form.host}
                    onChange={(e) => field("host", e.target.value)}
                  />
                </label>
                <label>
                  Porta SSH
                  <input
                    type="number"
                    min={1}
                    max={65535}
                    value={form.port}
                    onChange={(e) => field("port", Number(e.target.value))}
                  />
                </label>
                <label>
                  Utente SSH
                  <input
                    required
                    value={form.username}
                    onChange={(e) => field("username", e.target.value)}
                  />
                </label>
                <label>
                  Directory ROM
                  <input
                    required
                    value={form.rom_root}
                    onChange={(e) => field("rom_root", e.target.value)}
                  />
                </label>
                <label>
                  Directory BIOS · sola diagnostica
                  <input
                    required
                    value={form.bios_root}
                    onChange={(e) => field("bios_root", e.target.value)}
                  />
                </label>
                <label>
                  Margine libero minimo · GB
                  <input
                    type="number"
                    min={0.1}
                    step={0.1}
                    value={form.safety_bytes / 1e9}
                    onChange={(e) =>
                      field(
                        "safety_bytes",
                        Math.round(Number(e.target.value) * 1e9),
                      )
                    }
                  />
                </label>
              </div>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={!!form.is_default}
                  onChange={(e) => field("is_default", e.target.checked)}
                />
                Dispositivo predefinito
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={form.chd_confirmed}
                  onChange={(e) => field("chd_confirmed", e.target.checked)}
                />
                Ho verificato il supporto CHD nel core PS1 configurato
              </label>
              <p className="muted">
                Il rilevamento dell’estensione in EmulationStation da solo non
                garantisce la compatibilità del core.
              </p>
              <div className="button-row">
                <button className="primary" disabled={!!busy}>
                  Salva dispositivo
                </button>
                <button type="button" onClick={() => setFormOpen(false)}>
                  Annulla
                </button>
              </div>
            </form>
          )}
          {device && (
            <>
              <section className="panel">
                <div className="section-heading">
                  <h3>
                    <ShieldCheck size={20} /> Configurazione SSH ·{" "}
                    {device.config.name}
                  </h3>
                  <button
                    onClick={() => {
                      setEditing(device.id);
                      setForm({
                        ...device.config,
                        is_default: device.is_default,
                      });
                      setFormOpen(true);
                    }}
                  >
                    Modifica
                  </button>
                </div>
                <ol className="ssh-steps">
                  <li>
                    Verifica l’identità del server confrontando la fingerprint
                    con una fonte affidabile.
                  </li>
                  <li>
                    Apri l’assistente: la password viene inserita soltanto nel
                    terminale SSH di Windows.
                  </li>
                  <li>Verifica l’accesso con chiave, SFTP e diagnostica.</li>
                </ol>
                <p className="mono wrap">
                  {device.fingerprint || "Fingerprint non ancora confermata"}
                </p>
                <div className="button-row">
                  <button
                    disabled={!!busy}
                    onClick={() =>
                      void action("Verifica host SSH", async () =>
                        setIdentity(
                          await api(`/devices/${device.id}/probe`, "POST"),
                        ),
                      )
                    }
                  >
                    1. Verifica fingerprint
                  </button>
                  <button
                    disabled={!!busy || !device.fingerprint}
                    onClick={() =>
                      void action("Apertura assistente SSH", async () => {
                        const value = await api<{ message: string }>(
                          `/devices/${device.id}/key-setup`,
                          "POST",
                        );
                        setNotice(value.message);
                      })
                    }
                  >
                    2. Configura chiave Ed25519
                  </button>
                  <button
                    disabled={!!busy || !device.fingerprint}
                    onClick={() =>
                      void action("Test SSH, SFTP e diagnostica", async () => {
                        const job = await api<Job>(
                          `/devices/${device.id}/diagnostics`,
                          "POST",
                        );
                        try {
                          await waitForJob(job.id, () => {});
                        } finally {
                          await loadDevices();
                        }
                      })
                    }
                  >
                    3. Test SSH e diagnostica
                  </button>
                </div>
                {identity && (
                  <div className="ssh-identity">
                    <strong>
                      {identity.previously_trusted
                        ? "Identità già registrata in known_hosts"
                        : "Nuova identità da verificare"}
                    </strong>
                    <p className="mono wrap">{identity.fingerprint}</p>
                    <button
                      disabled={!!busy}
                      onClick={() =>
                        void action("Conferma identità", async () => {
                          await api(`/devices/${device.id}/trust`, "POST", {
                            fingerprint: identity.fingerprint,
                            confirmed: true,
                          });
                          setIdentity(null);
                          await loadDevices();
                        })
                      }
                    >
                      Ho verificato questa fingerprint
                    </button>
                  </div>
                )}
                {device.error && (
                  <p role="alert" className="error-text">
                    {device.error}
                  </p>
                )}
                <p className="muted">
                  Chiave privata nel profilo Windows con permessi limitati.
                  Nessuna password nel database. L’assistente conserva un backup
                  di authorized_keys.
                </p>
                <button
                  className="danger"
                  onClick={() => setRemoving(device.id)}
                >
                  Rimuovi dispositivo
                </button>
                {removing === device.id && (
                  <div role="alert">
                    <p>
                      Verrà rimossa solo la registrazione locale. I file del
                      Raspberry e le chiavi restano intatti.
                    </p>
                    <button
                      onClick={() =>
                        void action("Rimozione dispositivo", async () => {
                          await api(`/devices/${device.id}`, "DELETE");
                          setRemoving("");
                          await loadDevices();
                        })
                      }
                    >
                      Conferma rimozione
                    </button>
                  </div>
                )}
              </section>
              {diagnostic?.hostname && (
                <section className="panel">
                  <div className="section-heading">
                    <h3>Diagnostica Raspberry</h3>
                    {status(device.status)}
                  </div>
                  <div className="stat-grid">
                    <div className="stat">
                      <span>Temperatura CPU</span>
                      <strong>
                        {diagnostic.temperature_c == null
                          ? "Sconosciuta"
                          : `${diagnostic.temperature_c.toFixed(1)} °C`}
                      </strong>
                    </div>
                    <div className="stat">
                      <span>Spazio libero effettivo</span>
                      <strong>
                        {diagnostic.space
                          ? bytes(diagnostic.space.free)
                          : "Non rilevato"}
                      </strong>
                      <small>
                        su{" "}
                        {diagnostic.space
                          ? bytes(diagnostic.space.total)
                          : "Non rilevato"}
                      </small>
                    </div>
                    <div className="stat">
                      <span>RAM disponibile</span>
                      <strong>
                        {diagnostic.ram_available == null
                          ? "Sconosciuta"
                          : bytes(diagnostic.ram_available)}
                      </strong>
                    </div>
                    <div className="stat">
                      <span>Uptime</span>
                      <strong>
                        {diagnostic.uptime_seconds == null
                          ? "Sconosciuto"
                          : `${Math.floor(diagnostic.uptime_seconds / 3600)} h`}
                      </strong>
                    </div>
                  </div>
                  <dl className="diagnostic-list">
                    {Object.entries({
                      Modello: diagnostic.model,
                      Hostname: diagnostic.hostname,
                      "Indirizzi IP": diagnostic.ip,
                      "Sistema operativo": diagnostic.os,
                      RetroPie: diagnostic.retropie_version,
                      EmulationStation: diagnostic.emulationstation_version,
                      "Servizio SSH": diagnostic.ssh_service,
                      "Directory EmulationStation": diagnostic.es_root,
                      "Configurazione sistemi": diagnostic.systems_config,
                      "EmulationStation attiva": diagnostic.es_running
                        ? "Sì · scrittura gamelist rinviata"
                        : "No",
                    }).map(([key, value]) => (
                      <div key={key}>
                        <dt>{key}</dt>
                        <dd>{value || "Non rilevato"}</dd>
                      </div>
                    ))}
                  </dl>
                  {Object.entries(diagnostic.directories || {}).map(
                    ([key, d]) => (
                      <p
                        key={key}
                        className={
                          d.exists && d.readable && d.writable
                            ? "success-text"
                            : "error-text"
                        }
                      >
                        {d.path} · {d.exists ? "presente" : "assente"} · lettura{" "}
                        {d.readable ? "sì" : "no"} · scrittura{" "}
                        {d.writable ? "sì" : "no"}
                      </p>
                    ),
                  )}
                  <details>
                    <summary>Core PlayStation configurato</summary>
                    <pre>
                      {diagnostic.psx_emulator_config || "Non rilevato"}
                    </pre>
                  </details>
                </section>
              )}
            </>
          )}
        </>
      ) : (
        <>
          <section className="panel">
            <h2>Prepara la sincronizzazione</h2>
            <p className="muted">
              Confronto SHA-256, spazio reale e trasferimento dei soli gruppi
              mancanti.
            </p>
            <label>
              Raspberry di destinazione
              <select
                value={deviceId}
                onChange={(e) => {
                  setDeviceId(e.target.value);
                  setRun(null);
                }}
              >
                <option value="">Scegli un dispositivo</option>
                {devices.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.config.name} · {d.config.host}
                    {d.is_default ? " · predefinito" : ""}
                  </option>
                ))}
              </select>
            </label>
            <div className="button-row">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={metadata}
                  onChange={(e) => setMetadata(e.target.checked)}
                />
                Includi metadati EmulationStation
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={covers}
                  onChange={(e) => setCovers(e.target.checked)}
                />
                Includi copertine locali
              </label>
            </div>
            <div className="section-heading">
              <strong>{selected.length} giochi selezionati</strong>
              <button onClick={onCatalog}>Apri Catalogo</button>
            </div>
            <label>
              Cerca nella libreria
              <input
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setPage(1);
                }}
              />
            </label>
            <div className="sync-picker">
              {games.map((g) => (
                <label key={g.id} className="sync-game">
                  <input
                    type="checkbox"
                    checked={selected.includes(g.id)}
                    onChange={(e) =>
                      onSelect(
                        e.target.checked
                          ? [...selected, g.id]
                          : selected.filter((id) => id !== g.id),
                      )
                    }
                  />
                  <span>
                    <strong>{g.title}</strong>
                    <small>
                      {g.platform} · {bytes(g.size)} · {g.license}
                    </small>
                  </span>
                </label>
              ))}
            </div>
            {!games.length && (
              <p className="muted">
                Nessun gioco nella selezione corrente. Importa i giochi nel
                Catalogo.
              </p>
            )}
            <div className="pagination">
              <button disabled={page === 1} onClick={() => setPage(page - 1)}>
                Precedente
              </button>
              <span>
                Pagina {page} · {total} giochi
              </span>
              <button
                disabled={page * 24 >= total}
                onClick={() => setPage(page + 1)}
              >
                Successiva
              </button>
            </div>
            <button
              className="primary"
              disabled={!!busy || running || !deviceId || !selected.length}
              onClick={() => void action("Preparazione dry-run", preview)}
            >
              <RefreshCw size={16} /> Analizza e prepara dry-run
            </button>
          </section>
          {run && (
            <section className="panel" aria-live="polite">
              <div className="section-heading">
                <h3>Sincronizzazione</h3>
                {status(run.status)}
              </div>
              {run.error && (
                <p className="error-text" role="alert">
                  {run.error}
                </p>
              )}
              {run.plan?.groups && (
                <>
                  <div className="stat-grid">
                    <div className="stat">
                      <span>Spazio richiesto</span>
                      <strong>{bytes(run.plan.required_bytes)}</strong>
                    </div>
                    <div className="stat">
                      <span>Libero sul Raspberry</span>
                      <strong>{bytes(run.plan.free_bytes)}</strong>
                    </div>
                    <div className="stat">
                      <span>Margine da conservare</span>
                      <strong>{bytes(run.plan.safety_bytes)}</strong>
                    </div>
                  </div>
                  {run.plan.warnings.map((w) => (
                    <p key={w} className="sync-warning">
                      {w}
                    </p>
                  ))}
                  {run.plan.blocked.map((w) => (
                    <p key={w} className="error-text">
                      {w}
                    </p>
                  ))}
                  <div className="sync-files">
                    {run.plan.groups.map((group) => (
                      <details key={group.id}>
                        <summary>
                          {group.title} · {group.files.length} file
                        </summary>
                        {group.files.map((f) => (
                          <div key={f.path} className="sync-file">
                            <span className="wrap">{f.path}</span>
                            <span>{bytes(f.size)}</span>
                            {status(f.state)}
                          </div>
                        ))}
                      </details>
                    ))}
                  </div>
                  {!!run.plan.media.length && (
                    <details>
                      <summary>Copertine · {run.plan.media.length}</summary>
                      <div className="media-preview">
                        {run.plan.media.map((m) => (
                          <figure key={m.path}>
                            <img
                              src={`/api/games/${m.game_id}/cover`}
                              alt="Copertina da sincronizzare"
                            />
                            <figcaption>
                              {bytes(m.size)} · {labels[m.state]}
                            </figcaption>
                          </figure>
                        ))}
                      </div>
                    </details>
                  )}
                  {!!run.plan.gamelists.length && (
                    <details>
                      <summary>File gamelist.xml individuati</summary>
                      {run.plan.gamelists.map((f) => (
                        <p key={f.path} className="wrap">
                          {f.path} · {labels[f.state]}
                        </p>
                      ))}
                    </details>
                  )}
                  {run.status === "preview" && (
                    <div className="sync-confirm">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={rights}
                          onChange={(e) => setRights(e.target.checked)}
                        />
                        Confermo di essere autorizzato a trasferire questi
                        giochi sul mio Raspberry.
                      </label>
                      {!!run.plan.media.length && (
                        <label className="checkbox-label">
                          <input
                            type="checkbox"
                            checked={mediaRights}
                            onChange={(e) => setMediaRights(e.target.checked)}
                          />
                          Confermo l’autorizzazione a utilizzare le copertine
                          selezionate.
                        </label>
                      )}
                      <button
                        className="primary"
                        disabled={
                          !!busy ||
                          !rights ||
                          (!mediaRights && !!run.plan.media.length) ||
                          !run.plan.can_sync
                        }
                        onClick={() =>
                          void action("Avvio sincronizzazione", async () => {
                            await api(`/sync/runs/${run.id}/confirm`, "POST", {
                              confirmed: true,
                              rights_confirmed: true,
                              media_rights_confirmed: mediaRights,
                            });
                            setRun(await api(`/sync/runs/${run.id}`));
                          })
                        }
                      >
                        Conferma e sincronizza
                      </button>
                    </div>
                  )}
                </>
              )}
              {running && (
                <>
                  <p className="wrap">
                    {run.progress.file ||
                      "Lettura dell’inventario e verifica degli hash…"}
                  </p>
                  <progress
                    aria-label="Avanzamento complessivo"
                    max={Math.max(1, run.progress.total || 1)}
                    value={Math.min(
                      run.progress.bytes || 0,
                      run.progress.total || 1,
                    )}
                  />
                  <p>
                    {bytes(run.progress.bytes || 0)} /{" "}
                    {bytes(run.progress.total || 0)} · tentativo{" "}
                    {run.progress.attempt || 1}
                  </p>
                  {!!run.progress.file_total && (
                    <>
                      <progress
                        aria-label="Avanzamento file"
                        max={run.progress.file_total}
                        value={run.progress.file_bytes || 0}
                      />
                      <small>
                        {bytes(run.progress.file_bytes || 0)} /{" "}
                        {bytes(run.progress.file_total)}
                      </small>
                    </>
                  )}
                  <p>
                    <button
                      disabled={run.status === "cancelling" || !!busy}
                      onClick={() =>
                        void action("Annullamento", async () => {
                          await api(`/sync/runs/${run.id}/control`, "POST", {
                            action: "cancel",
                          });
                          setRun(await api(`/sync/runs/${run.id}`));
                        })
                      }
                    >
                      Annulla trasferimento
                    </button>
                  </p>
                </>
              )}
              {["failed", "cancelled"].includes(run.status) && (
                <button
                  disabled={!!busy}
                  onClick={() =>
                    void action("Ripresa sincronizzazione", async () => {
                      await api(`/sync/runs/${run.id}/control`, "POST", {
                        action: "retry",
                      });
                      setRun(await api(`/sync/runs/${run.id}`));
                    })
                  }
                >
                  Riprova trasferimento
                </button>
              )}
              {run.status === "completed" && (
                <div className="sync-report">
                  <h3>Report finale</h3>
                  <p>
                    {bytes(run.report.transferred_bytes || 0)} trasferiti ·{" "}
                    {run.report.skipped_files || 0} file già presenti.
                  </p>
                  {run.report.space_after && (
                    <p>
                      Spazio libero aggiornato:{" "}
                      {bytes(run.report.space_after.free)}
                    </p>
                  )}
                  {run.report.metadata_deferred && (
                    <p className="sync-warning">
                      I gamelist sono rinviati perché EmulationStation è attiva.
                      Dopo averla chiusa, prepara un nuovo dry-run per
                      completare i metadati.
                    </p>
                  )}
                  {run.report.gamelists?.map((m) => (
                    <p className="wrap" key={m.path}>
                      {m.path} · {labels[m.status]}
                    </p>
                  ))}
                  {run.report.backups?.map((p) => (
                    <p className="wrap" key={p}>
                      Backup conservato: {p}
                    </p>
                  ))}
                  <p className="muted">
                    La presenza dei file non certifica il lancio del gioco
                    nell’emulatore.
                  </p>
                </div>
              )}
            </section>
          )}
          {!!history.length && (
            <section className="panel">
              <h3>Operazioni recenti</h3>
              {history.map((h) => (
                <button
                  className="sync-history"
                  key={h.id}
                  onClick={() =>
                    void action("Caricamento report", async () =>
                      setRun(await api(`/sync/runs/${h.id}`)),
                    )
                  }
                >
                  <span>{new Date(h.created_at).toLocaleString("it-IT")}</span>
                  {status(h.status)}
                </button>
              ))}
            </section>
          )}
        </>
      )}
    </div>
  );
}
