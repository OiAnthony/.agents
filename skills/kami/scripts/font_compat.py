"""Hand WeasyPrint TrueType instead of CID-keyed CFF fonts.

WeasyPrint subsets a CID-keyed CFF font (Source Han Serif K, Kami's Korean
serif, ships as such an .otf) into a PDF that Poppler draws but MuPDF and
macOS Quartz, the engine behind Preview, draw blank: the Korean text is in the
PDF and extracts fine, and the page shows only Latin text (production.md
pitfall 25). The same glyphs as TrueType outlines subset cleanly for every
reader, so before each render this rewrites `@font-face` sources that resolve
to a local CID-keyed CFF file to a TrueType copy converted once and cached.

Only sources found on disk are rewritten: a relative or file:// path, or a
remote URL whose file name exists in the skill font directory or the
ensure-fonts download directory. Fonts fontconfig resolves by family name
never pass through `@font-face` and are left alone.
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

CONVERTER_VERSION = "1"

_FONT_FACE = re.compile(r"@font-face\s*\{[^}]*\}", re.I)
_URL = re.compile(r"""url\(\s*(['"]?)([^'")]+?)\1\s*\)""", re.I)
_FORMAT_OPENTYPE = re.compile(r"""(url\([^)]*\)\s*)format\(\s*(['"]?)opentype\2\s*\)""", re.I)


def _cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "kami" / "fonts"


def _font_dirs() -> list[Path]:
    skill_fonts = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    data = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    user_fonts = Path(os.environ.get("KAMI_FONT_DIR") or Path(data) / "fonts" / "kami")
    return [skill_fonts, user_fonts]


def _local_path(url: str, base: Path) -> Path | None:
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        name = Path(unquote(parsed.path)).name
        for folder in _font_dirs():
            if (folder / name).is_file():
                return folder / name
        return None
    if parsed.scheme == "file":
        path = Path(unquote(parsed.path))
    elif parsed.scheme:
        return None
    else:
        path = (base / unquote(url)).resolve()
    return path if path.is_file() else None


def is_cid_cff(path: Path) -> bool:
    if path.suffix.lower() not in (".otf", ".otc", ".ttc"):
        return False
    try:
        with path.open("rb") as fh:
            if fh.read(4) != b"OTTO":
                return False
        from fontTools.ttLib import TTFont
        font = TTFont(str(path), lazy=True)
        if "CFF " not in font:
            return False
        top = font["CFF "].cff.topDictIndex[0]
        return getattr(top, "ROS", None) is not None
    except Exception:
        return False


def _convert(src: Path, dst: Path) -> None:
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import TTFont, newTable

    font = TTFont(str(src))
    order = font.getGlyphOrder()
    glyph_set = font.getGlyphSet()
    glyphs = {}
    for name in order:
        pen = TTGlyphPen(glyph_set)
        glyph_set[name].draw(Cu2QuPen(pen, 1.0, reverse_direction=True))
        glyphs[name] = pen.glyph()
    del font["CFF "]
    for tag in ("VORG",):
        if tag in font:
            del font[tag]
    font["loca"] = newTable("loca")
    glyf = font["glyf"] = newTable("glyf")
    glyf.glyphOrder = order
    glyf.glyphs = glyphs
    maxp = font["maxp"] = newTable("maxp")
    maxp.tableVersion = 0x00010000
    for field in ("maxZones",):
        setattr(maxp, field, 1)
    for field in ("maxTwilightPoints", "maxStorage", "maxFunctionDefs", "maxInstructionDefs",
                  "maxStackElements", "maxSizeOfInstructions", "maxComponentElements"):
        setattr(maxp, field, 0)
    font["head"].glyphDataFormat = 0
    font["post"].formatType = 3.0
    font.sfntVersion = "\x00\x01\x00\x00"
    dst.parent.mkdir(parents=True, exist_ok=True)
    # Write beside the destination and rename, so a concurrent render never
    # reads a half-written font.
    fd, tmp = tempfile.mkstemp(dir=dst.parent, suffix=".ttf.tmp")
    os.close(fd)
    try:
        font.save(tmp)
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def truetype_copy(path: Path) -> Path:
    stat = path.stat()
    key = hashlib.sha256(
        f"{CONVERTER_VERSION}:{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}".encode()
    ).hexdigest()[:16]
    dst = _cache_dir() / f"{path.stem}-{key}.ttf"
    if not dst.is_file():
        _convert(path, dst)
    return dst


def use_truetype_fonts(html: str, base: Path) -> str:
    """Rewrite @font-face sources that point at CID-keyed CFF files."""
    def face(block: re.Match) -> str:
        text = block.group(0)

        def url(m: re.Match) -> str:
            local = _local_path(m.group(2).strip(), base)
            if local is None or not is_cid_cff(local):
                return m.group(0)
            try:
                return f'url("{truetype_copy(local).as_uri()}")'
            except Exception:
                return m.group(0)  # conversion failure keeps the original source

        rewritten = _URL.sub(url, text)
        if rewritten != text:
            # A TrueType file declared as format("opentype") is still accepted,
            # but say what it is.
            rewritten = _FORMAT_OPENTYPE.sub(
                lambda m: m.group(1) + 'format("truetype")' if "kami/fonts" in m.group(1) else m.group(0),
                rewritten)
        return rewritten

    if "@font-face" not in html:
        return html
    return _FONT_FACE.sub(face, html)
