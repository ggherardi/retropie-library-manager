"""Interactive OpenSSH enrollment: passwords are entered only in the user's terminal."""

import argparse
import base64
import subprocess

from backend.ssh_connection import SSHConnection, ensure_key, ssh_directory

INSTALL = r"""
import base64, os, pathlib, shutil, sys, time, uuid
key=base64.b64decode(sys.argv[1]).decode().strip()
assert key.startswith('ssh-ed25519 ') and '\n' not in key
folder=pathlib.Path.home()/'.ssh'
assert not folder.is_symlink(), 'Symlink .ssh non consentito'
folder.mkdir(mode=0o700, exist_ok=True)
assert folder.stat().st_uid == os.getuid(), 'Proprietario .ssh inatteso'
target=folder/'authorized_keys'
assert not target.is_symlink(), 'Symlink authorized_keys non consentito'
old=b''
if target.exists():
 assert target.is_file() and target.stat().st_uid == os.getuid()
 assert target.stat().st_size < 1000000
 old=target.read_bytes()
 if any(line.split()[:2] == key.encode().split()[:2] for line in old.splitlines()):
  print('Chiave gia presente'); sys.exit(0)
 backup=folder/('authorized_keys.rlm-backup-'+time.strftime('%Y%m%d%H%M%S')+'-'+uuid.uuid4().hex[:8])
 shutil.copy2(target, backup); backup.chmod(0o600)
 print('Backup: '+str(backup))
temporary=folder/('authorized_keys.rlm-'+uuid.uuid4().hex)
fd=os.open(str(temporary), os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
with os.fdopen(fd,'wb') as stream:
 stream.write(old + (b'\n' if old and not old.endswith(b'\n') else b'') + key.encode()+b'\n')
 stream.flush(); os.fsync(stream.fileno())
temporary.replace(target); folder.chmod(0o700)
print('Chiave pubblica installata; autenticazione password invariata.')
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--fingerprint", required=True)
    args = parser.parse_args()
    identity = ensure_key()
    code = base64.b64encode(INSTALL.encode()).decode()
    public = base64.b64encode(identity["public_key"].encode()).decode()
    command = f"python3 -c \"import base64;exec(base64.b64decode('{code}'))\" {public}"
    print("Configurazione RetroPie Library Manager. Inserire la password soltanto nel prompt SSH.")
    print("Server verificato: " + args.fingerprint)
    result = subprocess.run(
        [
            "ssh",
            "-F",
            "none",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={ssh_directory() / 'known_hosts'}",
            "-o",
            "HostKeyAlgorithms=ssh-ed25519",
            "-o",
            "ConnectTimeout=10",
            "-p",
            str(args.port),
            "-i",
            identity["path"],
            f"{args.username}@{args.host}",
            command,
        ],
        check=False,
    )
    if result.returncode:
        raise SystemExit("Installazione non completata. Riprovare dall’app.")
    with SSHConnection(vars(args)) as remote:
        print("Accesso con chiave e SFTP verificati: " + remote.sftp.normalize("."))
    input("Configurazione completata. Premere Invio per chiudere.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Configurazione non completata: " + str(exc))
        input("Premere Invio per chiudere. La password non è stata memorizzata.")
        raise SystemExit(1) from None
