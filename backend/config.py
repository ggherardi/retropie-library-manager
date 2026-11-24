import os
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("RLM_DATA_DIR", str(PROJECT / "data"))).resolve()
PLATFORMS = {
    "nes": "NES / Famicom",
    "snes": "Super Nintendo",
    "mastersystem": "Master System",
    "megadrive": "Mega Drive / Genesis",
    "sg-1000": "SG-1000",
    "pcengine": "PC Engine / TurboGrafx-16",
    "atari2600": "Atari 2600",
    "atari7800": "Atari 7800",
    "gamegear": "Game Gear",
    "ngp": "Neo Geo Pocket",
    "ngpc": "Neo Geo Pocket Color",
    "gb": "Game Boy",
    "gbc": "Game Boy Color",
    "gba": "Game Boy Advance",
    "neogeo": "Neo Geo",
    "arcade": "Arcade",
    "mame-libretro": "MAME 2003",
    "fba": "FinalBurn Neo",
    "psx": "PlayStation",
}
# Labels used by identification can include systems without an installation profile.
PLATFORM_LABELS = {
    **PLATFORMS,
    "namco-system-246": "Namco System 246",
    "namco-system-256": "Namco System 256",
    "cinematronics-laserdisc": "Cinematronics LaserDisc",
    "c64": "Commodore 64",
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
    ".sg": "sg-1000",
    ".pce": "pcengine",
    ".a26": "atari2600",
    ".a78": "atari7800",
    ".gg": "gamegear",
    ".ngp": "ngp",
    ".ngc": "ngpc",
    ".cue": "psx",
    ".chd": "psx",
    ".pbp": "psx",
    ".iso": "psx",
}

ARCADE_PLATFORMS = {"arcade", "neogeo", "mame-libretro", "fba"}
