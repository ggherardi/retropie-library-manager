"""Recognition-only fingerprints from MAME 0.280, independent of installable core DATs.

Sources: src/mame/namco/namcops2.cpp and src/mame/cinematronics/dlair.cpp.
Keys shared by disc revisions establish the game, not the disc revision.
"""

from dataclasses import dataclass

from backend.config import PLATFORM_LABELS


@dataclass(frozen=True)
class ReferenceGame:
    title: str
    platform: str
    driver: str
    programs: dict[str, frozenset[tuple[int, str]]]
    accessories: frozenset[tuple[int, str]]
    medium: str


REFERENCE_GAMES = (
    ReferenceGame(
        "Soul Calibur III: Arcade Edition",
        "namco-system-246",
        "namco/namcops2",
        {
            "soulclb3 / soulclb3b": frozenset(
                {
                    (8388608, "6bb2d31cb669336345b5508bcca56936ea97c04a"),
                    (262144, "13bc6a3688985c0cd9900b063824a4af691a1b31"),
                }
            ),
            "soulclb3a": frozenset({(8650752, "01e628344b2cde2edbda9ffea53af6a63e3bddf1")}),
        },
        frozenset({(2097152, "f0a74bbcaf801f3fd0b7002ebd0118564aae3528")}),
        "Il gioco usa anche un DVD separato. Le ROM identificano il titolo, la revisione del DVD resta da verificare.",
    ),
    ReferenceGame(
        "Tekken 5.1",
        "namco-system-256",
        "namco/namcops2",
        {
            "tekken51": frozenset(
                {
                    (8388608, "72ee2aea4032e9b03a735b1b6c7574233f0c7711"),
                    (262144, "ef10accbdc82143c31d29e2b8b812a209b341b1b"),
                }
            ),
        },
        frozenset({(2097152, "bc4fb4e1e53adbd92385f1726bd69663ff870f1e")}),
        "Il gioco usa anche un DVD separato.",
    ),
    ReferenceGame(
        "Dragon's Lair",
        "cinematronics-laserdisc",
        "cinematronics/dlair",
        {
            "dlairb": frozenset(
                (8192, sha)
                for sha in (
                    "fc7ff5d883de9b38a9e0532c35990f4b319ba1d3",
                    "e94e19f738e0eb69700e56c6069c7f3c0911303f",
                    "d4015046bf1c1f51c29d9d9f8e8d008519b61cd1",
                    "05b487e651a4817991dfc2308834b8f2fae918b4",
                    "0b8026927697a99fe8fa0dd4bd643418779a1d45",
                )
            ),
            "dlair": frozenset(
                (8192, sha)
                for sha in (
                    "c0cafff8b2982125fd3314ffc66681e47f027fc9",
                    "614ca8f6c5b6fa1d590f6b80d731377faa3a65a9",
                    "29d1015b951f0f2d4e5257497f3bf007c5e2262c",
                    "71149e2d359cc5944fbbb53dd7d0c2b42fbc9bb4",
                )
            ),
        },
        frozenset({(8192, "52f91c304a878ba02b2fa1cda1a9489d6dd5a34f")}),  # Pioneer LD-V1000 firmware
        "Le ROM contengono il programma. Le scene del gioco si trovano sul LaserDisc separato.",
    ),
)


def recognize(inventory):
    parts = {(part["size"], part["sha1"]) for part in inventory.values()}
    for game in REFERENCE_GAMES:
        # Leave mixed containers to normal per-member analysis.
        if not parts <= game.accessories.union(*game.programs.values()):
            continue
        matches = [name for name, program in game.programs.items() if program <= parts]
        if matches:
            return {
                "title": game.title,
                "platform": game.platform,
                "match": "verified",
                "basis": f"Dimensioni e SHA-1 delle ROM di programma nel catalogo MAME 0.280 ({', '.join(matches)}).",
                "catalog_url": f"https://github.com/mamedev/mame/blob/mame0280/src/mame/{game.driver}.cpp",
                "reason": f"I profili arcade gestiti (MAME 2003 e FinalBurn Neo) non supportano "
                f"{PLATFORM_LABELS[game.platform]} per questo gioco. {game.medium}",
            }
    return None
