#!/usr/bin/env python3
"""Draft a Kami brand profile from a public website.

Usage:
    python3 scripts/brand_extract.py https://example.com [-o brand.md]

Fetches only the given page plus up to five stylesheets from the same site
(its host or a subdomain), ranks color, font, logo, and name candidates,
maps them onto Kami (one accent, darkened until it reads on parchment),
and prints a draft profile in the format of references/brand.example.md. It never writes to ~/.config: review
the draft, then copy it there yourself. Stdlib only.
"""
from __future__ import annotations

import argparse
import colorsys
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_PROFILE = SKILL_ROOT / "references" / "brand.example.md"

PARCHMENT = "#f5f4ed"
MIN_CONTRAST = 4.5
LIGHTNESS_STEP = 0.02
MAX_STYLESHEETS = 5
PAGE_BYTES = 2_000_000
CSS_BYTES = 1_500_000
TIMEOUT_SECONDS = 10
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

BRAND_VAR = re.compile(r"brand|primary|accent|theme|highlight|main", re.I)
CUSTOM_PROP = re.compile(r"(--[\w-]+)\s*:\s*([^;}{]+)")
HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b")
FUNC = re.compile(r"\b(rgba?|hsla?)\(\s*([^)]*)\)", re.I)
FONT_FAMILY = re.compile(r"font-family\s*:\s*([^;}{]+)", re.I)
FONT_FACE = re.compile(r"@font-face\s*\{([^}]*)\}", re.I | re.S)
REGION = re.compile(r"<(header|nav)\b.*?</\1\s*>", re.I | re.S)
SVG = re.compile(r"<svg\b([^>]*)>", re.I)
ANCHOR_WITH_SVG = re.compile(r"<a\b([^>]*)>\s*(?:<[^>]+>\s*)*?<svg\b", re.I | re.S)
GENERIC_FONTS = {
    "serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui",
    "ui-sans-serif", "ui-serif", "ui-monospace", "ui-rounded", "inherit",
    "initial", "unset", "-apple-system", "blinkmacsystemfont", "emoji", "math",
    "apple color emoji", "segoe ui emoji", "segoe ui symbol", "noto color emoji",
}


class BrandFetchError(RuntimeError):
    """The page could not be fetched; reported as one ERROR line."""


# ---------------------------------------------------------------- color math

def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) in (3, 4):
        value = "".join(ch * 2 for ch in value[:3])
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def relative_luminance(color: str) -> float:
    """WCAG 2.x relative luminance with sRGB gamma expansion per channel."""
    def channel(c8: int) -> float:
        c = c8 / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in _hex_to_rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
    a, b = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def ensure_contrast(color: str, bg: str = PARCHMENT, target: float = MIN_CONTRAST) -> tuple[str, int]:
    """Darken in HSL lightness steps until `color` reaches `target` on `bg`.

    Returns (color, steps); steps is 0 when the input already passes.
    """
    r, g, b = (c / 255 for c in _hex_to_rgb(color))
    h, lightness, s = colorsys.rgb_to_hls(r, g, b)
    current, steps = _rgb_to_hex((r * 255, g * 255, b * 255)), 0
    while contrast_ratio(current, bg) < target and lightness > 0:
        lightness = max(0.0, lightness - LIGHTNESS_STEP)
        steps += 1
        current = _rgb_to_hex(tuple(c * 255 for c in colorsys.hls_to_rgb(h, lightness, s)))
    return current, steps


def _parse_color(token: str) -> str | None:
    """Normalize a hex / rgb() / hsl() literal to #rrggbb, or None."""
    token = token.strip()
    if token.startswith("#"):
        digits = token[1:]
        if len(digits) in (4, 8):
            alpha = int(digits[3], 16) / 15 if len(digits) == 4 else int(digits[6:], 16) / 255
            if alpha < 0.5:
                return None  # mostly transparent
        return _rgb_to_hex(_hex_to_rgb(token))
    match = FUNC.fullmatch(token) or FUNC.search(token)
    if not match:
        return None
    kind = match.group(1).lower()
    parts = [p for p in re.split(r"[\s,/]+", match.group(2).strip()) if p]
    if len(parts) < 3 or any(p.startswith("var(") for p in parts):
        return None
    try:
        if len(parts) > 3:
            alpha = float(parts[3].rstrip("%")) / (100 if parts[3].endswith("%") else 1)
            if alpha < 0.5:
                return None
        if kind.startswith("rgb"):
            rgb = [float(p.rstrip("%")) * (2.55 if p.endswith("%") else 1) for p in parts[:3]]
            return _rgb_to_hex(tuple(rgb))  # type: ignore[arg-type]
        hue = float(re.sub(r"deg$", "", parts[0]))
        sat = float(parts[1].rstrip("%")) / 100
        lig = float(parts[2].rstrip("%")) / 100
        return _rgb_to_hex(tuple(c * 255 for c in colorsys.hls_to_rgb(hue / 360 % 1, lig, sat)))
    except ValueError:
        return None


def _is_brand_candidate(color: str) -> bool:
    """Drop near-white, near-black, and greys: a brand accent has hue."""
    r, g, b = (c / 255 for c in _hex_to_rgb(color))
    _, lightness, sat = colorsys.rgb_to_hls(r, g, b)
    return sat >= 0.25 and 0.12 <= lightness <= 0.85


def _colors_in(text: str) -> list[str]:
    found = [m.group(0) for m in HEX.finditer(text)]
    found += [m.group(0) for m in FUNC.finditer(text)]
    return [c for c in (_parse_color(t) for t in found) if c]


# ---------------------------------------------------------------- HTML scan

class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._in_style = False
        self.meta: dict[str, str] = {}
        self.stylesheets: list[str] = []
        self.styles: list[str] = []
        self.inline_styles: list[str] = []
        self.touch_icons: list[str] = []
        self.logo_imgs: list[str] = []

    def handle_starttag(self, tag: str, attrs_list) -> None:
        attrs = {k.lower(): (v or "") for k, v in attrs_list}
        if attrs.get("style"):
            self.inline_styles.append(attrs["style"])
        if tag == "title":
            self._in_title = True
        elif tag == "style":
            self._in_style = True
        elif tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            if key and attrs.get("content"):
                self.meta.setdefault(key, attrs["content"].strip())
        elif tag == "link":
            rel = attrs.get("rel", "").lower().split()
            href = attrs.get("href", "")
            if "stylesheet" in rel and href:
                self.stylesheets.append(href)
            if "apple-touch-icon" in rel and href:
                self.touch_icons.append(href)
        elif tag == "img":
            haystack = " ".join(attrs.get(k, "") for k in ("src", "alt", "class", "id")).lower()
            if "logo" in haystack and attrs.get("src"):
                self.logo_imgs.append(attrs["src"])

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "style":
            self._in_style = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif self._in_style:
            self.styles.append(data)


def _inline_svg_logos(html: str) -> list[str]:
    """Describe inline <svg> logos inside header/nav, by the attribute that marks them."""
    found: list[str] = []
    for region in REGION.finditer(html):
        block, where = region.group(0), region.group(1).lower()
        for attrs in (m.group(1) for m in SVG.finditer(block)):
            if "logo" in attrs.lower():
                found.append(f"inline <svg> in <{where}> ({_short_attrs(attrs)})")
        for attrs in (m.group(1) for m in ANCHOR_WITH_SVG.finditer(block)):
            lower = attrs.lower()
            if "logo" in lower or "home" in lower:
                found.append(f"inline <svg> in <{where}> link ({_short_attrs(attrs)})")
    return list(dict.fromkeys(found))


def _short_attrs(attrs: str) -> str:
    pairs = re.findall(r'(class|id|aria-label|href)\s*=\s*"([^"]*)"', attrs, re.I)
    return ", ".join(f'{k}="{v[:40]}"' for k, v in pairs) or attrs.strip()[:60]


def _site_name(parser: _PageParser, host: str) -> str:
    for key in ("og:site_name", "application-name", "apple-mobile-web-app-title"):
        if parser.meta.get(key):
            return parser.meta[key]
    title = re.sub(r"\s+", " ", parser.title).strip()
    if title:
        parts = [p.strip() for p in re.split(r"\s[|\u2013\u2014\-\u00b7:]\s", title) if p.strip()]
        return parts[0] if parts else title
    return host


def _rank_fonts(css: str) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for block in FONT_FACE.findall(css):
        for m in FONT_FAMILY.finditer(block):
            counts[_clean_font(m.group(1).split(",")[0])] += 2
    declarations = [m.group(1) for m in FONT_FAMILY.finditer(FONT_FACE.sub("", css))]
    declarations += [
        v for n, v in CUSTOM_PROP.findall(css)
        if re.search(r"font|family", n, re.I) and ("," in v or '"' in v or "'" in v)
    ]
    for declaration in declarations:
        for family in declaration.split(","):
            name = _clean_font(family)
            if re.match(r"[A-Za-z][\w .-]*$", name or ""):
                counts[name] += 1
                break
    return [(f, n) for f, n in counts.most_common() if f and f.lower() not in GENERIC_FONTS]


def _clean_font(raw: str) -> str:
    return raw.strip().strip("'\"").strip().replace("!important", "").strip()


def extract(html: str, css_texts: list[str], base_url: str = "") -> dict:
    """Pure parse step: rank brand candidates from page HTML and stylesheet text."""
    parser = _PageParser()
    parser.feed(html)
    parser.close()
    css = "\n".join([*parser.styles, *css_texts])

    scores: Counter[str] = Counter()
    for color in _colors_in(css):
        scores[color] += 1
    # Inline style attributes mostly paint demo content (labels, charts) in the
    # page body, so they only break ties and never earn the brand-name bonus.
    for color in _colors_in(";".join(parser.inline_styles)):
        scores[color] += 0.25
    for name, value in CUSTOM_PROP.findall(css):
        if BRAND_VAR.search(name):
            for color in _colors_in(value):
                scores[color] += 5
    for key in ("theme-color", "msapplication-tilecolor"):
        if parser.meta.get(key):
            color = _parse_color(parser.meta[key])
            if color:
                scores[color] += 8
    colors = [(c, n) for c, n in scores.most_common() if _is_brand_candidate(c)]

    def absolute(href: str) -> str:
        return urllib.parse.urljoin(base_url, href) if base_url else href

    logos = _inline_svg_logos(html)
    logos += [absolute(src) for src in parser.logo_imgs]
    logos += [absolute(href) for href in parser.touch_icons]
    if not logos and parser.meta.get("og:image"):
        logos.append(absolute(parser.meta["og:image"]))

    host = urllib.parse.urlparse(base_url).hostname or ""
    return {
        "name": _site_name(parser, host),
        "host": host.removeprefix("www."),
        "colors": colors,
        "fonts": _rank_fonts(css),
        "logos": list(dict.fromkeys(logos)),
        "stylesheets": [absolute(h) for h in parser.stylesheets],
    }


# ---------------------------------------------------------------- fetch

def _fetch(url: str, cap: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read(cap + 1)[:cap]
        charset = response.headers.get_content_charset() if hasattr(response, "headers") else None
    return body.decode(charset or "utf-8", errors="replace")


def _same_site(page: str, href: str) -> bool:
    """Same scheme, and the stylesheet host is the page host or one of its subdomains.

    Sites often serve CSS from a static subdomain (static.example.com); a CDN on
    another domain is skipped so the scan stays on the site the user named.
    """
    a, b = urllib.parse.urlparse(page), urllib.parse.urlparse(href)
    if a.scheme != b.scheme:
        return False
    host, other = (a.hostname or ""), (b.hostname or "")
    root = host.removeprefix("www.")
    return other == host or other == root or other.endswith("." + root)


def fetch_site(url: str) -> tuple[dict, int, int]:
    """Fetch the page and up to MAX_STYLESHEETS same-site stylesheets.

    Returns (extract result, stylesheets read, stylesheets skipped).
    """
    try:
        html = _fetch(url, PAGE_BYTES)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", None) or exc
        raise BrandFetchError(f"could not fetch {url}: {reason}") from exc
    first = extract(html, [], url)
    same_site = [h for h in first["stylesheets"] if _same_site(url, h)]
    css_texts: list[str] = []
    for href in same_site[:MAX_STYLESHEETS]:
        try:
            css_texts.append(_fetch(href, CSS_BYTES))
        except (urllib.error.URLError, OSError, ValueError):
            continue
    skipped = len(first["stylesheets"]) - len(css_texts)
    return extract(html, css_texts, url), len(css_texts), skipped


# ---------------------------------------------------------------- profile

def _set_field(text: str, field: str, value: str) -> str:
    """Fill `field: ""` in the example frontmatter, keeping its comment column."""
    pattern = re.compile(rf'^({field}:\s*)""(\s*)(#.*)?$', re.M)

    def repl(m: re.Match) -> str:
        quoted = '"' + value.replace('"', "'") + '"'
        pad = max(1, 2 + len(m.group(2)) - len(quoted))  # keep the comment column
        return f"{m.group(1)}{quoted}{' ' * pad}{m.group(3) or ''}".rstrip()

    return pattern.sub(repl, text, count=1)


def build_profile(result: dict, url: str) -> str:
    template = EXAMPLE_PROFILE.read_text(encoding="utf-8")
    head, _, _ = template.partition("Examples to replace with your own:")
    head = head.replace(
        "# Then edit the values below.",
        "# Then edit the values below.\n#\n"
        f"# Draft generated by scripts/brand_extract.py from {url}.\n"
        "# Review every value before copying it into place.",
        1,
    )
    notes: list[str] = []
    if result["name"]:
        head = _set_field(head, "company", result["name"])
    if result["host"]:
        head = _set_field(head, "website", result["host"])

    if result["colors"]:
        source = result["colors"][0][0]
        accent, steps = ensure_contrast(source)
        head = _set_field(head, "brand_color", accent.upper())
        ratio = contrast_ratio(accent, PARCHMENT)
        if steps:
            notes.append(
                f"Brand color: the site accent {source.upper()} reads at "
                f"{contrast_ratio(source, PARCHMENT):.2f}:1 on Kami parchment {PARCHMENT}, below "
                f"{MIN_CONTRAST}:1, so it was darkened {steps} HSL lightness step(s) to "
                f"{accent.upper()} ({ratio:.2f}:1)."
            )
        else:
            notes.append(
                f"Brand color: {accent.upper()} taken from the site as is, "
                f"{ratio:.2f}:1 on Kami parchment {PARCHMENT}."
            )
        if result["colors"][0][1] < 1:
            notes.append(
                "Low confidence: no saturated color was found in the stylesheets read, "
                "so this pick comes from inline styles in the page body."
            )
        others = ", ".join(c.upper() for c, _ in result["colors"][1:5])
        if others:
            notes.append(
                f"Kami uses one accent only. Other site colors, not applied: {others}."
            )
    else:
        notes.append("Brand color: no saturated color found on the page; Kami ink blue stays.")

    if result["fonts"]:
        names = ", ".join(f for f, _ in result["fonts"][:4])
        notes.append(
            f"Site fonts: {names}. A habit note only; Kami keeps its own serif stacks."
        )
    if result["logos"]:
        notes.append(
            "Logo candidates (download one and set `logo:` to its local path): "
            + "; ".join(result["logos"][:4]) + "."
        )

    body = "Draft notes from the site scan:\n\n" + "\n".join(f"- {n}" for n in notes) + "\n"
    return head + body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Draft a Kami brand profile from a website.")
    parser.add_argument("url", help="page to scan, e.g. https://example.com")
    parser.add_argument("-o", "--output", type=Path, help="write the draft here instead of stdout")
    args = parser.parse_args(argv)

    url = args.url if "://" in args.url else f"https://{args.url}"
    try:
        result, read, skipped = fetch_site(url)
    except BrandFetchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    profile = build_profile(result, url)
    if args.output:
        args.output.write_text(profile, encoding="utf-8")
        print(
            f"OK: wrote draft brand profile to {args.output} "
            f"({read} stylesheet(s) read, {skipped} skipped)"
        )
    else:
        sys.stdout.write(profile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
