"""Read-only configured-core and BIOS checks; never launches or stops a process."""

from pathlib import PurePosixPath

from backend.config import ARCADE_PLATFORMS
from backend.content_checks import PSX_BIOS
from backend.remote_fs import rpc

PREFLIGHT = r"""
import pathlib,json,sys,base64,re,hashlib
args=json.loads(base64.b64decode(sys.argv[1])); platform=args['platform']
# installation_preflight_v1
path=pathlib.Path('/opt/retropie/configs')/platform/'emulators.cfg'
text=path.read_text(errors='replace') if path.is_file() and path.stat().st_size<100000 else ''
values=dict(re.findall(r'^\s*([\w-]+)\s*=\s*"([^"\n]+)"',text,re.M))
core=values.get('default','')
overrides=pathlib.Path('/opt/retropie/configs/all/emulators.cfg')
if core and args.get('rom_path') and overrides.is_file() and overrides.stat().st_size<100000:
 other=dict(re.findall(r'^\s*([\w-]+)\s*=\s*"([^"\n]+)"',overrides.read_text(errors='replace'),re.M))
 old='a'+hashlib.md5((platform+args['rom_path']+'\n').encode()).hexdigest()
 key=re.sub(r'[^a-zA-Z0-9_-]','',platform+'_'+pathlib.Path(args['rom_path']).stem)
 core=other.get(old) or other.get(key) or core
command=values.get(core,'')
binaries=re.findall(r'(/opt/retropie/[^\s"\x27]+)',command)
core_binaries=[p for p in binaries if p.endswith('.so')] if core.startswith('lr-') else binaries
installed=bool(core and core_binaries and all(pathlib.Path(p).is_file() for p in core_binaries))
bios=[]
if platform=='psx':
 for name,expected in args['bios'].items():
  p=pathlib.Path(args['bios_root'])/name
  present=p.is_file() and not p.is_symlink(); md5=None
  if present and p.stat().st_size==524288:md5=hashlib.md5(p.read_bytes()).hexdigest()
  bios.append({'name':name,'available':present,'md5':md5,'verified':md5==expected})
print(json.dumps({'core':core,'installed':installed,'bios':bios,'read_only':True}))
"""


class PreflightError(ValueError):
    def __init__(self, message, report):
        super().__init__(message)
        self.report = report


def preflight(connection, config, platform, game=None):
    if platform in ARCADE_PLATFORMS:
        return {"basis": "Validazione DAT/core/BIOS effettuata dal servizio arcade durante il dry-run"}
    rom_path = ""
    if game:
        launch = "discs.m3u" if game.format == "multidisc" else game.files[0]["relative"]
        rom_path = str(PurePosixPath(config["rom_root"]) / platform / ("rlm-" + game.sha256[:24]) / launch)
    result = rpc(
        connection, PREFLIGHT, {**config, "platform": platform, "bios": PSX_BIOS, "rom_path": rom_path}
    )
    if not result["installed"]:
        raise PreflightError(
            "Core configurato non disponibile per "
            + platform
            + ". Verificare il dispositivo dalla console locale.",
            result,
        )
    if platform == "psx":
        if result["core"] != "lr-pcsx-rearmed":
            raise PreflightError(
                "Preflight BIOS PS1 disponibile per lr-pcsx-rearmed; altro core richiede revisione. Nessuna configurazione modificata.",
                result,
            )
        if not any(b["verified"] for b in result["bios"]):
            raise PreflightError(
                "BIOS PS1 mancante o hash non verificato: fornire localmente un BIOS legittimo compatibile, ad esempio scph1001.bin o scph5501.bin. Nessun download automatico.",
                result,
            )
    return result
