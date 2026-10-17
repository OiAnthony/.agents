"""Deterministic data charts: a JSON spec in, a Kami-palette SVG out.

Hand-placing bar heights and arc endpoints is where silent wrong numbers come
from, so the geometry is computed here and nowhere else. Every chart carries
its own spec in `data-kami-spec`; `--check-charts` regenerates each chart from
that spec and fails when the drawn SVG no longer matches it, which catches a
hand-edited label as surely as a stale bar.

Spec (one chart per file):

    {"type": "bar",   "categories": ["2022", "2023"],
                      "series": [{"name": "Revenue", "values": [44, 60]}]}
    {"type": "line",  same shape as bar}
    {"type": "hbar",  "items": [{"label": "A", "value": 31}, ...], "focus": 0}
    {"type": "donut", "items": [{"label": "A", "value": 32}, ...],
                      "center_label": "Share"}
    {"type": "candlestick",
                      "points": [{"label": "D1", "open": 120, "high": 128,
                                  "low": 116, "close": 126}, ...]}
    {"type": "waterfall",
                      "items": [{"label": "Start", "value": 120, "total": true},
                                {"label": "A", "value": 30},
                                {"label": "End", "total": true}]}

Optional on every type: "unit" (axis caption), "prefix" / "suffix" (value
labels), "decimals", "source" (footnote), "lang" ("cn", "en", "ko"; inferred
from the labels when absent), "title" (accessible name only, never drawn;
the document's figure caption carries the takeaway).

Usage:
    python3 scripts/build.py --chart spec.json [-o chart.svg]
    python3 scripts/build.py --check-charts filled.html
"""
from __future__ import annotations

import html
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

PARCHMENT = "#f5f4ed"
NEAR_BLACK = "#141413"
CHARCOAL = "#4d4c48"
OLIVE = "#504e49"
STONE = "#6b6a64"
LIGHT_STONE = "#b8b7b0"
MIST = "#d4d3cd"
BRAND = "#1B365D"
BRAND_TINT = "#EEF2F7"
GRID = "#e8e7e1"

SERIES = (BRAND, OLIVE, STONE, LIGHT_STONE, MIST, BRAND_TINT)

FONT_CN = ("'TsangerJinKai02', 'Source Han Serif SC', 'Source Han Serif CN', "
           "'Noto Serif CJK SC', 'Noto Serif SC', 'Songti SC', 'STSong', 'SimSun', "
           "Charter, Georgia, serif")
FONT_KO = ("'Source Han Serif K', 'Source Han Serif KR', 'Noto Serif KR', "
           "'Nanum Myeongjo', 'AppleMyungjo', Charter, Georgia, serif")
FONT_EN = "Charter, Georgia, Palatino, 'Times New Roman', serif"

WORDS = {
    "en": {"up": "Up (close above open)", "down": "Down (close below open)",
           "increase": "Increase", "decrease": "Decrease", "total": "Total"},
    "cn": {"up": "上涨", "down": "下跌", "increase": "增加", "decrease": "减少", "total": "合计"},
    "ko": {"up": "상승", "down": "하락", "increase": "증가", "decrease": "감소", "total": "합계"},
}

LIMITS = {
    "bar": (8, 3), "line": (12, 3), "hbar": (12, 1),
    "donut": (6, 1), "candlestick": (30, 1), "waterfall": (8, 1),
}

# One layout for every chart, sized for a document column: a 680-unit-wide
# chart set across a ~170mm column lands near 0.7 scale, so 12-unit labels
# print at about 8.5pt, just under body text.
TOP, BASE = 24, 224           # plot area y range
PLOT_H = BASE - TOP
LABEL_Y = BASE + 22           # category labels under the axis
LEGEND_Y = BASE + 44          # hairline above the legend row
FS_TICK, FS_LABEL, FS_VALUE, FS_LEGEND, FS_NOTE = 11, 12, 12, 12, 11


def _width(spec: dict, base: int) -> int:
    """Canvas width. "size": "compact" narrows the canvas, not the type, for a
    chart shown small (a half-column slide, two charts side by side): drawn at
    the same physical width, its labels come out about 1.5 times larger."""
    size = spec.get("size", "full")
    if size not in ("full", "compact"):
        raise ChartError('size must be "full" or "compact"')
    return round(base * 0.65) if size == "compact" else base


def _height(legend: bool, spec: dict) -> int:
    """Chart height: plot, labels, optional legend row, optional source line."""
    height = LEGEND_Y + 32 if legend else LABEL_Y + 16
    src = spec.get("source")
    return height + (22 if isinstance(src, str) and src.strip() else 0)


class ChartError(ValueError):
    pass


# ------------------------------------------------------------------ helpers

def _num(value, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ChartError(f"{where}: expected a number, got {value!r}")
    return float(value)


def _c(v: float) -> str:
    """Coordinate text: one decimal, trailing zero dropped."""
    s = f"{round(v, 1):.1f}"
    s = s[:-2] if s.endswith(".0") else s
    return "0" if s == "-0" else s


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def _wide(ch: str) -> bool:
    return unicodedata.east_asian_width(ch) in ("W", "F")


def text_width(text: str, size: float) -> float:
    return sum(size if _wide(ch) else size * 0.56 for ch in str(text))


def _lang(spec: dict, labels: list[str]) -> str:
    lang = spec.get("lang")
    if lang in WORDS:
        return lang
    if isinstance(lang, str) and lang.lower().startswith("zh"):
        return "cn"
    joined = "".join(labels)
    if re.search(r"[가-힯ᄀ-ᇿ]", joined):
        return "ko"
    if any(_wide(ch) for ch in joined):
        return "cn"
    return "en"


def _font(lang: str) -> str:
    return {"cn": FONT_CN, "ko": FONT_KO}.get(lang, FONT_EN)


def _decimals(spec: dict, values: list[float]) -> int:
    if isinstance(spec.get("decimals"), int):
        return max(0, min(4, spec["decimals"]))
    best = 0
    for v in values:
        text = repr(float(v))
        if "e" in text:
            continue
        frac = text.split(".")[1].rstrip("0")
        best = max(best, len(frac))
    return min(best, 2)


def fmt(value: float, decimals: int, prefix: str = "", suffix: str = "", sign: bool = False) -> str:
    body = f"{abs(value):,.{decimals}f}"
    neg = value < 0 and float(body.replace(",", "")) != 0
    lead = "-" if neg else ("+" if sign and value > 0 else "")
    return f"{lead}{prefix}{body}{suffix}"


def nice_scale(lo: float, hi: float, *, include_zero: bool) -> tuple[float, float, float]:
    """Round [lo, hi] out to a 4-8 tick axis with a 1/2/2.5/5 step."""
    if include_zero:
        lo, hi = min(lo, 0.0), max(hi, 0.0)
    if hi == lo:
        hi = lo + (abs(lo) or 1.0)
    raw = (hi - lo) / 6
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw - 1e-12)
    lo_n = math.floor(lo / step + 1e-9) * step
    hi_n = math.ceil(hi / step - 1e-9) * step
    return lo_n, hi_n, step


class _Svg:
    def __init__(self, spec: dict, kind: str, width: int, height: int, font: str) -> None:
        self.kind, self.width, self.height, self.font = kind, width, height, font
        self.spec = spec
        self.parts: list[str] = []

    def add(self, line: str) -> None:
        self.parts.append(line)

    def text(self, x: float, y: float, value: str, *, size: float = FS_LABEL, fill: str = NEAR_BLACK,
             anchor: str = "start", weight: str | None = None, extra: str = "") -> None:
        attrs = f'x="{_c(x)}" y="{_c(y)}" fill="{fill}" font-size="{size:g}" font-family="{self.font}"'
        if anchor != "start":
            attrs += f' text-anchor="{anchor}"'
        if weight:
            attrs += f' font-weight="{weight}"'
        if extra:
            attrs += f" {extra}"
        self.add(f"<text {attrs}>{_esc(value)}</text>")

    def render(self) -> str:
        canonical = json.dumps(self.spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        title = self.spec.get("title")
        label = f' aria-label="{_esc(title)}"' if isinstance(title, str) and title else ""
        head = (f'<svg viewBox="0 0 {self.width} {self.height}" xmlns="http://www.w3.org/2000/svg" '
                f'role="img"{label} data-kami-chart="{self.kind}" data-kami-spec="{_esc(canonical)}">')
        body = [f'<rect width="100%" height="100%" fill="{PARCHMENT}"/>', *self.parts]
        return head + "\n" + "\n".join(f"  {p}" for p in body) + "\n</svg>\n"


def _step_decimals(step: float) -> int:
    """Tick labels carry the precision of the step, not of the data (0-20 by 5, not 0.0-20.0)."""
    for dec in range(5):
        if abs(step * 10 ** dec - round(step * 10 ** dec)) < 1e-9:
            return dec
    return 4


def _plot_left(lo: float, hi: float, step: float, unit) -> float:
    """Left edge of the plot: tick labels start at the chart's own left edge, so
    the chart lines up with the text column it sits in."""
    dec = _step_decimals(step)
    ticks = [fmt(lo + i * step, dec) for i in range(round((hi - lo) / step) + 1)]
    return (22 if unit else 0) + max(text_width(t, FS_TICK) for t in ticks) + 10


def _axis(svg: _Svg, x0: float, x1: float, lo: float, hi: float, step: float,
          ymap, unit: str | None) -> None:
    decimals = _step_decimals(step)
    ticks = round((hi - lo) / step)
    for i in range(ticks + 1):
        v = lo + i * step
        y = ymap(v)
        svg.add(f'<line x1="{_c(x0)}" y1="{_c(y)}" x2="{_c(x1)}" y2="{_c(y)}" stroke="{GRID}" stroke-width="0.8"/>')
        svg.text(x0 - 8, y + 4, fmt(v, decimals), size=FS_TICK, fill=STONE, anchor="end")
    if unit:
        mid = (TOP + BASE) / 2
        svg.text(8, mid, unit, size=FS_NOTE, fill=STONE, anchor="middle",
                 extra=f'transform="rotate(-90 8 {_c(mid)})"')


def _legend(svg: _Svg, x0: float, x1: float, y: float, entries: list[tuple[str, str]]) -> None:
    """entries: (square swatch markup with {x} {y} slots, label)."""
    svg.add(f'<line x1="{_c(x0)}" y1="{_c(y)}" x2="{_c(x1)}" y2="{_c(y)}" stroke="{GRID}" stroke-width="0.8"/>')
    x = x0
    for swatch, label in entries:
        svg.add(swatch.format(x=_c(x), y=_c(y + 13)))
        tx = x + 18
        svg.text(tx, y + 24, label, size=FS_LEGEND, fill=OLIVE)
        x = tx + text_width(label, FS_LEGEND) + 32


def _source(svg: _Svg, spec: dict, x: float) -> None:
    """The source line sits on the last row _height reserved for it."""
    src = spec.get("source")
    if isinstance(src, str) and src.strip():
        svg.text(x, svg.height - 6, src.strip(), size=FS_NOTE, fill=STONE)


def _square(color: str) -> str:
    stroke = f' stroke="{GRID}" stroke-width="0.8"' if color == BRAND_TINT else ""
    return '<rect x="{x}" y="{y}" width="12" height="12" fill="' + color + '"' + stroke + ' rx="2"/>'


def _common(spec: dict) -> tuple[str, str]:
    prefix = spec.get("prefix", "")
    suffix = spec.get("suffix", "")
    if not isinstance(prefix, str) or not isinstance(suffix, str):
        raise ChartError("prefix and suffix must be strings")
    return prefix, suffix


def _limit(kind: str, count: int, series: int = 1) -> None:
    max_items, max_series = LIMITS[kind]
    if count == 0:
        raise ChartError(f"{kind}: no data")
    if count > max_items:
        hint = " (use hbar for 7+ shares)" if kind == "donut" else ""
        raise ChartError(f"{kind}: {count} items, at most {max_items}{hint}")
    if series > max_series:
        raise ChartError(f"{kind}: {series} series, at most {max_series}")


def _label(item, where: str) -> str:
    if not isinstance(item, str) or not item.strip():
        raise ChartError(f"{where}: label must be a non-empty string")
    return item


# ------------------------------------------------------------- bar / line

def _series_spec(spec: dict, kind: str) -> tuple[list[str], list[tuple[str, list[float]]]]:
    cats = spec.get("categories")
    series = spec.get("series")
    if not isinstance(cats, list) or not isinstance(series, list) or not series:
        raise ChartError(f"{kind}: needs 'categories' and a non-empty 'series' list")
    cats = [_label(c, f"categories[{i}]") for i, c in enumerate(cats)]
    out = []
    for si, s in enumerate(series):
        if not isinstance(s, dict) or not isinstance(s.get("values"), list):
            raise ChartError(f"series[{si}]: needs 'values'")
        vals = [_num(v, f"series[{si}].values[{i}]") for i, v in enumerate(s["values"])]
        if len(vals) != len(cats):
            raise ChartError(f"series[{si}]: {len(vals)} values for {len(cats)} categories")
        name = s.get("name", "")
        out.append((name if isinstance(name, str) else str(name), vals))
    _limit(kind, len(cats), len(out))
    return cats, out


def _bar(spec: dict) -> _Svg:
    cats, series = _series_spec(spec, "bar")
    prefix, suffix = _common(spec)
    allv = [v for _, vals in series for v in vals]
    dec = _decimals(spec, allv)
    lo, hi, step = nice_scale(min(allv), max(allv), include_zero=True)
    legend = len(series) > 1
    lang = _lang(spec, cats + [n for n, _ in series])
    svg = _Svg(spec, "bar", _width(spec, 680), _height(legend, spec), _font(lang))
    x0, x1 = _plot_left(lo, hi, step, spec.get("unit")), svg.width - 4

    def ymap(v: float) -> float:
        return BASE - (v - lo) / (hi - lo) * PLOT_H

    _axis(svg, x0, x1, lo, hi, step, ymap, spec.get("unit"))
    zero = ymap(0)
    svg.add(f'<line x1="{x0}" y1="{_c(zero)}" x2="{x1}" y2="{_c(zero)}" stroke="{NEAR_BLACK}" stroke-width="0.8"/>')
    n, s = len(cats), len(series)
    gw = (x1 - x0) / n
    # One series gets a bar about half its slot; grouped bars stay narrow so
    # the gap between groups still reads as the category break.
    bw = min(56.0, gw * 0.5) if s == 1 else min(32.0, (gw * 0.7 - 8 * (s - 1)) / s)
    total = s * bw + 8 * (s - 1)
    for i, cat in enumerate(cats):
        cx = x0 + gw * (i + 0.5)
        for si, (_, vals) in enumerate(series):
            v = vals[i]
            bx = cx - total / 2 + si * (bw + 8)
            top, bottom = (ymap(v), zero) if v >= 0 else (zero, ymap(v))
            svg.add(f'<rect x="{_c(bx)}" y="{_c(top)}" width="{_c(bw)}" height="{_c(bottom - top)}" '
                    f'fill="{SERIES[si]}" rx="2"/>')
            ly = top - 4 if v >= 0 else bottom + 12
            svg.text(bx + bw / 2, ly, fmt(v, dec, prefix, suffix), size=FS_VALUE, anchor="middle",
                     weight="500" if si == 0 else None)
        svg.text(cx, LABEL_Y, cat, size=FS_LABEL, anchor="middle")
    if legend:
        _legend(svg, x0, x1, LEGEND_Y, [(_square(SERIES[i]), name) for i, (name, _) in enumerate(series)])
    _source(svg, spec, 0)
    return svg


_LINE_STYLES = (
    ("2", "", True), ("1.5", ' stroke-dasharray="5 3"', False), ("1.5", ' stroke-dasharray="2 3"', False),
)


def _line(spec: dict) -> _Svg:
    cats, series = _series_spec(spec, "line")
    prefix, suffix = _common(spec)
    allv = [v for _, vals in series for v in vals]
    dec = _decimals(spec, allv)
    lo, hi, step = nice_scale(min(allv), max(allv), include_zero=min(allv) >= 0 and spec.get("zero", True))
    legend = len(series) > 1
    lang = _lang(spec, cats + [n for n, _ in series])
    svg = _Svg(spec, "line", _width(spec, 680), _height(legend, spec), _font(lang))
    end_w = max(text_width(fmt(vals[-1], dec, prefix, suffix), FS_VALUE) for _, vals in series)
    x0, x1 = _plot_left(lo, hi, step, spec.get("unit")), svg.width - end_w - 12

    def ymap(v: float) -> float:
        return BASE - (v - lo) / (hi - lo) * PLOT_H

    n = len(cats)
    xs = [(x0 + x1) / 2] if n == 1 else [x0 + i * (x1 - x0) / (n - 1) for i in range(n)]
    _axis(svg, x0, x1, lo, hi, step, ymap, spec.get("unit"))
    for x in xs[1:-1]:
        svg.add(f'<line x1="{_c(x)}" y1="{TOP}" x2="{_c(x)}" y2="{BASE}" stroke="{GRID}" '
                f'stroke-width="0.5" stroke-dasharray="3 4"/>')
    svg.add(f'<line x1="{x0}" y1="{BASE}" x2="{x1}" y2="{BASE}" stroke="{NEAR_BLACK}" stroke-width="0.8"/>')
    ends = []
    for si, (_, vals) in enumerate(series):
        width, dash, filled = _LINE_STYLES[si]
        color = SERIES[si]
        pts = " ".join(f"{_c(x)},{_c(ymap(v))}" for x, v in zip(xs, vals))
        svg.add(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}"{dash} '
                f'stroke-linejoin="round" stroke-linecap="round"/>')
        for i, (x, v) in enumerate(zip(xs, vals)):
            y = ymap(v)
            if filled:
                r = "5.5" if i == n - 1 else "4"
                svg.add(f'<circle cx="{_c(x)}" cy="{_c(y)}" r="{r}" fill="{color}" stroke="{PARCHMENT}" stroke-width="1.5"/>')
            else:
                svg.add(f'<circle cx="{_c(x)}" cy="{_c(y)}" r="3.5" fill="{PARCHMENT}" stroke="{color}" stroke-width="1.5"/>')
        ends.append([ymap(vals[-1]) + 4, si, vals[-1]])
    ends.sort()
    for i in range(1, len(ends)):  # keep end labels at least 12px apart
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + 12)
    for y, si, v in ends:
        svg.text(xs[-1] + 8, y, fmt(v, dec, prefix, suffix), size=FS_VALUE,
                 fill=SERIES[si], weight="500" if si == 0 else None)
    for x, cat in zip(xs, cats):
        svg.text(x, LABEL_Y, cat, size=FS_LABEL, anchor="middle")
    if legend:
        _legend_lines(svg, x0, x1, LEGEND_Y, [name for name, _ in series])
    _source(svg, spec, 0)
    return svg


def _legend_lines(svg: _Svg, x0: float, x1: float, y: float, names: list[str]) -> None:
    svg.add(f'<line x1="{_c(x0)}" y1="{_c(y)}" x2="{_c(x1)}" y2="{_c(y)}" stroke="{GRID}" stroke-width="0.8"/>')
    x, cy = x0, y + 18
    for si, name in enumerate(names):
        width, dash, filled = _LINE_STYLES[si]
        color = SERIES[si]
        svg.add(f'<line x1="{_c(x)}" y1="{_c(cy)}" x2="{_c(x + 24)}" y2="{_c(cy)}" stroke="{color}" '
                f'stroke-width="{width}"{dash} stroke-linecap="round"/>')
        if filled:
            svg.add(f'<circle cx="{_c(x + 12)}" cy="{_c(cy)}" r="3.5" fill="{color}"/>')
        else:
            svg.add(f'<circle cx="{_c(x + 12)}" cy="{_c(cy)}" r="3" fill="{PARCHMENT}" stroke="{color}" stroke-width="1.5"/>')
        svg.text(x + 32, cy + 4, name, size=FS_LEGEND, fill=OLIVE)
        x = x + 32 + text_width(name, FS_LEGEND) + 32


# ------------------------------------------------------------------- hbar

def _items(spec: dict, kind: str) -> list[tuple[str, float]]:
    items = spec.get("items")
    if not isinstance(items, list):
        raise ChartError(f"{kind}: needs an 'items' list")
    out = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            raise ChartError(f"items[{i}]: expected an object")
        out.append((_label(it.get("label"), f"items[{i}]"), _num(it.get("value"), f"items[{i}].value")))
    _limit(kind, len(out))
    return out


def _hbar(spec: dict) -> _Svg:
    items = _items(spec, "hbar")
    prefix, suffix = _common(spec)
    if any(v < 0 for _, v in items):
        raise ChartError("hbar: values must be zero or positive")
    dec = _decimals(spec, [v for _, v in items])
    focus = spec.get("focus", 0)
    if focus is not None and (not isinstance(focus, int) or not 0 <= focus < len(items)):
        raise ChartError("hbar: focus must be an item index or null")
    lang = _lang(spec, [l for l, _ in items])
    unit = spec.get("unit") if isinstance(spec.get("unit"), str) and spec.get("unit") else None
    row, bar = 30, 18
    top = 34 if unit else 10
    has_source = isinstance(spec.get("source"), str) and spec["source"].strip()
    height = top + len(items) * row + 6 + (26 if has_source else 0)
    svg = _Svg(spec, "hbar", _width(spec, 680), height, _font(lang))
    label_w = min(200.0, max(text_width(l, FS_LABEL) for l, _ in items))
    x0 = label_w + 14
    vmax = max(v for _, v in items) or 1.0
    labels = [fmt(v, dec, prefix, suffix) for _, v in items]
    span = svg.width - 20 - x0 - max(text_width(t, FS_VALUE) for t in labels) - 10
    if unit:
        svg.text(x0, top - 14, unit, size=FS_NOTE, fill=STONE)
    for i, (label, v) in enumerate(items):
        y = top + i * row
        w = v / vmax * span
        color = BRAND if i == focus else LIGHT_STONE
        svg.text(x0 - 14, y + 14, label, size=FS_LABEL, anchor="end")
        svg.add(f'<rect x="{_c(x0)}" y="{_c(y + 1)}" width="{_c(w)}" height="{bar}" fill="{color}" rx="2"/>')
        svg.text(x0 + w + 8, y + 14, labels[i], size=FS_VALUE, weight="500" if i == focus else None)
    svg.add(f'<line x1="{_c(x0)}" y1="{top - 3}" x2="{_c(x0)}" y2="{_c(top + len(items) * row - 7)}" '
            f'stroke="{NEAR_BLACK}" stroke-width="0.8"/>')
    _source(svg, spec, 0)
    return svg


# ------------------------------------------------------------------ donut

def _shares(values: list[float], decimals: int) -> list[float]:
    """Percentages that sum to exactly 100 at the shown precision (largest remainder)."""
    total = sum(values)
    scale = 10 ** decimals
    raw = [v / total * 100 * scale for v in values]
    floors = [math.floor(r) for r in raw]
    short = round(100 * scale) - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in order[:short]:
        floors[i] += 1
    return [f / scale for f in floors]


def _arc_point(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    rad = math.radians(deg)
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def _donut(spec: dict) -> _Svg:
    """Ring on the left, legend beside it at reading size, one composition."""
    items = _items(spec, "donut")
    if any(v <= 0 for _, v in items):
        raise ChartError("donut: every value must be positive")
    dec = spec["decimals"] if isinstance(spec.get("decimals"), int) else 0
    shares = _shares([v for _, v in items], dec)
    lang = _lang(spec, [l for l, _ in items] + [str(spec.get("center_label", ""))])
    has_source = isinstance(spec.get("source"), str) and spec["source"].strip()
    cx, cy, R, r = 114, 128, 112, 68
    pct = [fmt(s, dec, suffix="%") for s in shares]
    pct_w = max(text_width(p, 14) for p in pct)
    lx = cx + R + 44
    need = lx + 22 + pct_w + 14 + max(text_width(l, FS_LABEL) for l, _ in items) + 8
    width = max(_width(spec, 680), round(need))
    svg = _Svg(spec, "donut", width, 260 + (26 if has_source else 0), _font(lang))
    total = sum(v for _, v in items)
    angle = -90.0
    for i, (_, v) in enumerate(items):
        span = v / total * 360
        color = SERIES[i]
        stroke = f' stroke="{GRID}" stroke-width="0.8"' if color == BRAND_TINT else ""
        if span >= 359.999:
            d = (f"M {_c(cx)} {_c(cy - R)} A {R} {R} 0 1 1 {_c(cx)} {_c(cy + R)} "
                 f"A {R} {R} 0 1 1 {_c(cx)} {_c(cy - R)} M {_c(cx)} {_c(cy - r)} "
                 f"A {r} {r} 0 1 0 {_c(cx)} {_c(cy + r)} A {r} {r} 0 1 0 {_c(cx)} {_c(cy - r)} Z")
            svg.add(f'<path d="{d}" fill="{color}" fill-rule="evenodd"{stroke}/>')
        else:
            end = angle + span
            large = 1 if span > 180 else 0
            ox1, oy1 = _arc_point(cx, cy, R, angle)
            ox2, oy2 = _arc_point(cx, cy, R, end)
            ix2, iy2 = _arc_point(cx, cy, r, end)
            ix1, iy1 = _arc_point(cx, cy, r, angle)
            d = (f"M {_c(ox1)} {_c(oy1)} A {R} {R} 0 {large} 1 {_c(ox2)} {_c(oy2)} "
                 f"L {_c(ix2)} {_c(iy2)} A {r} {r} 0 {large} 0 {_c(ix1)} {_c(iy1)} Z")
            svg.add(f'<path d="{d}" fill="{color}"{stroke}/>')
        angle += span
    svg.add(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{PARCHMENT}" stroke-width="1.5"/>')
    svg.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{PARCHMENT}" stroke-width="1.5"/>')
    center = spec.get("center_label")
    has_center = isinstance(center, str) and center
    svg.text(cx, cy + (-2 if has_center else 10), pct[0], size=30, fill=BRAND, anchor="middle", weight="500")
    if has_center:
        svg.text(cx, cy + 20, center, size=FS_NOTE, fill=STONE, anchor="middle")
    n = len(items)
    rowh = 32
    y0 = cy - n * rowh / 2
    for i, (label, _) in enumerate(items):
        y = y0 + i * rowh
        svg.add(_square(SERIES[i]).format(x=_c(lx), y=_c(y + 10)))
        svg.text(lx + 22, y + 21, pct[i], size=14, fill=BRAND if i == 0 else NEAR_BLACK,
                 weight="500" if i == 0 else None)
        svg.text(lx + 22 + pct_w + 14, y + 21, label, size=FS_LABEL, fill=OLIVE)
    _source(svg, spec, 0)
    return svg


# ------------------------------------------------------------ candlestick

def _candlestick(spec: dict) -> _Svg:
    pts = spec.get("points")
    if not isinstance(pts, list):
        raise ChartError("candlestick: needs a 'points' list")
    rows = []
    for i, p in enumerate(pts):
        if not isinstance(p, dict):
            raise ChartError(f"points[{i}]: expected an object")
        o, h, l, c = (_num(p.get(k), f"points[{i}].{k}") for k in ("open", "high", "low", "close"))
        if h < max(o, c) or l > min(o, c):
            raise ChartError(f"points[{i}]: high {h:g} / low {l:g} do not contain open {o:g} and close {c:g}")
        rows.append((_label(p.get("label"), f"points[{i}]"), o, h, l, c))
    _limit("candlestick", len(rows))
    prefix, suffix = _common(spec)
    dec = _decimals(spec, [v for row in rows for v in row[1:]])
    lo, hi, step = nice_scale(min(r[3] for r in rows), max(r[2] for r in rows), include_zero=False)
    lang = _lang(spec, [r[0] for r in rows])
    words = WORDS[lang]
    svg = _Svg(spec, "candlestick", _width(spec, 760), _height(True, spec), _font(lang))
    x0, x1 = _plot_left(lo, hi, step, spec.get("unit")), svg.width - 4

    def ymap(v: float) -> float:
        return BASE - (v - lo) / (hi - lo) * PLOT_H

    _axis(svg, x0, x1, lo, hi, step, ymap, spec.get("unit"))
    n = len(rows)
    stepx = (x1 - x0) / n
    bw = min(16.0, stepx * 0.5)
    every = max(1, math.ceil(n / 5))
    for i, (label, o, h, l, c) in enumerate(rows):
        cx = x0 + stepx * (i + 0.5)
        color = BRAND if c >= o else STONE
        svg.add(f'<line x1="{_c(cx)}" y1="{_c(ymap(h))}" x2="{_c(cx)}" y2="{_c(ymap(l))}" '
                f'stroke="{color}" stroke-width="1.2"/>')
        top, bottom = ymap(max(o, c)), ymap(min(o, c))
        svg.add(f'<rect x="{_c(cx - bw / 2)}" y="{_c(top)}" width="{_c(bw)}" '
                f'height="{_c(max(1.0, bottom - top))}" fill="{color}" rx="1"/>')
        if i % every == 0 or (i == n - 1 and (n - 1) % every >= every / 2):
            svg.text(cx, LABEL_Y, label, size=FS_TICK, fill=STONE, anchor="middle")
    _legend(svg, x0, x1, LEGEND_Y, [(_square(BRAND), words["up"]), (_square(STONE), words["down"])])
    _source(svg, spec, 0)
    return svg


# -------------------------------------------------------------- waterfall

def _waterfall(spec: dict) -> _Svg:
    items = spec.get("items")
    if not isinstance(items, list):
        raise ChartError("waterfall: needs an 'items' list")
    _limit("waterfall", len(items))
    prefix, suffix = _common(spec)
    rows = []  # (label, kind, value shown, level_before, level_after)
    level = 0.0
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            raise ChartError(f"items[{i}]: expected an object")
        label = _label(it.get("label"), f"items[{i}]")
        if it.get("total"):
            if "value" in it:
                v = _num(it["value"], f"items[{i}].value")
                if i > 0 and abs(v - level) > 1e-9 * max(1.0, abs(level)):
                    raise ChartError(f"items[{i}] '{label}': total {v:g} does not equal the running sum {level:g}")
                level = v
            elif i == 0:
                raise ChartError("items[0]: an opening total needs a value")
            rows.append((label, "total", level, 0.0, level))
        else:
            d = _num(it.get("value"), f"items[{i}].value")
            rows.append((label, "delta", d, level, level + d))
            level += d
    dec = _decimals(spec, [r[2] for r in rows])
    levels = [x for r in rows for x in (r[3], r[4])]
    lo, hi, step = nice_scale(min(levels), max(levels), include_zero=True)
    lang = _lang(spec, [r[0] for r in rows])
    words = WORDS[lang]
    svg = _Svg(spec, "waterfall", _width(spec, 720), _height(True, spec), _font(lang))
    x0, x1 = _plot_left(lo, hi, step, spec.get("unit")), svg.width - 4

    def ymap(v: float) -> float:
        return BASE - (v - lo) / (hi - lo) * PLOT_H

    _axis(svg, x0, x1, lo, hi, step, ymap, spec.get("unit"))
    n = len(rows)
    stepx = (x1 - x0) / n
    bw = min(64.0, stepx * 0.75)
    prev_edge = None
    for i, (label, kind, v, before, after) in enumerate(rows):
        cx = x0 + stepx * (i + 0.5)
        bx = cx - bw / 2
        if prev_edge is not None:
            y = ymap(before if kind == "delta" else after)
            svg.add(f'<line x1="{_c(prev_edge)}" y1="{_c(y)}" x2="{_c(bx)}" y2="{_c(y)}" '
                    f'stroke="{LIGHT_STONE}" stroke-width="0.8" stroke-dasharray="3 2"/>')
        a, b = (0.0, after) if kind == "total" else (before, after)
        top, bottom = ymap(max(a, b)), ymap(min(a, b))
        color = CHARCOAL if kind == "total" else (BRAND if v >= 0 else STONE)
        svg.add(f'<rect x="{_c(bx)}" y="{_c(top)}" width="{_c(bw)}" height="{_c(max(1.0, bottom - top))}" '
                f'fill="{color}" rx="2"/>')
        text = fmt(v, dec, prefix, suffix, sign=kind == "delta")
        ly = bottom + 14 if (kind == "delta" and v < 0) else top - 8
        svg.text(cx, ly, text, size=FS_VALUE, anchor="middle", weight="500")
        svg.text(cx, LABEL_Y, label, size=FS_LABEL, anchor="middle")
        prev_edge = bx + bw
    _legend(svg, x0, x1, LEGEND_Y, [(_square(BRAND), words["increase"]), (_square(STONE), words["decrease"]),
                               (_square(CHARCOAL), words["total"])])
    _source(svg, spec, 0)
    return svg


BUILDERS = {"bar": _bar, "line": _line, "hbar": _hbar, "donut": _donut,
            "candlestick": _candlestick, "waterfall": _waterfall}


def render_chart(spec: dict) -> str:
    if not isinstance(spec, dict):
        raise ChartError("spec must be a JSON object")
    kind = spec.get("type")
    if kind not in BUILDERS:
        raise ChartError(f"type must be one of {', '.join(BUILDERS)}; got {kind!r}")
    return BUILDERS[kind](spec).render()


# ------------------------------------------------------------------ gate

_CHART_RE = re.compile(r"<svg\b[^>]*\bdata-kami-chart=\"[^\"]*\"[^>]*>.*?</svg>", re.S | re.I)
_SPEC_RE = re.compile(r'\bdata-kami-spec="([^"]*)"')
_KIND_RE = re.compile(r'\bdata-kami-chart="([^"]*)"')
_GAPS = re.compile(r">\s+<")


def _inner(svg: str) -> str:
    """Drawn content only: embedding may restyle the root tag, never the marks."""
    body = svg[svg.index(">") + 1: svg.rindex("</svg>")]
    return _GAPS.sub("><", body).strip()


def find_charts(text: str) -> list[str]:
    return _CHART_RE.findall(text)


def compare_chart(svg: str) -> str | None:
    """None when the drawn chart matches its embedded spec, else the reason."""
    m = _SPEC_RE.search(svg[: svg.index(">") + 1])
    if not m:
        return "no data-kami-spec on the chart root"
    try:
        spec = json.loads(html.unescape(m.group(1)))
        expected = render_chart(spec)
    except (json.JSONDecodeError, ChartError) as exc:
        return f"embedded spec is invalid: {exc}"
    want, got = _inner(expected), _inner(svg)
    if want == got:
        return None
    want_parts, got_parts = want.split("><"), got.split("><")
    for i, (a, b) in enumerate(zip(want_parts, got_parts)):
        if a != b:
            at = next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            lo = max(0, at - 24)
            return (f"drawn mark {i} differs from the spec: expected ...{a[lo:at + 24]}..., "
                    f"found ...{b[lo:at + 24]}...")
    return f"{abs(len(want_parts) - len(got_parts))} mark(s) added or removed after generation"


def check_charts(argv: list[str]) -> int:
    files = [a for a in argv if not a.startswith("-")]
    if not files:
        print("ERROR: usage: --check-charts file.html|file.svg ...")
        return 2
    failures = 0
    for name in files:
        path = Path(name)
        if not path.is_file():
            print(f"ERROR: {name}: file not found")
            return 2
        charts = find_charts(path.read_text(encoding="utf-8", errors="replace"))
        if not charts:
            print(f"OK: {name}: no generated charts")
            continue
        for i, svg in enumerate(charts, 1):
            kind = _KIND_RE.search(svg).group(1)
            reason = compare_chart(svg)
            if reason:
                failures += 1
                print(f"ERROR: {name}: chart {i} ({kind}): {reason}; "
                      "fix the spec and regenerate with --chart, never edit the SVG by hand")
            else:
                print(f"OK: {name}: chart {i} ({kind}) matches its data")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    args = list(argv)
    out = None
    if "-o" in args:
        i = args.index("-o")
        if i + 1 >= len(args):
            print("ERROR: -o needs a path")
            return 2
        out = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1 or args[0].startswith("-"):
        print("ERROR: usage: --chart spec.json [-o chart.svg]")
        return 2
    try:
        spec = json.loads(Path(args[0]).read_text(encoding="utf-8"))
        svg = render_chart(spec)
    except FileNotFoundError:
        print(f"ERROR: {args[0]}: file not found")
        return 2
    except json.JSONDecodeError as exc:
        print(f"ERROR: {args[0]}: invalid JSON: {exc}")
        return 2
    except ChartError as exc:
        print(f"ERROR: {exc}")
        return 2
    if out:
        Path(out).write_text(svg, encoding="utf-8")
        print(f"OK: wrote {out} ({spec['type']})")
    else:
        sys.stdout.write(svg)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
