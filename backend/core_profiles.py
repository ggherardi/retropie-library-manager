"""Read-only inspection of installed cores. Never start ES, initialize cores or load games."""

import hashlib
import re

from backend.remote_fs import rpc

PROFILES = {
    "lr-mame2003": {
        "name": "MAME 2003",
        "romset": "MAME 0.78",
        "extensions": [".zip"],
        "dat_url": "https://github.com/libretro/mame2003-libretro/blob/master/metadata/mame2003.xml",
    },
    "lr-fbneo": {
        "name": "FinalBurn Neo",
        "romset": "DAT della stessa revisione del core",
        "extensions": [".zip", ".7z"],
        "dat_url": "https://github.com/libretro/FBNeo/tree/master/dats",
    },
}

AUDIT = r'''
import os,pathlib,json,hashlib,subprocess,sys,base64
args=json.loads(base64.b64decode(sys.argv[1]))
INFO="""
import ctypes,json,sys
class Info(ctypes.Structure):
 _fields_=[('name',ctypes.c_char_p),('version',ctypes.c_char_p),('extensions',ctypes.c_char_p),('need_fullpath',ctypes.c_bool),('block_extract',ctypes.c_bool)]
lib=ctypes.CDLL(sys.argv[1]); value=Info()
lib.retro_get_system_info.argtypes=[ctypes.POINTER(Info)]; lib.retro_get_system_info.restype=None
lib.retro_get_system_info(ctypes.byref(value))
print(json.dumps({k:(getattr(value,k) or b'').decode('utf-8','replace')[:300] for k in ['name','version','extensions']}))
"""
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(262144),b''):h.update(block)
 return h.hexdigest()
def safe(path,root):
 p=pathlib.Path(path); r=pathlib.Path(root)
 return str(p.resolve()).startswith(str(r.resolve())+'/') and all(not q.is_symlink() for q in [p]+list(p.parents))
cores={}; base=pathlib.Path('/opt/retropie/libretrocores')
installed=[]
if base.is_dir():
 for directory in base.iterdir():
  if directory.is_dir() and not directory.is_symlink():
   installed.append(directory.name)
for key,filename in [('lr-mame2003','mame2003_libretro.so'),('lr-fbneo','fbneo_libretro.so')]:
 path=base/key/filename; item={'installed':path.is_file(),'path':str(path),'version':None,'sha256':None}
 if item['installed'] and safe(path,base):
  item['sha256']=sha(path)
  try:
   p=subprocess.run([sys.executable,'-c',INFO,str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=6)
   if p.returncode==0:item.update(json.loads(p.stdout.decode()))
   else:item['error']='Impossibile leggere retro_get_system_info; nessuna compatibilita assunta'
  except (OSError,ValueError,subprocess.TimeoutExpired):item['error']='Metadati core non rilevabili'
 cores[key]=item
configs={}
for system in list(args['platforms'])+['all']:
 path=pathlib.Path('/opt/retropie/configs')/system/'emulators.cfg'
 try:
  if path.stat().st_size<100000: configs[system]=path.read_text(errors='replace')
 except OSError:pass
bios=[]
for root in [args['bios_root'],args['bios_root']+'/fbneo',args['rom_root']+'/neogeo']:
 directory=pathlib.Path(root)
 if not directory.is_dir():continue
 for path in directory.iterdir():
  if path.is_file() and path.name.lower() in ['neogeo.zip','neocd.bin','aes-bios.bin'] and safe(path,root):
   bios.append({'path':str(path),'size':path.stat().st_size,'sha256':sha(path),'contents_checked':False})
sessions=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  if os.readlink(str(p/'exe'))!='/opt/retropie/supplementary/emulationstation/emulationstation':continue
  tty=int((p/'stat').read_text().rsplit(')',1)[1].split()[4]); stdin=os.readlink(str(p/'fd/0'))
  sessions.append({'pid':int(p.name),'tty_nr':tty,'stdin':stdin,'valid_local_session':tty!=0 and stdin.startswith('/dev/tty')})
 except (OSError,ValueError):pass
dirs={system:{'exists':os.path.isdir(args['rom_root']+'/'+system),'writable':os.access(args['rom_root']+'/'+system,os.W_OK)} for system in args['platforms']}
s=os.statvfs(args['rom_root'])
print(json.dumps({'cores':cores,'installed_cores':installed,'configs':configs,'bios_inventory':bios,'emulationstation_sessions':sessions,'directories':dirs,'space':{'total':s.f_blocks*s.f_frsize,'free':s.f_bavail*s.f_frsize},'read_only':True}))
'''


def audit_cores(connection, config, platforms):
    result = rpc(connection, AUDIT, {**config, "platforms": list(platforms)})
    result["profiles"] = PROFILES
    return result


def compatible(source, core, observed, binding=None):
    if (
        core not in PROFILES
        or not observed
        or not observed.get("installed")
        or not observed.get("version")
        or not observed.get("sha256")
    ):
        return False, "Core installato/versione non verificati"
    if source.config.get("core") != core:
        return False, "DAT riferito a un core diverso"
    version = source.config.get("version", "")
    if core == "lr-mame2003":
        valid = bool(
            re.search(r"(?<!\d)0\.78(?!\d)", version) and str(observed["version"]).startswith("0.78")
        )
        return (
            valid,
            "MAME 0.78 rilevato" if valid else "MAME 2003 richiede DAT 0.78, non 2003-plus o altre versioni",
        )
    commit = re.search(r"\b([a-f0-9]{7,40})\b", observed["version"])
    revision = source.config.get("revision", "")
    if (
        commit
        and source.config.get("official_verified") is True
        and len(revision) == 40
        and revision.startswith(commit.group(1))
        and source.config.get("source_url", "").startswith(
            "https://raw.githubusercontent.com/libretro/FBNeo/" + revision + "/dats/"
        )
    ):
        return True, "DAT ufficiale della revisione Git rilevata nel core"
    if (
        binding
        and binding.source_sha == source.sha256
        and binding.binary_sha == observed["sha256"]
        and binding.version == observed["version"]
    ):
        return True, "Corrispondenza DAT/core documentata dall’operatore e fissata ai rispettivi hash"
    return (
        False,
        "FBNeo richiede associazione documentata tra questo DAT e la revisione installata; il solo numero di versione non basta",
    )


def configured_core(audit, platform, archive_stem, rom_root="", extension=".zip", rom_path=""):
    text = audit.get("configs", {}).get(platform, "")
    values = {m.group(1): m.group(2) for m in re.finditer(r'^\s*([\w-]+)\s*=\s*"([^"\n]+)"', text, re.M)}
    overrides = {
        m.group(1): m.group(2)
        for m in re.finditer(r'^\s*([\w-]+)\s*=\s*"([^"\n]+)"', audit.get("configs", {}).get("all", ""), re.M)
    }
    key = re.sub(r"[^a-zA-Z0-9_-]", "", platform + "_" + archive_stem)
    old = (
        "a"
        + hashlib.md5(
            (
                platform + (rom_path or rom_root + "/" + platform + "/" + archive_stem + extension) + "\n"
            ).encode()
        ).hexdigest()
    )
    default = values.get("default", "")
    # runcommand requires a system default before applying a per-game override.
    return (overrides.get(old) or overrides.get(key) or default) if default else "", set(values)
