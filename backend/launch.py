"""Start the single application worker using persistent local network preferences."""

import argparse
import getpass
import os
import secrets

from backend.config import DATA
from backend.lan_access import Access, atomic_json, password_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int)
    parser.add_argument("--reset-password", action="store_true")
    parser.add_argument("--certfile")
    parser.add_argument("--keyfile")
    args = parser.parse_args()
    access = Access(DATA)
    if args.reset_password:
        password = getpass.getpass("Nuova password amministratore (12–128 caratteri): ")
        confirm = getpass.getpass("Ripeti password: ")
        if password != confirm or not 12 <= len(password) <= 128:
            raise SystemExit("Password non corrispondenti o lunghezza non valida")
        salt = secrets.token_hex(16)
        atomic_json(
            access.admin_file,
            {
                "algorithm": "scrypt",
                "n": 2**17,
                "r": 8,
                "p": 1,
                "salt": salt,
                "hash": password_hash(password, salt),
            },
        )
        with access.connection() as db:
            db.execute("DELETE FROM sessions")
        print("Password aggiornata; sessioni revocate. Riavvia l’app se era attiva.")
        return
    config = access.config()
    port = args.port if args.port is not None else config["port"]
    if not 1024 <= port <= 65535:
        raise SystemExit("Porta consentita: 1024–65535")
    private = [row for row in access.interfaces() if row["private"]]
    lan = config["lan_enabled"] and access.configured() and bool(private)
    os.environ["RLM_LAN_ACTIVE"] = "1" if lan else "0"
    scheme = "https" if args.certfile and args.keyfile else "http"
    if bool(args.certfile) != bool(args.keyfile):
        raise SystemExit("Fornire sia certificato sia chiave TLS")
    print(f"Locale: {scheme}://127.0.0.1:{port}")
    if lan:
        for row in private:
            print(f"LAN: {scheme}://{row['address']}:{port} (subnet {row['subnet']})")
        if scheme == "http":
            print(
                "HTTP non cifra password, sessioni o upload: usare solo una LAN fidata. HTTPS/tunnel privato consigliato."
            )
        print("Il firewall non viene modificato automaticamente.")
    elif config["lan_enabled"]:
        print("LAN non attivata: serve una password amministratore e una connessione Windows Privata.")
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0" if lan else "127.0.0.1",
        port=port,
        proxy_headers=False,
        ssl_certfile=args.certfile,
        ssl_keyfile=args.keyfile,
        access_log=True,
    )


if __name__ == "__main__":
    main()
