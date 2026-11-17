import posixpath
import xml.etree.ElementTree as ET

from defusedxml.ElementTree import DefusedXMLParser


def parse_xml(content):
    parser = DefusedXMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True), forbid_dtd=True)
    return ET.fromstring(content, parser=parser)


def merge_gamelist(existing: bytes | None, games: list[dict], system_root: str) -> bytes:
    root = parse_xml(existing) if existing else ET.Element("gameList")
    if root.tag != "gameList":
        raise ValueError("Radice XML gamelist non valida")
    changed = False
    for game in games:
        relative = "./" + game["launch"]
        absolute = posixpath.normpath(system_root + "/" + game["launch"])
        matches = [
            g
            for g in root.findall("game")
            if posixpath.normpath(
                (g.findtext("path") or "")
                if (g.findtext("path") or "").startswith("/")
                else system_root + "/" + (g.findtext("path") or "")
            )
            == absolute
        ]
        if len(matches) > 1:
            raise ValueError("Più record XML per lo stesso gioco: revisione richiesta")
        node = matches[0] if matches else ET.SubElement(root, "game")
        values = {
            "path": relative,
            "name": game["title"],
            "desc": game.get("description"),
            "genre": game.get("genre"),
            "developer": game.get("author"),
            "publisher": game.get("publisher"),
            "releasedate": f"{game['year']:04d}0101T000000" if game.get("year") else None,
            "favorite": "true" if game.get("favorite") else "false",
            "image": game.get("image"),
        }
        for tag, value in values.items():
            if value is None or value == "":
                continue  # Missing local metadata never erases a populated remote field.
            if any(ord(c) < 32 and c not in "\t\r\n" for c in str(value)):
                raise ValueError("Caratteri XML non validi nei metadati")
            child = node.find(tag)
            if child is None:
                child = ET.SubElement(node, tag)
            if child.text != str(value):
                child.text = str(value)
                changed = True
    if not changed and existing:
        return existing
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
