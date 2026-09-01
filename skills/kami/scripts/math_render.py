#!/usr/bin/env python3
r"""Strict standard-delimiter TeX rendering for Kami HTML documents.

Author formulas as \( inline \) or \[ display \] in HTML text nodes.
The renderer replaces them with self-contained MathJax SVG and fails closed
when delimiters, TeX, the locked runtime, or the renderer output is invalid.

CLI:
  python3 scripts/math_render.py --in-place filled.html
  python3 scripts/math_render.py --check filled.html
"""
from __future__ import annotations

import argparse
import functools
import html
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
NODE_RENDERER = SCRIPT_DIR / "mathjax_svg.js"
IGNORED_TAGS = frozenset(
    {
        "code", "datalist", "iframe", "kbd", "math", "mjx-container",
        "noembed", "noscript", "option", "plaintext", "pre", "samp", "script",
        "select", "style", "svg", "template", "textarea", "title", "xmp",
    }
)
FOREIGN_SELF_CLOSING_TAGS = frozenset({"math", "svg"})
MAX_FORMULAS = 500
MAX_FORMULA_CHARS = 10 * 1024
MAX_TOTAL_TEX_CHARS = 100 * 1024
MAX_RENDER_OUTPUT_BYTES = 24 * 1024 * 1024
NODE_TIMEOUT_SECONDS = 30
ENTITY_RE = re.compile(
    r"&(?:#[xX][0-9A-Fa-f]+;?|#[0-9]+;?|[A-Za-z][A-Za-z0-9]+;?)"
)
UNSAFE_SVG_ELEMENTS = frozenset(
    {"a", "embed", "foreignobject", "iframe", "object", "script"}
)


class MathRenderError(RuntimeError):
    """Raised when math source or renderer output is invalid."""


class MathJaxUnavailable(MathRenderError):
    """Raised when the locked Node.js MathJax runtime is unavailable."""


@dataclass(frozen=True)
class LatexSpan:
    start: int
    end: int
    tex: str
    display: bool


class _TextRangeParser(HTMLParser):
    """Collect exact raw text-node ranges while excluding literal/code regions."""

    def __init__(self, raw: str):
        super().__init__(convert_charrefs=False)
        self.raw = raw
        self.ranges: list[tuple[int, int]] = []
        self.issues: list[str] = []
        self.legacy_placeholders = 0
        self._active_start: int | None = None
        self._ignored_stack: list[str] = []
        self._line_offsets = [0]
        for line in raw.splitlines(keepends=True):
            self._line_offsets.append(self._line_offsets[-1] + len(line))

    def _offset(self) -> int:
        line, column = self.getpos()
        return self._line_offsets[line - 1] + column

    def _start_text(self) -> None:
        if not self._ignored_stack and self._active_start is None:
            self._active_start = self._offset()

    def _finish_text(self, end: int) -> None:
        if self._active_start is not None and end > self._active_start:
            self.ranges.append((self._active_start, end))
        self._active_start = None

    def handle_data(self, _data: str) -> None:
        self._start_text()

    def handle_entityref(self, _name: str) -> None:
        self._start_text()

    def handle_charref(self, _name: str) -> None:
        self._start_text()

    def _check_legacy_class(self, attrs) -> None:
        if self._ignored_stack:
            return
        for name, value in attrs:
            if name.lower() != "class" or not value:
                continue
            tokens = {token.casefold() for token in value.split()}
            if tokens & {"latex-inline", "latex-display"}:
                self.legacy_placeholders += 1

    def handle_starttag(self, tag: str, attrs) -> None:
        self._finish_text(self._offset())
        tag = tag.lower()
        # HTML permits an option end tag to be omitted before a following
        # option or optgroup. Mirror that tree-builder rule so ordinary form
        # markup does not make strict document rendering fail.
        if self._ignored_stack and self._ignored_stack[-1] == "option":
            if tag in {"option", "optgroup"}:
                self._ignored_stack.pop()
        if tag not in IGNORED_TAGS:
            self._check_legacy_class(attrs)
        if tag in IGNORED_TAGS:
            self._ignored_stack.append(tag)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self._finish_text(self._offset())
        tag = tag.lower()
        if tag not in IGNORED_TAGS:
            self._check_legacy_class(attrs)
        if tag in IGNORED_TAGS and tag not in FOREIGN_SELF_CLOSING_TAGS:
            self.issues.append(
                f"self-closing <{tag}/> is ambiguous for formula scanning"
            )

    def handle_endtag(self, tag: str) -> None:
        self._finish_text(self._offset())
        tag = tag.lower()
        # The option end tag may also be omitted before the parent select or
        # datalist closes, and before an optgroup closes.
        if self._ignored_stack and self._ignored_stack[-1] == "option":
            if tag in {"datalist", "optgroup", "select"}:
                self._ignored_stack.pop()
        if tag not in IGNORED_TAGS or not self._ignored_stack:
            return
        if tag == self._ignored_stack[-1]:
            self._ignored_stack.pop()
            return
        self.issues.append(
            f"mismatched ignored HTML closing tag </{tag}> inside "
            f"<{self._ignored_stack[-1]}>"
        )

    def handle_comment(self, _data: str) -> None:
        self._finish_text(self._offset())

    def handle_decl(self, _decl: str) -> None:
        self._finish_text(self._offset())

    def handle_pi(self, _data: str) -> None:
        self._finish_text(self._offset())

    def finish(self) -> list[tuple[int, int]]:
        self._finish_text(len(self.raw))
        if self._ignored_stack:
            self.issues.append(
                "unclosed ignored HTML tag(s): "
                + ", ".join(f"<{tag}>" for tag in self._ignored_stack)
            )
        return self.ranges


class _SvgSafetyParser(HTMLParser):
    """Inspect MathJax's HTML-serialized SVG without substring false positives."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.root_name: str | None = None
        self.root_count = 0
        self.saw_svg = False
        self.unsafe = False
        self.malformed = False
        self._stack: list[str] = []

    def _inspect(self, tag: str, attrs) -> None:
        name = tag.casefold()
        if self.root_name is None:
            self.root_name = name
        self.saw_svg = self.saw_svg or name == "svg"
        self.unsafe = self.unsafe or name in UNSAFE_SVG_ELEMENTS
        for raw_name, value in attrs:
            attribute = raw_name.rsplit(":", 1)[-1].casefold()
            if attribute in {"href", "src"} or attribute.startswith("on"):
                self.unsafe = True
            if attribute == "style" and value and re.search(
                r"(?:javascript\s*:|url\s*\()", value, re.IGNORECASE
            ):
                self.unsafe = True

    def handle_starttag(self, tag: str, attrs) -> None:
        if not self._stack:
            self.root_count += 1
        self._inspect(tag, attrs)
        self._stack.append(tag.casefold())

    def handle_startendtag(self, tag: str, attrs) -> None:
        if not self._stack:
            self.root_count += 1
        self._inspect(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        name = tag.casefold()
        if not self._stack or self._stack[-1] != name:
            self.malformed = True
            return
        self._stack.pop()

    def handle_data(self, data: str) -> None:
        if not self._stack and data.strip():
            self.malformed = True

    def handle_decl(self, _decl: str) -> None:
        self.unsafe = True

    def handle_pi(self, _data: str) -> None:
        self.unsafe = True


def _next_delimiter(
    text: str,
    start: int,
    accepted: str,
) -> tuple[int, str, int] | None:
    """Return (delimiter backslash, marker, index after marker) in linear time."""
    cursor = start
    while cursor < len(text):
        slash = text.find("\\", cursor)
        if slash < 0:
            return None
        run_end = slash + 1
        while run_end < len(text) and text[run_end] == "\\":
            run_end += 1
        run_length = run_end - slash
        if (
            run_length % 2 == 1
            and run_end < len(text)
            and text[run_end] in accepted
        ):
            return run_end - 1, text[run_end], run_end + 1
        cursor = run_end
    return None


def _raw_boundary_offsets(
    text: str,
    decoded: str,
    requested: set[int],
) -> dict[int, int]:
    """Map only requested decoded boundaries back to raw HTML offsets."""
    if not requested:
        return {}
    if "&" not in text:
        return {boundary: boundary for boundary in requested}

    targets = iter(sorted(requested))
    target = next(targets, None)
    offsets: dict[int, int] = {}
    raw_cursor = 0
    decoded_cursor = 0
    for match in ENTITY_RE.finditer(text):
        plain_length = match.start() - raw_cursor
        plain_end = decoded_cursor + plain_length
        while target is not None and target <= plain_end:
            offsets[target] = raw_cursor + (target - decoded_cursor)
            target = next(targets, None)
        decoded_cursor = plain_end

        token = match.group(0)
        value = html.unescape(token)
        if value == token:
            entity_length = len(token)
            entity_end = decoded_cursor + entity_length
            while target is not None and target <= entity_end:
                offsets[target] = match.start() + (target - decoded_cursor)
                target = next(targets, None)
        else:
            entity_length = len(value)
            entity_end = decoded_cursor + entity_length
            while target is not None and target <= entity_end:
                offsets[target] = (
                    match.end() if target == entity_end else match.start()
                )
                target = next(targets, None)
        decoded_cursor = entity_end
        raw_cursor = match.end()

    plain_length = len(text) - raw_cursor
    plain_end = decoded_cursor + plain_length
    while target is not None and target <= plain_end:
        offsets[target] = raw_cursor + (target - decoded_cursor)
        target = next(targets, None)
    if target is not None or plain_end != len(decoded):
        raise MathRenderError("HTML entity mapping is ambiguous in a formula text node")
    return offsets


def _preflight_text_range(
    text: str,
    formula_budget: int,
    tex_budget: int,
) -> str | None:
    """Reject formula-count and source-size excess before allocating span maps."""
    decoded = html.unescape(text)
    formulas = 0
    tex_chars = 0
    cursor = 0
    saw_delimiter = False
    while delimiter := _next_delimiter(decoded, cursor, "([)]"):
        saw_delimiter = True
        _delimiter_start, marker, content_start = delimiter
        if marker in ")]":
            cursor = content_start
            continue
        closing = "]" if marker == "[" else ")"
        closing_delimiter = _next_delimiter(decoded, content_start, closing)
        if closing_delimiter is None:
            return decoded
        closing_start, _closing_marker, after_closing = closing_delimiter
        formula_chars = closing_start - content_start
        formulas += 1
        if formulas > formula_budget:
            raise MathRenderError(
                f"more than {MAX_FORMULAS} formulas exceed the formula safety limit"
            )
        if formula_chars > MAX_FORMULA_CHARS:
            raise MathRenderError(
                f"formula exceeds the {MAX_FORMULA_CHARS}-character safety limit"
            )
        tex_chars += formula_chars
        if tex_chars > tex_budget:
            raise MathRenderError(
                f"formula source exceeds the {MAX_TOTAL_TEX_CHARS}-character safety limit"
            )
        cursor = after_closing
    return decoded if saw_delimiter else None


def _scan_text_range(
    text: str,
    absolute_start: int,
    formula_budget: int,
    tex_budget: int,
) -> tuple[list[LatexSpan], list[str], int]:
    decoded = _preflight_text_range(text, formula_budget, tex_budget)
    if decoded is None:
        return [], [], 0
    decoded_spans: list[tuple[int, int, str, bool]] = []
    issue_records: list[tuple[str, int]] = []
    delimiter_events = 0
    tex_chars = 0
    cursor = 0
    while delimiter := _next_delimiter(decoded, cursor, "([)]"):
        delimiter_start, marker, content_start = delimiter
        delimiter_events += 1
        if delimiter_events > formula_budget:
            raise MathRenderError(
                f"more than {MAX_FORMULAS} TeX delimiters exceed the safety limit"
            )
        if marker in ")]":
            mode = "inline" if marker == ")" else "display"
            issue_records.append(
                (f"unmatched {mode} TeX closing delimiter", delimiter_start)
            )
            cursor = content_start
            continue
        display = marker == "["
        closing = "]" if display else ")"
        closing_delimiter = _next_delimiter(decoded, content_start, closing)
        if closing_delimiter is None:
            mode = "display" if display else "inline"
            issue_records.append(
                (f"unclosed {mode} TeX delimiter", delimiter_start)
            )
            break
        closing_start, _closing_marker, after_closing = closing_delimiter
        tex = decoded[content_start:closing_start]
        if not tex.strip():
            issue_records.append(
                (
                    f"empty {'display' if display else 'inline'} TeX formula",
                    delimiter_start,
                )
            )
        if len(tex) > MAX_FORMULA_CHARS:
            raise MathRenderError(
                f"formula exceeds the {MAX_FORMULA_CHARS}-character safety limit"
            )
        tex_chars += len(tex)
        if tex_chars > tex_budget:
            raise MathRenderError(
                f"formula source exceeds the {MAX_TOTAL_TEX_CHARS}-character safety limit"
            )
        decoded_spans.append((delimiter_start, after_closing, tex, display))
        cursor = after_closing
    requested = {
        boundary
        for start, end, _tex, _display in decoded_spans
        for boundary in (start, end)
    }
    requested.update(position for _message, position in issue_records)
    raw_offsets = _raw_boundary_offsets(text, decoded, requested)
    spans = [
        LatexSpan(
            absolute_start + raw_offsets[start],
            absolute_start + raw_offsets[end],
            tex,
            display,
        )
        for start, end, tex, display in decoded_spans
    ]
    issues = [
        f"{message} at character {absolute_start + raw_offsets[position] + 1}"
        for message, position in issue_records
    ]
    return spans, issues, delimiter_events


def _latex_spans(raw: str) -> tuple[list[LatexSpan], list[str]]:
    parser = _TextRangeParser(raw)
    try:
        parser.feed(raw)
        parser.close()
    except Exception as exc:
        raise MathRenderError(f"could not parse HTML text nodes: {exc}") from exc

    ranges = parser.finish()
    spans: list[LatexSpan] = []
    issues: list[str] = list(parser.issues)
    delimiter_events = 0
    total_tex_chars = 0
    for start, end in ranges:
        found, range_issues, range_events = _scan_text_range(
            raw[start:end],
            start,
            MAX_FORMULAS - delimiter_events,
            MAX_TOTAL_TEX_CHARS - total_tex_chars,
        )
        spans.extend(found)
        delimiter_events += range_events
        total_tex_chars += sum(len(span.tex) for span in found)
        issues.extend(range_issues)
    if parser.legacy_placeholders:
        issues.append(
            f"{parser.legacy_placeholders} legacy LaTeX placeholder(s) remain"
        )
    return spans, issues


def _node_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NODE_OPTIONS", None)
    return environment


@functools.lru_cache(maxsize=4)
def _validated_node(node: str) -> str:
    """Reject Node releases outside the locked runtime's engine contract."""
    try:
        result = subprocess.run(
            [node, "-p", 'process.versions.node.split(".")[0]'],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
            env=_node_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MathJaxUnavailable(f"could not inspect Node.js: {exc}") from exc
    try:
        major = int(result.stdout.strip())
    except ValueError as exc:
        detail = result.stderr.strip() or result.stdout.strip() or "no version output"
        raise MathJaxUnavailable(
            f"could not inspect Node.js version: {detail[:500]}"
        ) from exc
    if result.returncode or major < 20 or major == 21:
        raise MathJaxUnavailable(
            "strict LaTeX rendering requires Node.js 20 or Node.js 22+"
        )
    return node


def _node_command(*args: str) -> list[str]:
    node = shutil.which("node")
    if not node:
        raise MathJaxUnavailable(
            "Node.js is unavailable; install Node.js, then run "
            "'bash scripts/ensure_mathjax.sh'."
        )
    if not NODE_RENDERER.is_file():
        raise MathJaxUnavailable(f"MathJax renderer missing: {NODE_RENDERER}")
    return [
        _validated_node(node),
        "--max-old-space-size=256",
        str(NODE_RENDERER),
        *args,
    ]


def probe_mathjax() -> dict:
    """Return the locked runtime's availability without installing anything."""
    try:
        command = _node_command("--probe")
    except MathJaxUnavailable as exc:
        return {"status": "missing", "version": None, "detail": str(exc)}
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=5,
            check=False,
            env=_node_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "status": "degraded",
            "version": None,
            "detail": f"MathJax probe failed: {type(exc).__name__}: {exc}",
        }
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        return {
            "status": "missing",
            "version": None,
            "detail": (
                "locked MathJax runtime unavailable; run "
                "'bash scripts/ensure_mathjax.sh'. "
                + (detail[:1000] or "probe process failed")
            ),
        }
    try:
        payload = json.loads(result.stdout.decode("utf-8"))
        version = payload["version"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        return {
            "status": "degraded",
            "version": None,
            "detail": f"invalid MathJax probe output: {exc}",
        }
    return {"status": "available", "version": str(version)}


def _render_svg(formulas: list[dict]) -> list[str]:
    payload = json.dumps(formulas, ensure_ascii=False).encode("utf-8")
    try:
        result = subprocess.run(
            _node_command(),
            input=payload,
            capture_output=True,
            timeout=NODE_TIMEOUT_SECONDS,
            check=False,
            env=_node_environment(),
        )
    except subprocess.TimeoutExpired as exc:
        raise MathRenderError(
            f"MathJax exceeded the {NODE_TIMEOUT_SECONDS}-second safety timeout"
        ) from exc
    except OSError as exc:
        raise MathJaxUnavailable(f"could not start MathJax: {exc}") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        if "Cannot find module" in detail or "@mathjax/src" in detail:
            raise MathJaxUnavailable(
                "locked MathJax runtime unavailable; run "
                "'bash scripts/ensure_mathjax.sh'. "
                + (detail[:3000] or "renderer process failed")
            )
        raise MathRenderError(detail[:3000] or "MathJax process failed")
    if len(result.stdout) > MAX_RENDER_OUTPUT_BYTES:
        raise MathRenderError(
            f"MathJax output exceeds the {MAX_RENDER_OUTPUT_BYTES}-byte safety limit"
        )
    try:
        rendered = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MathRenderError(f"invalid MathJax output: {exc}") from exc
    if not isinstance(rendered, list) or len(rendered) != len(formulas):
        raise MathRenderError("MathJax returned a mismatched formula count")
    for index, fragment in enumerate(rendered, start=1):
        if not isinstance(fragment, str):
            raise MathRenderError(f"formula {index} returned an invalid SVG fragment")
        inspector = _SvgSafetyParser()
        try:
            inspector.feed(fragment)
            inspector.close()
        except Exception as exc:
            raise MathRenderError(
                f"formula {index} returned malformed SVG: {exc}"
            ) from exc
        if (
            inspector.root_name != "mjx-container"
            or inspector.root_count != 1
            or not inspector.saw_svg
            or inspector.unsafe
            or inspector.malformed
            or inspector._stack
            or not fragment.rstrip().endswith("</mjx-container>")
        ):
            raise MathRenderError(f"formula {index} returned unsafe SVG content")
    return rendered


def render_latex_in_html(raw: str) -> str:
    """Replace standard TeX delimiters in HTML text nodes with strict SVG."""
    spans, issues = _latex_spans(raw)
    if issues:
        raise MathRenderError("; ".join(issues))
    if not spans:
        return raw
    formulas = [{"tex": span.tex, "display": span.display} for span in spans]
    fragments = _render_svg(formulas)
    pieces: list[str] = []
    cursor = 0
    for span, fragment in zip(spans, fragments):
        pieces.append(raw[cursor:span.start])
        if span.display:
            pieces.append(
                '<span class="latex-display-svg" '
                'style="display:block;text-align:center;margin:10pt 0;'
                'break-inside:avoid;">'
                + fragment
                + "</span>"
            )
        else:
            pieces.append(
                '<span class="latex-inline-svg" '
                'style="display:inline-block;vertical-align:middle;'
                'white-space:nowrap;">'
                + fragment
                + "</span>"
            )
        cursor = span.end
    pieces.append(raw[cursor:])
    return "".join(pieces)


def check_latex_html(raw: str) -> list[str]:
    """Return every raw, unmatched, or legacy formula-source issue."""
    spans, issues = _latex_spans(raw)
    if spans:
        issues.insert(0, f"{len(spans)} raw LaTeX formula delimiter pair(s) remain")
    return issues


def check_latex_file(argv: list[str]) -> int:
    """CLI-shaped formula-source check shared with the MCP server."""
    if len(argv) != 1:
        print("ERROR: usage: math check path/to/filled.html")
        return 2
    path = Path(argv[0])
    if not path.is_file():
        print(f"ERROR: {path} not found")
        return 2
    try:
        issues = check_latex_html(path.read_text(encoding="utf-8"))
    except (MathRenderError, OSError, UnicodeError) as exc:
        print(f"ERROR: {path}: {exc}")
        return 1
    if issues:
        print(f"ERROR: {path}: " + "; ".join(issues))
        return 1
    print(f"OK: {path}: no raw or unrendered LaTeX")
    return 0


def _atomic_write_text(path: Path, content: str) -> None:
    if path.is_symlink():
        raise MathRenderError(f"refusing to replace symlink in place: {path}")
    mode = stat.S_IMODE(path.stat().st_mode)
    temporary: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--in-place", type=Path)
    group.add_argument("--check", type=Path)
    args = parser.parse_args(argv)
    path = args.in_place or args.check
    if not path.is_file():
        print(f"ERROR: {path} not found")
        return 1
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"ERROR: could not read {path}: {exc}")
        return 1
    if args.in_place:
        try:
            spans, issues = _latex_spans(raw)
            if issues:
                raise MathRenderError("; ".join(issues))
            rendered = render_latex_in_html(raw)
            if rendered != raw:
                _atomic_write_text(path, rendered)
        except (MathRenderError, OSError) as exc:
            print(f"ERROR: strict LaTeX rendering failed: {exc}")
            return 1
        print(f"OK: {path}: rendered {len(spans)} LaTeX formula(s) to SVG")
        return 0
    try:
        issues = check_latex_html(raw)
    except MathRenderError as exc:
        issues = [str(exc)]
    if issues:
        print(f"ERROR: {path}: " + "; ".join(issues))
        return 1
    print(f"OK: {path}: no raw or unrendered LaTeX")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
