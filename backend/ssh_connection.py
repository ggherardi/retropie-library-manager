"""Pinned SSH identities and local-only Ed25519 credentials."""

import base64
import hashlib
import os
import re
import socket
import subprocess
from pathlib import Path

import paramiko
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def ssh_directory() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share")))
    return Path(os.environ.get("RLM_SSH_DIR", str(base / "RetroPieLibraryManager/ssh")))


def protect(path: Path):
    if os.name == "nt":
        identity = subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"], text=True)
        match = re.search(r"S-1-\d+(?:-\d+)+", identity)
        if not match:
            raise ValueError("Identità Windows non determinabile")
        sid = match.group(0)
        grant = f"*{sid}:" + ("(OI)(CI)F" if path.is_dir() else "F")
        subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", grant], check=True, capture_output=True
        )
    else:
        path.chmod(0o700 if path.is_dir() else 0o600)


def ensure_key() -> dict:
    folder = ssh_directory()
    folder.mkdir(parents=True, exist_ok=True)
    protect(folder)
    private = folder / "id_ed25519"
    if not private.exists():
        key = Ed25519PrivateKey.generate()
        with private.open("xb") as output:
            output.write(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.OpenSSH,
                    serialization.NoEncryption(),
                )
            )
        protect(private)
        public = key.public_key().public_bytes(
            serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
        )
        private.with_suffix(".pub").write_bytes(public + b" rlm-local\n")
    protect(private)
    loaded = paramiko.Ed25519Key.from_private_key_file(str(private))
    return {
        "fingerprint": fingerprint(loaded),
        "public_key": f"{loaded.get_name()} {loaded.get_base64()} rlm-local",
        "path": str(private),
    }


def fingerprint(key) -> str:
    return "SHA256:" + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")


def host_label(host, port):
    return host if port == 22 else f"[{host}]:{port}"


def known_keys():
    keys = paramiko.HostKeys()
    for path in [Path.home() / ".ssh/known_hosts", ssh_directory() / "known_hosts"]:
        if path.exists():
            keys.load(str(path))
    return keys


def probe(host, port):
    with socket.create_connection((host, port), timeout=8) as sock:
        with paramiko.Transport(sock) as transport:
            options = transport.get_security_options()
            options.key_types = ("ssh-ed25519",)
            transport.start_client(timeout=8)
            key = transport.get_remote_server_key()
            label = host_label(host, port)
            known = known_keys()
            saved = known.lookup(label)
            if saved and not known.check(label, key):
                raise ValueError(
                    "Host key cambiata: verificare il Raspberry e aggiornare known_hosts manualmente"
                )
            return {
                "fingerprint": fingerprint(key),
                "key": key.get_base64(),
                "algorithm": key.get_name(),
                "previously_trusted": bool(saved),
                "host": host,
                "port": port,
            }


def trust(host, port, expected):
    observed = probe(host, port)
    if observed["fingerprint"] != expected:
        raise ValueError("Fingerprint diversa da quella confermata")
    folder = ssh_directory()
    folder.mkdir(parents=True, exist_ok=True)
    protect(folder)
    path = folder / "known_hosts"
    keys = paramiko.HostKeys()
    if path.exists():
        keys.load(str(path))
    key = paramiko.Ed25519Key(data=base64.b64decode(observed["key"]))
    keys.add(host_label(host, port), "ssh-ed25519", key)
    temporary = folder / "known_hosts.tmp"
    keys.save(str(temporary))
    protect(temporary)
    temporary.replace(path)
    return observed


class SSHConnection:
    def __init__(self, device):
        self.device = device
        self.client = paramiko.SSHClient()
        self.sftp = None

    def __enter__(self):
        device = self.device
        if not device.get("fingerprint"):
            raise ValueError("Verificare e confermare prima la fingerprint SSH")
        path = ssh_directory() / "known_hosts"
        if not path.exists():
            raise ValueError("known_hosts dell'app assente: ripetere la verifica")
        self.client.load_host_keys(str(path))
        self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
        try:
            self.client.connect(
                device["host"],
                port=device["port"],
                username=device["username"],
                key_filename=str(ssh_directory() / "id_ed25519"),
                allow_agent=False,
                look_for_keys=False,
                timeout=8,
                auth_timeout=12,
                banner_timeout=8,
            )
            transport = self.client.get_transport()
            if transport is None:
                raise ValueError("Trasporto SSH non disponibile")
            if fingerprint(transport.get_remote_server_key()) != device["fingerprint"]:
                raise ValueError("Fingerprint del dispositivo non corrispondente")
            self.sftp = self.client.open_sftp()
            channel = self.sftp.get_channel()
            if channel is None:
                raise ValueError("Canale SFTP non disponibile")
            channel.settimeout(20)
            return self
        except Exception:
            self.client.close()
            raise

    def __exit__(self, *_):
        if self.sftp:
            self.sftp.close()
        self.client.close()

    def execute(self, command, limit=2_000_000):
        # Callers use fixed commands or a fixed interpreter with base64 JSON input.
        _, stdout, stderr = self.client.exec_command(command, timeout=20)
        output = stdout.read(limit + 1)
        error = stderr.read(4096)
        if len(output) > limit or stdout.channel.recv_exit_status() != 0:
            raise ValueError("Comando diagnostico fallito: " + error.decode("utf-8", "replace")[:300])
        return output.decode("utf-8", "replace").strip()
