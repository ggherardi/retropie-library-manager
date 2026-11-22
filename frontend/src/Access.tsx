import { useCallback, useEffect, useState, type ReactNode } from "react";
import { api, setCSRF } from "./api";
import "./access.css";

type Status = {
  configured: boolean;
  authenticated: boolean;
  local: boolean;
  csrf: string;
  setup_token: string;
};
type Network = {
  lan_enabled: boolean;
  active: boolean;
  admin_configured: boolean;
  port: number;
  configured_port: number;
  local_url: string;
  lan_urls: string[];
  restart_needed: boolean;
  transport_warning: string;
  firewall_note: string;
  interfaces: {
    address: string;
    subnet: string;
    name: string;
    private: boolean;
  }[];
};

async function authenticate(path: string, password: string, setup_token = "") {
  const response = await fetch(`/api/access/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-RLM-Request": "1" },
    body: JSON.stringify({ password, setup_token }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || "Accesso non riuscito");
  setCSRF(result.csrf);
  window.dispatchEvent(new Event("rlm-auth-change"));
}

export function AuthGate({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/access/status", { cache: "no-store" });
      if (!response.ok)
        throw new Error("Accesso non disponibile da questa rete");
      const result = await response.json();
      setCSRF(result.csrf || "");
      setStatus(result);
      setError("");
    } catch {
      setError(
        "Il PC ospite non risponde. Controlla che Start.cmd sia in esecuzione.",
      );
    }
  }, []);
  useEffect(() => {
    void refresh();
    const update = () => void refresh();
    window.addEventListener("rlm-auth-change", update);
    window.addEventListener("rlm-auth-required", update);
    return () => {
      window.removeEventListener("rlm-auth-change", update);
      window.removeEventListener("rlm-auth-required", update);
    };
  }, [refresh]);
  if (!status)
    return (
      <main className="auth-page">
        <h1>RetroPie Library Manager</h1>
        <p>{error || "Connessione al PC ospite…"}</p>
        <button onClick={() => void refresh()}>Riprova connessione</button>
      </main>
    );
  if (!status.configured || status.authenticated) return <>{children}</>;
  return (
    <main className="auth-page">
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            await authenticate("login", password);
            setPassword("");
          } catch (e) {
            setError(String(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        <span className="eyebrow">ACCESSO LOCALE PROTETTO</span>
        <h1>RetroPie Library Manager</h1>
        <p>Accedi con la password amministratore configurata sul PC ospite.</p>
        {location.protocol === "http:" && (
          <p className="auth-warning">
            HTTP non cifra password e sessioni. Collegati solo da una rete
            fidata; per riservatezza usa HTTPS locale o un tunnel privato.
          </p>
        )}
        <label>
          Password amministratore
          <input
            aria-label="Password amministratore"
            type="password"
            autoComplete="current-password"
            value={password}
            maxLength={128}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && <p role="alert">{error}</p>}
        <button className="primary" disabled={busy}>
          {busy ? "Accesso…" : "Accedi"}
        </button>
      </form>
    </main>
  );
}

export default function AccessSettings() {
  const [status, setStatus] = useState<Status | null>(null);
  const [network, setNetwork] = useState<Network | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [enabled, setEnabled] = useState(false);
  const [port, setPort] = useState(8000);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    const [s, n] = await Promise.all([
      api<Status>("/access/status"),
      api<Network>("/access/network"),
    ]);
    setStatus(s);
    setNetwork(n);
    setEnabled(n.lan_enabled);
    setPort(n.configured_port);
  }, []);
  useEffect(() => {
    void load().catch((e) => setNotice(String(e)));
  }, [load]);
  const perform = async (operation: () => Promise<unknown>) => {
    setBusy(true);
    setNotice("");
    try {
      await operation();
      await load();
    } catch (e) {
      setNotice(String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="panel access-settings">
      <h2>Accesso da smartphone e altri PC</h2>
      <p>
        Il PC ospite deve essere acceso e Start.cmd in esecuzione. Tutti i
        dispositivi devono essere nella stessa rete domestica.
      </p>
      {network && (
        <>
          <p>
            Su questo PC: <a href={network.local_url}>{network.local_url}</a>
          </p>
          <p>
            Accesso LAN:{" "}
            <strong>
              {network.active
                ? "Attivo e protetto"
                : network.lan_enabled
                  ? "Configurato, da avviare"
                  : "Disattivato"}
            </strong>{" "}
            · Porta attuale {network.port}
          </p>
          <p className="auth-warning">{network.transport_warning}</p>
          {network.interfaces.map((n) => (
            <p key={n.address}>
              {n.name}: {n.address} · {n.subnet} ·{" "}
              {n.private
                ? "Rete privata"
                : "Profilo pubblico: accesso LAN bloccato"}
            </p>
          ))}
          {network.lan_urls.map((url) => (
            <p key={url}>
              Da telefono o altro computer: <a href={url}>{url}</a>
            </p>
          ))}
          {network.active && network.lan_urls.length > 0 && (
            <img
              className="access-qr"
              src="/api/access/qr"
              alt="Codice QR dell’indirizzo LAN, senza password o token"
              width={200}
              height={200}
            />
          )}
          <p>{network.firewall_note}</p>
        </>
      )}
      {status && !status.configured && status.local && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void perform(async () => {
              if (password !== confirm)
                throw new Error("Le password non coincidono");
              await authenticate("setup", password, status.setup_token);
              setPassword("");
              setConfirm("");
              setNotice(
                "Password configurata. Ora puoi abilitare l’accesso LAN su una rete Privata.",
              );
            });
          }}
        >
          <h3>Configura la password iniziale</h3>
          <p>
            Non esiste una password predefinita. Dopo la configurazione anche le
            API locali richiedono l’accesso. La password è salvata come hash
            scrypt.
          </p>
          <label>
            Nuova password amministratore
            <input
              type="password"
              autoComplete="new-password"
              minLength={12}
              maxLength={128}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <label>
            Ripeti password
            <input
              type="password"
              autoComplete="new-password"
              minLength={12}
              maxLength={128}
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </label>
          <button className="primary" disabled={busy}>
            Configura password
          </button>
        </form>
      )}
      {status?.configured && (
        <>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void perform(async () => {
                await api("/access/network", "PUT", {
                  lan_enabled: enabled,
                  port,
                });
                setNotice(
                  "Preferenze salvate. Riavvia solo il server locale con Start.cmd quando non ci sono operazioni in corso.",
                );
              });
            }}
          >
            <label className="checkline">
              <input
                type="checkbox"
                checked={enabled}
                disabled={!status.local}
                onChange={(e) => setEnabled(e.target.checked)}
              />{" "}
              Abilita accesso dalla LAN privata
            </label>
            <label>
              Porta all’avvio
              <input
                type="number"
                min={1024}
                max={65535}
                value={port}
                disabled={!status.local}
                onChange={(e) => setPort(Number(e.target.value))}
              />
            </label>
            <button disabled={busy || !status.local}>Salva accesso LAN</button>
            {!status.local && (
              <p>Le preferenze di rete si modificano soltanto dal PC ospite.</p>
            )}
            {network?.restart_needed && (
              <p>
                Le preferenze saranno applicate al prossimo avvio con Start.cmd.
              </p>
            )}
          </form>
          <button
            onClick={() =>
              void perform(async () => {
                await api("/access/logout", "POST");
                setCSRF("");
                window.dispatchEvent(new Event("rlm-auth-change"));
              })
            }
          >
            Esci dalla sessione
          </button>
        </>
      )}
      {notice && <p role="status">{notice}</p>}
      <p>
        Su smartphone seleziona i file nell’app File/Download: la selezione di
        cartelle intere può non essere disponibile. Gli archivi vengono caricati
        sul PC, controllati e preparati dalla pipeline esistente.
      </p>
    </section>
  );
}
