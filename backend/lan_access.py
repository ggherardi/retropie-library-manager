"""Local administrator authentication and explicit private-LAN access.

Password hashes, session digests and network preferences live only in ignored data.
No forwarded header grants trust. HTTP LAN traffic is explicitly not confidential.
"""

import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import sqlite3
import subprocess
import threading
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import SecretStr

from backend.schemas import Input

COOKIE = "rlm_session"
IDLE_SECONDS = 1800
ABSOLUTE_SECONDS = 8 * 3600


def local_client(host):
    if host == "testclient":  # Starlette's in-process test transport, never a TCP peer.
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def password_hash(password, salt):
    return hashlib.scrypt(
        password.encode("utf8"), salt=bytes.fromhex(salt), n=2**17, r=8, p=1, maxmem=256 * 1024**2, dklen=32
    ).hex()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".new")
    with temporary.open("w", encoding="utf8") as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def discover_interfaces():
    """Only actual IPv4 interfaces with a gateway; virtual host-only NICs excluded."""
    if os.name == "nt":
        script = r"""$ErrorActionPreference='Stop'; @(
Get-NetIPConfiguration | Where-Object {$_.IPv4DefaultGateway} | ForEach-Object {
 $nic=$_; $profile=Get-NetConnectionProfile -InterfaceIndex $nic.InterfaceIndex -ErrorAction SilentlyContinue
 foreach($ip in $nic.IPv4Address) { [pscustomobject]@{address=$ip.IPAddress;prefix=$ip.PrefixLength;name=$nic.InterfaceAlias;private=([int]$profile.NetworkCategory -eq 1)} }
}) | ConvertTo-Json -Compress"""
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            return []
        rows = json.loads(result.stdout.decode("utf-8-sig", "replace") or "[]")
        rows = rows if isinstance(rows, list) else [rows]
    else:
        # Conservative: no inferred subnet/profile on an unconfigured non-Windows host.
        rows = []
    valid = []
    for row in rows:
        address = ipaddress.ip_address(row["address"])
        if address.is_private and not address.is_loopback and not address.is_link_local:
            row["subnet"] = str(ipaddress.ip_network(f"{address}/{int(row['prefix'])}", strict=False))
            valid.append(row)
    return valid


class PasswordInput(Input):
    password: SecretStr
    setup_token: str = ""


class NetworkInput(Input):
    lan_enabled: bool = False
    port: int = 8000


class Access:
    def __init__(self, data):
        self.data = data
        self.admin_file = data / "access-admin.json"
        self.network_file = data / "network.json"
        self.db_file = data / "access.sqlite3"
        self.setup_token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.password_slots = threading.BoundedSemaphore(2)
        self.interfaces_cache: tuple[float, list[dict]] = (0.0, [])
        self.lan_active = os.environ.get("RLM_LAN_ACTIVE") == "1"
        self.data.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS sessions
                (token TEXT PRIMARY KEY, csrf TEXT, created REAL, seen REAL);
                CREATE TABLE IF NOT EXISTS attempts (peer TEXT, stamp REAL);""")

    def connection(self):
        return sqlite3.connect(self.db_file, timeout=10)

    def configured(self):
        return self.admin_file.is_file()

    def config(self):
        return (
            json.loads(self.network_file.read_text(encoding="utf8"))
            if self.network_file.exists()
            else {"lan_enabled": False, "port": 8000}
        )

    def interfaces(self):
        with self.lock:
            stamp, rows = self.interfaces_cache
            if time.monotonic() - stamp > 30:
                try:
                    rows = discover_interfaces()
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    rows = []
                self.interfaces_cache = (time.monotonic(), rows)
            return rows

    def session(self, request):
        token = request.cookies.get(COOKIE, "")
        if not token or len(token) > 128:
            return None
        hashed = hashlib.sha256(token.encode()).hexdigest()
        stamp = time.time()
        with self.connection() as db:
            row = db.execute("SELECT csrf,created,seen FROM sessions WHERE token=?", (hashed,)).fetchone()
            if not row or row[1] + ABSOLUTE_SECONDS < stamp or row[2] + IDLE_SECONDS < stamp:
                db.execute("DELETE FROM sessions WHERE token=?", (hashed,))
                return None
            if stamp - row[2] > 30:
                db.execute("UPDATE sessions SET seen=? WHERE token=?", (stamp, hashed))
        return {"csrf": row[0], "digest": hashed}

    def issue(self, request):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        stamp = time.time()
        with self.connection() as db:
            db.execute(
                "DELETE FROM sessions WHERE created<? OR seen<?",
                (stamp - ABSOLUTE_SECONDS, stamp - IDLE_SECONDS),
            )
            # Bound persistent sessions; login always rotates the current browser's token.
            old = request.cookies.get(COOKIE, "")
            db.execute("DELETE FROM sessions WHERE token=?", (hashlib.sha256(old.encode()).hexdigest(),))
            if db.execute("SELECT count(*) FROM sessions").fetchone()[0] >= 100:
                db.execute(
                    "DELETE FROM sessions WHERE token=(SELECT token FROM sessions ORDER BY seen LIMIT 1)"
                )
            db.execute(
                "INSERT INTO sessions VALUES (?,?,?,?)",
                (hashlib.sha256(token.encode()).hexdigest(), csrf, stamp, stamp),
            )
        response = JSONResponse({"authenticated": True, "csrf": csrf})
        response.set_cookie(
            COOKIE,
            token,
            max_age=ABSOLUTE_SECONDS,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="strict",
            path="/",
        )
        return response

    def derive_password(self, password, salt):
        # Each scrypt calculation needs 128 MiB: bound unauthenticated memory use.
        if not self.password_slots.acquire(blocking=False):
            raise HTTPException(
                429, "Accessi simultanei: riprova tra pochi secondi", headers={"Retry-After": "5"}
            )
        try:
            return password_hash(password, salt)
        finally:
            self.password_slots.release()

    def throttle(self, peer):
        stamp = time.time()
        with self.lock, self.connection() as db:
            db.execute("DELETE FROM attempts WHERE stamp<?", (stamp - 300,))
            recent = db.execute("SELECT count(*) FROM attempts WHERE peer=?", (peer,)).fetchone()[0]
            total = db.execute("SELECT count(*) FROM attempts WHERE stamp>?", (stamp - 60,)).fetchone()[0]
            if recent >= 5 or total >= 30:
                raise HTTPException(
                    429, "Troppi tentativi. Attendi cinque minuti.", headers={"Retry-After": "300"}
                )
            db.execute("INSERT INTO attempts VALUES (?,?)", (peer, stamp))

    async def guard(self, request, call_next):
        peer = request.client.host if request.client else ""
        local = local_client(peer)
        interfaces = self.interfaces() if self.lan_active or not local else []
        allowed_hosts = {"127.0.0.1", "localhost", "::1", "testserver", *[r["address"] for r in interfaces]}
        if request.url.hostname not in allowed_hosts:
            return JSONResponse({"detail": "Host non autorizzato"}, status_code=400)
        if not local:
            try:
                permitted = (
                    self.lan_active
                    and self.config()["lan_enabled"]
                    and self.configured()
                    and any(
                        r["private"] and ipaddress.ip_address(peer) in ipaddress.ip_network(r["subnet"])
                        for r in interfaces
                    )
                )
            except ValueError:
                permitted = False
            if not permitted:
                return JSONResponse(
                    {"detail": "Accesso consentito solo dalla LAN privata configurata"}, status_code=403
                )
        path = request.url.path
        public = path in {"/api/access/status", "/api/access/login", "/api/access/setup", "/api/health"}
        static = path == "/" or path.startswith("/assets/") or path == "/favicon.ico"
        session = self.session(request) if self.configured() else None
        request.state.access_session = session
        if self.configured() and not session and not public and not static:
            return JSONResponse({"detail": "Accedi con la password amministratore"}, status_code=401)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get("X-RLM-Request") != "1":
                return JSONResponse({"detail": "Header applicazione richiesto"}, status_code=403)
            origin = request.headers.get("Origin")
            origins = {str(request.base_url).rstrip("/")}
            if local and not self.configured():
                origins.update(
                    {
                        "http://127.0.0.1:5173",
                        "http://localhost:5173",
                        "http://127.0.0.1:8000",
                        "http://localhost:8000",
                    }
                )
            if origin and origin not in origins:
                return JSONResponse({"detail": "Origine non autorizzata"}, status_code=403)
            if (
                self.configured()
                and not public
                and (
                    not session
                    or not hmac.compare_digest(request.headers.get("X-RLM-CSRF", ""), session["csrf"])
                )
            ):
                return JSONResponse(
                    {"detail": "Sessione scaduta o controllo CSRF non valido"}, status_code=403
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = (
            "no-store" if not path.startswith("/assets/") else "private, max-age=3600"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
        )
        return response

    def network_info(self, port, scheme="http"):
        config = self.config()
        rows = self.interfaces()
        active = (
            self.lan_active
            and config["lan_enabled"]
            and self.configured()
            and any(row["private"] for row in rows)
        )
        return {
            "lan_enabled": config["lan_enabled"],
            "active": active,
            "admin_configured": self.configured(),
            "port": port,
            "configured_port": config["port"],
            "local_url": f"{scheme}://127.0.0.1:{port}",
            "interfaces": rows,
            "lan_urls": [f"{scheme}://{r['address']}:{port}" for r in rows if active and r["private"]],
            "restart_needed": config["lan_enabled"] != self.lan_active or config["port"] != port,
            "transport_warning": "HTTP non cifra password, sessioni o file. Usa solo una rete fidata; per riservatezza usa HTTPS locale o un tunnel privato.",
            "firewall_note": "Serve una regola TCP limitata alla rete Privata e alla subnet locale. L’app non modifica il firewall.",
        }

    def routes(self):
        router = APIRouter(prefix="/api/access")

        @router.get("/status")
        def status(request: Request):
            configured = self.configured()
            local = local_client(request.client.host if request.client else "")
            session = request.state.access_session
            return {
                "configured": configured,
                "authenticated": bool(session),
                "local": local,
                "csrf": session["csrf"] if session else "",
                "setup_token": self.setup_token if local and not configured else "",
            }

        @router.post("/setup")
        def setup(request: Request, body: PasswordInput):
            if not local_client(request.client.host if request.client else ""):
                raise HTTPException(403, "Configura la password dal PC che ospita l’app")
            with self.lock:
                if self.configured() or not hmac.compare_digest(body.setup_token, self.setup_token):
                    raise HTTPException(403, "Configurazione iniziale non disponibile")
                password = body.password.get_secret_value()
                if not 12 <= len(password) <= 128:
                    raise HTTPException(400, "Usa una password da 12 a 128 caratteri")
                salt = secrets.token_hex(16)
                atomic_json(
                    self.admin_file,
                    {
                        "algorithm": "scrypt",
                        "n": 2**17,
                        "r": 8,
                        "p": 1,
                        "salt": salt,
                        "hash": self.derive_password(password, salt),
                    },
                )
            return self.issue(request)

        @router.post("/login")
        def login(request: Request, body: PasswordInput):
            self.throttle(request.client.host if request.client else "")
            password = body.password.get_secret_value()
            if not self.configured() or not 1 <= len(password) <= 128:
                raise HTTPException(401, "Accesso non riuscito")
            admin = json.loads(self.admin_file.read_text(encoding="utf8"))
            if not hmac.compare_digest(self.derive_password(password, admin["salt"]), admin["hash"]):
                raise HTTPException(401, "Accesso non riuscito")
            return self.issue(request)

        @router.post("/logout")
        def logout(request: Request):
            session = request.state.access_session
            if session:
                with self.connection() as db:
                    db.execute("DELETE FROM sessions WHERE token=?", (session["digest"],))
            response = JSONResponse({"authenticated": False})
            response.delete_cookie(COOKIE, path="/")
            return response

        @router.get("/network")
        def network(request: Request):
            return self.network_info(request.url.port or 8000, request.url.scheme)

        @router.put("/network")
        def configure_network(request: Request, body: NetworkInput):
            if (
                not local_client(request.client.host if request.client else "")
                or not request.state.access_session
            ):
                raise HTTPException(403, "Configura la rete dal PC ospite dopo l’accesso amministratore")
            if not 1024 <= body.port <= 65535:
                raise HTTPException(400, "Porta consentita: 1024–65535")
            if body.lan_enabled and not any(r["private"] for r in self.interfaces()):
                raise HTTPException(
                    400, "La connessione Windows deve essere Privata. L’app non cambia il profilo di rete."
                )
            atomic_json(self.network_file, body.model_dump())
            return self.network_info(request.url.port or 8000, request.url.scheme)

        @router.get("/qr")
        def qr(request: Request):
            import io

            import qrcode

            urls = self.network_info(request.url.port or 8000, request.url.scheme)["lan_urls"]
            if not urls:
                raise HTTPException(400, "Nessun indirizzo LAN attivo verificato")
            image = qrcode.make(urls[0])
            output = io.BytesIO()
            image.save(output, format="PNG")
            return Response(output.getvalue(), media_type="image/png")

        return router
