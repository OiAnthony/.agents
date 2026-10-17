"""Keep Korean words whole at line ends in the PDF render.

Korean breaks lines between words (eojeol), not between syllables. Browsers do
that with `word-break: keep-all`; WeasyPrint ignores it and breaks inside a
word ("파이프라 / 인을"). Left alone, agents patch it in the source with
per-syllable joiners or a span around every word, which makes the HTML
unreadable. This runs once inside `render.render_pdf` instead: it puts U+2060
WORD JOINER between the characters of every word that contains Hangul, in the
rendered copy only. The joiner draws nothing and does not reach the PDF text
layer, so extracted text, search, and the PDF gates read the same words.

Words longer than MAX_WORD_UNITS stay breakable so a long compound in a narrow
table cell wraps instead of overflowing.
"""
from __future__ import annotations

import re

JOINER = "⁠"
MAX_WORD_UNITS = 16

_HANGUL = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")
_TOKEN = re.compile(r"(<!--.*?-->|<[^>]+>)", re.S)
_TAG_NAME = re.compile(r"<\s*(/?)\s*([a-zA-Z][\w:-]*)")
_UNIT = re.compile(r"&#?\w+;|.", re.S)

# Inside these the text is not prose (or is not text at all).
_SKIP = {"head", "style", "script", "svg", "math", "pre", "code", "textarea", "title"}
# A word may continue across these; any other tag ends it.
_INLINE = {"a", "abbr", "b", "bdi", "bdo", "cite", "data", "dfn", "em", "i", "kbd",
           "mark", "q", "s", "samp", "small", "span", "strong", "sub", "sup", "time",
           "u", "var", "wbr", "font"}


def _is_space(unit: str) -> bool:
    return unit.isspace()


def _join_text(text: str, carry: bool) -> tuple[str, bool]:
    """Join units inside Hangul words. `carry` says the previous text ended
    mid-word on a Hangul-bearing word, so this text continues it."""
    units = _UNIT.findall(text)
    out: list[str] = []
    i = 0
    first_word = True
    tail_open = False
    while i < len(units):
        if _is_space(units[i]):
            out.append(units[i])
            i += 1
            first_word = False
            continue
        j = i
        while j < len(units) and not _is_space(units[j]):
            j += 1
        word = units[i:j]
        continues = first_word and carry
        hangul = any(_HANGUL.match(u) for u in word)
        if (hangul or continues) and len(word) <= MAX_WORD_UNITS:
            if continues:
                out.append(JOINER)
            out.append(JOINER.join(word))
        else:
            out.append("".join(word))
        tail_open = j == len(units) and (hangul or continues)
        i = j
        first_word = False
    return "".join(out), tail_open


def _starts_hangul_word(text: str) -> bool:
    m = re.match(r"\S+", text)
    return bool(m) and bool(_HANGUL.search(m.group(0)))


def join_hangul_words(html: str) -> str:
    if not _HANGUL.search(html):
        return html
    parts = _TOKEN.split(html)
    skip_depth = 0
    skip_stack: list[str] = []
    carry = False          # previous text ended inside a Hangul word
    pending_plain = False  # previous text ended inside a plain word that a Hangul word may continue
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            out.append(part)
            if part.startswith("<!--"):
                continue
            m = _TAG_NAME.match(part)
            if not m:
                continue
            closing, name = m.group(1) == "/", m.group(2).lower()
            self_closing = part.rstrip().endswith("/>")
            if name in _SKIP and not self_closing:
                if closing:
                    if skip_stack and skip_stack[-1] == name:
                        skip_stack.pop()
                else:
                    skip_stack.append(name)
                skip_depth = len(skip_stack)
            if name not in _INLINE:
                carry = pending_plain = False
            continue
        if skip_depth:
            out.append(part)
            continue
        starts_word = bool(part) and not part[0].isspace()
        joined_carry = starts_word and (carry or (pending_plain and _starts_hangul_word(part)))
        text, tail = _join_text(part, joined_carry)
        out.append(text)
        ends_word = not part[-1].isspace()
        carry = tail
        pending_plain = ends_word and not tail
    return "".join(out)
