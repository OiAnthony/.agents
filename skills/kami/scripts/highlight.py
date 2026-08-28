"""Lightweight syntax highlighting for Kami HTML templates.

Scans HTML for <pre><code class="language-*"> blocks and applies
Pygments-based inline-style highlighting using Kami design tokens.
Blocks without a language- class pass through unchanged.
"""
from __future__ import annotations

import html as html_mod
import re
import sys

from shared import token_value

CODE_BLOCK_RE = re.compile(
    r'(?P<open><pre\b[^>]*>\s*<code\b[^>]*>)'
    r'(?P<code>.*?)'
    r'(?P<close></code\s*>\s*</pre\s*>)',
    re.DOTALL | re.IGNORECASE,
)
CLASS_ATTR_RE = re.compile(
    r'''(?:^|\s)class\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))''',
    re.IGNORECASE,
)

_KAMI_PALETTE: dict[str, str] | None = None


def _kami_palette() -> dict[str, str]:
    """Resolve design-token colors lazily.

    Kept out of module scope so importing this module (e.g. by build.py for a
    command that never highlights code) does not read tokens.json. That keeps
    the import resilient on a half-installed checkout, matching shared.py's
    baked-in fallbacks.
    """
    global _KAMI_PALETTE
    if _KAMI_PALETTE is None:
        _KAMI_PALETTE = {
            "brand":      token_value("brand"),
            "stone":      token_value("stone"),
            "olive":      token_value("olive"),
            "dark_warm":  token_value("dark-warm"),
            "near_black": token_value("near-black"),
        }
    return _KAMI_PALETTE


_WARNED_MISSING_PYGMENTS = False


def _warn_missing_pygments() -> None:
    global _WARNED_MISSING_PYGMENTS
    if _WARNED_MISSING_PYGMENTS:
        return
    print(
        "WARN: Pygments is not installed; language-tagged code blocks will render monochrome. "
        "Install with `python3 -m pip install Pygments` to enable syntax highlighting.",
        file=sys.stderr,
    )
    _WARNED_MISSING_PYGMENTS = True


def _build_kami_style():
    from pygments.style import Style
    from pygments.token import (
        Comment, Keyword, Literal, Name, Number, Operator,
        Punctuation, String, Token,
    )

    palette = _kami_palette()

    class KamiStyle(Style):
        background_color = ""
        default_style = ""
        styles = {
            Token:              "",
            Comment:            palette["stone"],
            Comment.Single:     palette["stone"],
            Comment.Multiline:  palette["stone"],
            Comment.Preproc:    palette["stone"],
            Keyword:            palette["brand"],
            Keyword.Constant:   palette["brand"],
            Keyword.Namespace:  palette["brand"],
            Keyword.Type:       palette["brand"],
            Name.Builtin:       palette["brand"],
            Name.Function:      palette["near_black"],
            Name.Class:         palette["near_black"],
            Name.Decorator:     palette["olive"],
            String:             palette["olive"],
            String.Doc:         palette["stone"],
            Number:             palette["dark_warm"],
            Number.Float:       palette["dark_warm"],
            Number.Integer:     palette["dark_warm"],
            Literal:            palette["dark_warm"],
            Operator:           "",
            Punctuation:        "",
        }

    return KamiStyle


def _language_from_open_tag(open_tag: str) -> str | None:
    """Return the first ``language-*`` class token from a code start tag."""
    code_tag = re.search(r"<code\b(?P<attrs>[^>]*)>", open_tag, re.IGNORECASE)
    if code_tag is None:
        return None
    class_attr = CLASS_ATTR_RE.search(code_tag.group("attrs"))
    if class_attr is None:
        return None
    class_value = next(value for value in class_attr.groups() if value is not None)
    for token in class_value.split():
        match = re.fullmatch(r"language-([\w+-]+)", token, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _highlight_block(match: re.Match[str]) -> str:
    from pygments import highlight as pyg_highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_by_name

    open_tag = match.group("open")
    language = _language_from_open_tag(open_tag)
    if language is None:
        return match.group(0)
    code = match.group("code")
    close_tag = match.group("close")

    code_text = html_mod.unescape(code)

    try:
        lexer = get_lexer_by_name(language, stripall=False)
    except Exception:
        return match.group(0)

    formatter = HtmlFormatter(
        style=_build_kami_style(),
        noclasses=True,
        nowrap=True,
    )

    highlighted = pyg_highlight(code_text, lexer, formatter)
    return f'{open_tag}{highlighted}{close_tag}'


def highlight_code_blocks(html_text: str) -> str:
    """Apply syntax highlighting to language-tagged code blocks.

    Returns HTML unchanged if Pygments is not installed or no
    language-tagged blocks are found.
    """
    matches = list(CODE_BLOCK_RE.finditer(html_text))
    if not matches or not any(
        _language_from_open_tag(match.group("open")) for match in matches
    ):
        return html_text

    try:
        import pygments  # noqa: F401
    except ImportError:
        _warn_missing_pygments()
        return html_text

    return CODE_BLOCK_RE.sub(_highlight_block, html_text)
