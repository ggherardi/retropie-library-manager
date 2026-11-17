import posixpath
import re
import xml.etree.ElementTree as ET

from defusedxml.ElementTree import DefusedXMLParser

MANAGED_FOLDER = re.compile(r"rlm-[0-9a-f]{24}", re.IGNORECASE)
INTERNAL_TITLE = re.compile(r"(?:rlm-[0-9a-f]+|[0-9a-f]{32,64}|game-\d+)", re.IGNORECASE)
GENERIC_FILENAME = re.compile(r"(?:tracks?|discs?|disks?|rom|game)[\s_.-]*\d*", re.IGNORECASE)


def parse_xml(content):
    parser = DefusedXMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True), forbid_dtd=True)
    return ET.fromstring(content, parser=parser)


def _readable_title(value: str | None) -> str | None:
    title = (value or "").strip()
    return (
        title if title and not INTERNAL_TITLE.fullmatch(title) and title != "Titolo da verificare" else None
    )


def _matching_node(root, kind: str, path: str, system_root: str):
    absolute = posixpath.normpath(posixpath.join(system_root, path))
    matches = [
        node
        for node in root.findall(kind)
        if posixpath.normpath(posixpath.join(system_root, node.findtext("path") or "")) == absolute
    ]
    if len(matches) > 1:
        raise ValueError(f"Più record XML {kind} per lo stesso percorso: revisione richiesta")
    return matches[0] if matches else None


def _update(node, values: dict) -> bool:
    changed = False
    for tag, value in values.items():
        if value is None or value == "":
            continue  # Missing local metadata never erases a populated remote field.
        if any(ord(c) < 32 and c not in "\t\r\n" for c in str(value)):
            raise ValueError("Caratteri XML non validi nei metadati")
        child = node.find(tag)
        if child is None:
            if tag == "favorite" and value == "false":
                continue  # EmulationStation omits default false when saving its own metadata.
            child = ET.SubElement(node, tag)
        if child.text != str(value):
            child.text = str(value)
            changed = True
    return changed


def merge_gamelist(
    existing: bytes | None,
    games: list[dict],
    system_root: str,
    title_reviews: list[dict] | None = None,
) -> bytes:
    root = parse_xml(existing) if existing else ET.Element("gameList")
    if root.tag != "gameList":
        raise ValueError("Radice XML gamelist non valida")
    changed = False
    folder_titles: dict[str, str] = {}
    for game in games:
        launch = game["launch"]
        if launch.startswith("/") or "\\" in launch or any(p in {"", ".", ".."} for p in launch.split("/")):
            raise ValueError("Percorso di avvio non valido")
        relative = "./" + launch
        node = _matching_node(root, "game", launch, system_root)
        group = launch.split("/", 1)[0]
        managed = "/" in launch and MANAGED_FOLDER.fullmatch(group) is not None
        folder = _matching_node(root, "folder", group, system_root) if managed else None
        # Acquired catalog titles take precedence; existing readable metadata is the next source.
        title = _readable_title(game.get("title"))
        needs_review = title is None
        for source in (node, folder):
            if title is None and source is not None:
                title = _readable_title(source.findtext("name"))
        if title is None:
            stem = posixpath.splitext(posixpath.basename(launch))[0]
            title = _readable_title(stem) if not GENERIC_FILENAME.fullmatch(stem) else None
            title = title or "Titolo da verificare"
        if needs_review and title_reviews is not None:
            title_reviews.append({"game_id": game.get("game_id"), "launch": launch, "title": title})
        if node is None:
            node = ET.SubElement(root, "game")
        values = {
            "path": relative,
            "name": title,
            "desc": game.get("description"),
            "genre": game.get("genre"),
            "developer": game.get("author"),
            "publisher": game.get("publisher"),
            "releasedate": f"{game['year']:04d}0101T000000" if game.get("year") else None,
            "favorite": ("true" if game["favorite"] else "false") if "favorite" in game else None,
            "image": game.get("image"),
            "thumbnail": game.get("thumbnail"),
        }
        changed = _update(node, values) or changed
        if managed:
            if group in folder_titles and folder_titles[group] != title:
                raise ValueError("Titoli discordanti nella stessa cartella gestita: revisione richiesta")
            folder_titles[group] = title
            if folder is None:
                folder = ET.SubElement(root, "folder")
            # EmulationStation displays a folder's own metadata before entering the game group.
            changed = (
                _update(
                    folder,
                    {
                        "path": "./" + group,
                        "name": title,
                        "desc": game.get("description"),
                        "image": game.get("image"),
                        "thumbnail": game.get("thumbnail"),
                    },
                )
                or changed
            )
    if not changed and existing:
        return existing
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
