"""Pinned FBNeo MVS profile. Unknown DAT revisions retain strict validation.

Evidence: libretro/FBNeo af50579270a610eda8ac580648d9c12acc7bb565,
d_neogeo.cpp:938-990; neo_run.cpp:435; retro_common.cpp:329.
"""

from backend.remote_fs import rpc

REVISION = "af50579270a610eda8ac580648d9c12acc7bb565"
REQUIRED = {"sp-s3.sp1", "sm1.sm1", "sfix.sfix", "000-lo.lo"}
PARTS = {
    "sp-s3.sp1": (131072, "91b64be3"),
    "sp-s2.sp1": (131072, "9036d879"),
    "sp-s.sp1": (131072, "c7f2fa45"),
    "sp-u2.sp1": (131072, "e72943de"),
    "sp1-u2": (131072, "62f021f4"),
    "sp-e.sp1": (131072, "2723a5b5"),
    "sp1-u4.bin": (131072, "1179a30f"),
    "sp1-u3.bin": (131072, "2025b7a2"),
    "vs-bios.rom": (131072, "f0e8f27d"),
    "sp-j2.sp1": (131072, "acede59c"),
    "sp1.jipan.1024": (131072, "9fb0abe4"),
    "sp-45.sp1": (524288, "03cc9f6a"),
    "sp-j3.sp1": (524288, "486cb450"),
    "japan-j3.bin": (131072, "dff6d41f"),
    "sp1-j3.bin": (131072, "fbc6d469"),
    "neo-po.bin": (131072, "16d0c132"),
    "neo-epo.bin": (131072, "d27a71f1"),
    "neodebug.bin": (131072, "698ebb7d"),
    "sp-1v1_3db8c.bin": (131072, "162f0ebe"),
    "uni-bios_4_0.rom": (131072, "a7aab458"),
    "uni-bios_3_3.rom": (131072, "24858466"),
    "uni-bios_3_2.rom": (131072, "a4e8b9b3"),
    "uni-bios_3_1.rom": (131072, "0c58093f"),
    "uni-bios_3_0.rom": (131072, "a97c89a9"),
    "uni-bios_2_3.rom": (131072, "27664eb5"),
    "uni-bios_2_3o.rom": (131072, "601720ae"),
    "uni-bios_2_2.rom": (131072, "2d50996a"),
    "uni-bios_2_1.rom": (131072, "8dabf76b"),
    "uni-bios_2_0.rom": (131072, "0c12c2ad"),
    "uni-bios_1_3.rom": (131072, "b24b44a0"),
    "uni-bios_1_2.rom": (131072, "4fa698e9"),
    "uni-bios_1_2o.rom": (131072, "e19d3ce9"),
    "uni-bios_1_1.rom": (131072, "5dda0d84"),
    "uni-bios_1_0.rom": (131072, "0ce453a0"),
    "neopen.sp1": (131072, "cb915e76"),
    "sm1.sm1": (131072, "94416d67"),
    "sfix.sfix": (131072, "c2ea0cfd"),
    "000-lo.lo": (131072, "5a86cff2"),
}


def mvs_profile(catalog, source):
    bios = catalog.get("neogeo", {})
    actual = {p["name"]: (p["size"], p.get("crc")) for p in bios.get("components", [])}
    return bool(
        source
        and source.get("official_verified") is True
        and source.get("core") == "lr-fbneo"
        and source.get("revision") == REVISION
        and bios.get("kind") == "bios"
        and actual == PARTS
    )


def check_mvs_configuration(connection):
    result = rpc(
        connection,
        r"""import json,pathlib
roots=[pathlib.Path('/opt/retropie/configs/all'),pathlib.Path('/opt/retropie/configs/neogeo')]
files=[]
for root in roots:
 files += [p for p in root.glob('*.cfg') if p.name.startswith('retroarch')]
 core=root/'retroarch/config/FinalBurn Neo'
 if core.is_dir(): files += list(core.glob('*.opt'))+list(core.glob('*.cfg'))
if len(files)>500:raise ValueError('Troppi override core')
conflicts=[]
emulators=pathlib.Path('/opt/retropie/configs/neogeo/emulators.cfg')
expected='/opt/retropie/emulators/retroarch/bin/retroarch -L /opt/retropie/libretrocores/lr-fbneo/fbneo_libretro.so --config /opt/retropie/configs/neogeo/retroarch.cfg %ROM%'
commands=[line.split('=',1)[1].strip().strip('"') for line in emulators.read_text().splitlines() if line.split('=',1)[0].strip()=='lr-fbneo']
if commands!=[expected]:conflicts.append('Comando lr-fbneo personalizzato non coperto dal profilo MVS')
for p in files:
 if p.is_symlink() or p.stat().st_size>1000000:raise ValueError('Configurazione non verificabile')
 for line in p.read_text(errors='strict').splitlines():
  line=line.strip()
  if line.startswith('#include') and line not in ['#include "/opt/retropie/configs/all/retroarch.cfg"']:conflicts.append(str(p)+': include non verificato')
  if not line or line.startswith('#') or '=' not in line:continue
  key,value=[v.strip().strip('"') for v in line.split('=',1)]
  if key=='core_options_path' and value not in ['', '/opt/retropie/configs/all/retroarch-core-options.cfg']:conflicts.append(str(p)+': '+key)
  if key=='core_options_directory' and value:conflicts.append(str(p)+': '+key)
  if key=='fbneo-neogeo-mode' and value not in ['DIPSWITCH','MVS_EUR']:conflicts.append(str(p)+': '+key)
  if key.startswith('fbneo') and 'bios' in key.lower() and 'dipswitch' in key.lower() and value not in ['0','0x00','MVS Asia/Europe ver. 6 (1 slot)']:conflicts.append(str(p)+': '+key)
print(json.dumps({'profile':'fbneo-mvs-standard-v1','checked_files':[str(p) for p in files],'conflicts':conflicts}))
""",
        {},
    )
    if result["conflicts"]:
        raise ValueError("Profilo MVS standard non applicabile: " + ", ".join(result["conflicts"]))
    return result


def shared_bios(connection, config, catalog, source, path, *, authorized=False):
    """Explicit BIOS operation using the ordinary bounded SFTP/hash primitives.

    Default is read-only dry-run; existing different files are never overwritten.
    """
    from uuid import uuid4

    from backend.arcade_archives import validate_set
    from backend.core_profiles import audit_cores
    from backend.paths import digest
    from backend.remote_fs import SafeRemote

    if not mvs_profile(catalog, source):
        raise ValueError("Profilo DAT MVS non verificato")
    audit = audit_cores(connection, config, ["neogeo"])
    observed = audit["cores"]["lr-fbneo"]
    if not observed.get("installed") or "af50579" not in observed.get("version", ""):
        raise ValueError("Revisione core non compatibile con il profilo BIOS")
    check_mvs_configuration(connection)
    report = validate_set(catalog["neogeo"], catalog, {"neogeo": path}, "non-merged", source_config=source)
    if report["status"] != "complete":
        raise ValueError("BIOS incompleto o hash non corrispondenti")
    remote = SafeRemote(connection, [config["bios_root"]])
    target = config["bios_root"] + "/neogeo.zip"
    sha = digest(path)
    size = path.stat().st_size
    actual = remote.hash(target)
    if actual not in [None, sha]:
        raise ValueError("BIOS remoto differente: sovrascrittura vietata")
    free = remote.space(config["bios_root"])["free"]
    if free - (size if actual is None else 0) < max(4 * 1024**3, config["safety_bytes"]):
        raise ValueError("Margine disco inferiore a 4 GiB")
    result = {
        "path": target,
        "sha256": sha,
        "size": size,
        "free": free,
        "state": "present" if actual else "new",
        "dry_run": not authorized,
        "bios_profile": report["bios_profile"],
    }
    if authorized and actual is None:
        temporary = config["bios_root"] + "/.rlm-bios-" + str(uuid4()) + ".part"
        with path.open("rb") as stream:
            remote.upload(temporary, stream, size, sha, lambda count: None)
        if digest(path) != sha:
            raise ValueError("Originale BIOS modificato durante il trasferimento")
        remote.rename_new(temporary, target)
    if authorized:
        if remote.hash(target) != sha:
            raise ValueError("SHA-256 BIOS finale non corrispondente")
        result["verified"] = True
    return result
