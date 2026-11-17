"""Local SFTP protocol double. Used only by tests, never by the production service."""

import base64
import json
import os
from pathlib import Path
from types import SimpleNamespace

from backend.config import EXTENSIONS, PLATFORMS


class LocalSFTP:
    def __init__(self, root):
        self.root = root
        self.writes = 0
        self.links = set()

    def resolve(self, path):
        return self.root / path.lstrip("/")

    def lstat(self, path):
        if path in self.links:
            return SimpleNamespace(st_mode=0o120777, st_size=0)
        return self.resolve(path).lstat()

    stat = lstat

    def open(self, path, mode="r"):
        if any(c in mode for c in "wax"):
            self.writes += 1
        mode = "xb" if "x" in mode else mode if "b" in mode else mode + "b"
        return self.resolve(path).open(mode)

    def mkdir(self, path, mode=0o755):
        self.writes += 1
        self.resolve(path).mkdir(mode=mode)

    def remove(self, path):
        self.resolve(path).unlink()

    def rmdir(self, path):
        self.resolve(path).rmdir()

    def rename(self, old, new):
        if self.resolve(new).exists():
            raise FileExistsError(new)
        self.resolve(old).rename(self.resolve(new))

    def posix_rename(self, old, new):
        os.replace(self.resolve(old), self.resolve(new))

    def normalize(self, path):
        return "/home/pi" if path == "." else path

    def listdir_attr(self, path):
        return [
            SimpleNamespace(filename=p.name, st_mode=p.lstat().st_mode) for p in self.resolve(path).iterdir()
        ]


class FakeConnection:
    def __init__(self, root: Path):
        self.sftp = LocalSFTP(root)
        self.free = 27_000_000_000
        self.running = False
        for directory in [
            "/home/pi/RetroPie/roms",
            "/home/pi/RetroPie/BIOS",
            "/opt/retropie/configs/all/emulationstation/gamelists",
            "/etc/emulationstation",
        ]:
            self.sftp.resolve(directory).mkdir(parents=True, exist_ok=True)
        systems = []
        for platform in PLATFORMS:
            self.sftp.resolve("/home/pi/RetroPie/roms/" + platform).mkdir(exist_ok=True)
            extensions = [ext for ext, p in EXTENSIONS.items() if p == platform]
            if platform == "psx":
                extensions += [".m3u"]
            systems.append(
                f"<system><name>{platform}</name><path>/home/pi/RetroPie/roms/{platform}</path><extension>{' '.join(extensions)}</extension></system>"
            )
        self.sftp.resolve("/etc/emulationstation/es_systems.cfg").write_text(
            "<systemList>" + "".join(systems) + "</systemList>"
        )
        core = self.sftp.resolve("/opt/retropie/configs/psx/emulators.cfg")
        core.parent.mkdir(parents=True, exist_ok=True)
        core.write_text('default = "lr-pcsx-rearmed"')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, command):
        code = base64.b64decode(command.split("base64.b64decode('")[1].split("')")[0]).decode()
        if "memory=" not in code:
            return json.dumps({"free": self.free, "total": 31_000_000_000})
        return json.dumps(
            {
                "model": "Synthetic Pi",
                "hostname": "test-pi",
                "home": "/home/pi",
                "es_root": "/opt/retropie/configs/all/emulationstation",
                "es_running": self.running,
                "systems_config": "/etc/emulationstation/es_systems.cfg",
                "space": {"free": self.free, "total": 31_000_000_000},
                "directories": {},
                "ssh_service": "active",
            }
        )
