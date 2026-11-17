import os
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("RLM_DATA_DIR", str(PROJECT / "data"))).resolve()
PLATFORMS = {
    "nes": "NES / Famicom",
    "snes": "Super Nintendo",
    "mastersystem": "Master System",
    "megadrive": "Mega Drive / Genesis",
    "gb": "Game Boy",
    "gbc": "Game Boy Color",
    "gba": "Game Boy Advance",
    "neogeo": "Neo Geo",
    "arcade": "Arcade",
    "psx": "PlayStation",
}
EXTENSIONS = {
    ".nes": "nes",
    ".fds": "nes",
    ".sfc": "snes",
    ".smc": "snes",
    ".sms": "mastersystem",
    ".md": "megadrive",
    ".gen": "megadrive",
    ".smd": "megadrive",
    ".gb": "gb",
    ".gbc": "gbc",
    ".gba": "gba",
    ".cue": "psx",
    ".chd": "psx",
    ".pbp": "psx",
    ".iso": "psx",
}
