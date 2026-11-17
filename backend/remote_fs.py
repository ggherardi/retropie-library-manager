"""SFTP paths are data, never shell fragments. Mutations stay inside explicit roots."""

import base64
import errno
import hashlib
import io
import json
import posixpath
import stat
from pathlib import PurePosixPath

from defusedxml import ElementTree as SafeXML

from backend.sync_schemas import remote_path


def rpc(connection, code, values=None):
    source = base64.b64encode(code.encode()).decode()
    args = base64.b64encode(json.dumps(values or {}).encode()).decode()
    return json.loads(
        connection.execute(f"python3 -c \"import base64;exec(base64.b64decode('{source}'))\" {args}")
    )


SPACE = """
import os,json,base64,sys
p=json.loads(base64.b64decode(sys.argv[1]))['path']
while not os.path.exists(p):
 p=os.path.dirname(p)
s=os.statvfs(p)
print(json.dumps({'total':s.f_blocks*s.f_frsize,'free':s.f_bavail*s.f_frsize}))
"""

DIAGNOSTICS = r"""
import os,json,socket,pathlib,subprocess,re,base64,sys
args=json.loads(base64.b64decode(sys.argv[1]))
def read(path):
 try: return pathlib.Path(path).read_text(errors='replace')[:100000].strip().strip('\0')
 except OSError: return None
def run(argv):
 try:
  p=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=5)
  return p.stdout.decode(errors='replace').strip() or None
 except (OSError,subprocess.TimeoutExpired): return None
home=str(pathlib.Path.home())
es=os.path.realpath(home+'/.emulationstation')
osinfo=read('/etc/os-release')
memory={line.split(':')[0]:int(line.split()[1])*1024 for line in (read('/proc/meminfo') or '').splitlines() if ':' in line}
running=any((read(str(p/'comm')) or '').startswith('emulationstatio') for p in pathlib.Path('/proc').iterdir() if p.name.isdigit())
log=read(es+'/es_log.txt') or ''
version=re.search(r'EmulationStation\s+(?:-\s*)?v?([0-9][\w.\-]+)',log)
rp=read('/opt/retropie/configs/all/retropie-release') or read('/etc/retropie-release')
if not rp:
 setup=read(home+'/RetroPie-Setup/retropie_packages.sh') or ''
 match=re.search(r'__version=["\x27]([^"\x27]+)',setup)
 rp=match.group(1) if match else None
directories={}
for key in ['rom_root','bios_root']:
 p=args[key]; directories[key]={'path':p,'exists':os.path.isdir(p),'readable':os.access(p,os.R_OK),'writable':os.access(p,os.W_OK)}
space=None
try:
 fs=os.statvfs(args['rom_root']); space={'total':fs.f_blocks*fs.f_frsize,'free':fs.f_bavail*fs.f_frsize}
except OSError: pass
temp=read('/sys/class/thermal/thermal_zone0/temp')
uptime=read('/proc/uptime')
print(json.dumps({'model':read('/proc/device-tree/model'),'hostname':socket.gethostname(),'os':osinfo,
 'retropie_version':rp,'emulationstation_version':version.group(1) if version else None,
 'ip':run(['hostname','-I']),'uptime_seconds':float(uptime.split()[0]) if uptime else None,
 'temperature_c':float(temp)/1000 if temp else None,'ram_total':memory.get('MemTotal'),'ram_available':memory.get('MemAvailable'),
 'space':space,'directories':directories,'ssh_service':run(['systemctl','is-active','ssh']),
 'home':home,'es_root':es,'es_running':running,
 'systems_config':home+'/.emulationstation/es_systems.cfg' if os.path.exists(home+'/.emulationstation/es_systems.cfg') else '/etc/emulationstation/es_systems.cfg'}))
"""


def diagnostics(connection, config):
    result = rpc(connection, DIAGNOSTICS, config)
    result["ssh"] = True
    result["sftp"] = bool(connection.sftp.normalize("."))
    home = result["home"]
    es = result["es_root"]
    if not (es.startswith(home + "/") or es.startswith("/opt/retropie/configs/")):
        raise ValueError("La directory EmulationStation risolve fuori dalle radici previste")
    path = result["systems_config"]
    if connection.sftp.stat(path).st_size > 1_000_000:
        raise ValueError("Configurazione EmulationStation troppo grande")
    with connection.sftp.open(path, "rb") as stream:
        root = SafeXML.fromstring(stream.read(1_000_001))
    result["systems"] = {}
    for system in root.findall("system"):
        name = system.findtext("name")
        result["systems"][name] = {
            "path": (system.findtext("path") or "").replace("~", home, 1),
            "extensions": (system.findtext("extension") or "").lower().split(),
        }
    try:
        with connection.sftp.open("/opt/retropie/configs/psx/emulators.cfg", "rb") as stream:
            result["psx_emulator_config"] = stream.read(65536).decode("utf-8", "replace")
    except OSError:
        result["psx_emulator_config"] = None
    return result


class SafeRemote:
    def __init__(self, connection, roots):
        self.connection = connection
        self.sftp = connection.sftp
        self.roots = [remote_path(root) for root in roots]

    def path(self, value):
        value = remote_path(value)
        if not any(value == root or value.startswith(root + "/") for root in self.roots):
            raise ValueError("Percorso remoto fuori dalle directory autorizzate")
        # Inspect every ancestor: no implicit traversal through symlinks.
        current = ""
        for part in PurePosixPath(value).parts[1:]:
            current += "/" + part
            try:
                info = self.sftp.lstat(current)
                if stat.S_ISLNK(info.st_mode):
                    raise ValueError("Symlink remoto non consentito: " + current)
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    raise
                break
        return value

    def info(self, path):
        path = self.path(path)
        try:
            return self.sftp.lstat(path)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                return None
            raise

    def read(self, path, limit=10_000_000):
        info = self.info(path)
        if info is None:
            return None
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError("File remoto non regolare o troppo grande")
        with self.sftp.open(self.path(path), "rb") as stream:
            value = stream.read(limit + 1)
        if len(value) > limit:
            raise ValueError("File remoto troppo grande")
        return value

    def hash(self, path):
        info = self.info(path)
        if info is None:
            return None
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Atteso un file regolare")
        sha = hashlib.sha256()
        with self.sftp.open(self.path(path), "rb") as stream:
            for chunk in iter(lambda: stream.read(262144), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def mkdir(self, path):
        path = self.path(path)
        if self.info(path):
            if not stat.S_ISDIR(self.info(path).st_mode):
                raise ValueError("Una directory è occupata da un file")
            return
        self.mkdir(posixpath.dirname(path))
        self.sftp.mkdir(path, 0o755)

    def space(self, path):
        return rpc(self.connection, SPACE, {"path": self.path(path)})

    def upload(self, path, source, size, expected, checkpoint):
        path = self.path(path)
        self.mkdir(posixpath.dirname(path))
        info = self.info(path)
        offset = info.st_size if info else 0
        if info and not stat.S_ISREG(info.st_mode):
            raise ValueError("Parziale non regolare")
        if offset > size:
            self.sftp.remove(path)
            offset = 0
        # Resume only if the remote prefix is identical to the local prefix.
        if offset:
            valid_prefix = True
            with self.sftp.open(path, "rb") as existing:
                remaining = offset
                while remaining:
                    checkpoint(0)
                    chunk = existing.read(min(262144, remaining))
                    if not chunk or chunk != source.read(len(chunk)):
                        valid_prefix = False
                        break
                    remaining -= len(chunk)
            if not valid_prefix:
                self.sftp.remove(path)
                offset = 0
        source.seek(offset)
        checkpoint(offset)
        with self.sftp.open(path, "ab" if offset else "wb") as target:
            while offset < size:
                chunk = source.read(min(65536, size - offset))
                if not chunk:
                    raise ValueError("File locale troncato")
                target.write(chunk)
                offset += len(chunk)
                checkpoint(offset)
            target.flush()
        if self.hash(path) != expected:
            self.sftp.remove(path)
            raise ValueError("SHA-256 remoto non corrispondente")
        checkpoint(size)

    def write_new(self, path, content):
        self.mkdir(posixpath.dirname(path))
        with self.sftp.open(self.path(path), "wx") as stream:
            stream.write(content)

    def rename_new(self, old, new):
        if self.info(new):
            raise ValueError("Destinazione remota già esistente; nessuna sovrascrittura")
        self.sftp.rename(self.path(old), self.path(new))

    def remove_owned_tree(self, path, marker):
        path = self.path(path)
        if marker not in PurePosixPath(path).name or not marker.startswith(".rlm-"):
            raise ValueError("Pulizia limitata allo staging di questa operazione")
        if not self.info(path):
            return

        def remove(directory):
            for item in self.sftp.listdir_attr(self.path(directory)):
                child = self.path(directory + "/" + item.filename)
                if stat.S_ISDIR(item.st_mode):
                    remove(child)
                elif stat.S_ISREG(item.st_mode):
                    self.sftp.remove(child)
                else:
                    raise ValueError("Elemento inatteso nello staging")
            self.sftp.rmdir(directory)

        remove(path)


def binary_source(item):
    return open(item["source"], "rb") if item.get("source") else io.BytesIO(base64.b64decode(item["content"]))
