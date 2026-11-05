#!/usr/bin/env python3
"""scan_ai_taste.py: static AI-taste scanner for Chinese + English prose.

Markdown aware. Skips front matter, fenced code, inline code, URLs, link
targets, and HTML comments. Prints hits with line:col, severity, rule id, and a
fix hint. Exits non-zero when any hit reaches --fail-on (default: high).

It is a lint, not a classifier. A clean scan does not mean the text is good;
see ../references/de-ai.md for the judgement checks no regex can make.

Usage:
  python3 scan_ai_taste.py draft.md
  python3 scan_ai_taste.py docs/ --profile gpt-6.1-sol
  cat draft.md | python3 scan_ai_taste.py - --json
  python3 scan_ai_taste.py outputs/*.md --ngrams 4 --top 30

Exit codes: 0 no hit at/above --fail-on; 1 at least one; 2 usage error.
Zero dependencies (Python 3.8+). PyYAML is used when present; otherwise a
built-in parser reads the restricted YAML subset used by patterns.yaml.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from typing import Dict, Iterable, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATTERNS = os.path.join(HERE, "patterns.yaml")
SEVERITIES = ["low", "medium", "high"]
SEV_RANK = {"low": 1, "medium": 2, "high": 3}
SEV_WEIGHT = {"low": 1, "medium": 2, "high": 5}
TEXT_EXT = {".md", ".markdown", ".txt", ".mdx", ".rst", ".adoc"}
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\u2B50\u2B06\u2194-\u21AA\u2705\u274C\u2728]"
)


# ---------------------------------------------------------------- YAML subset
def _scalar(raw: str):
    raw = raw.strip()
    if raw == "":
        return ""
    if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
        return raw[1:-1].replace("''", "'")
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        esc = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "/": "/"}
        return re.sub(r'\\(.)', lambda m: esc.get(m.group(1), "\\" + m.group(1)), raw[1:-1])
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [_scalar(x) for x in inner.split(",")] if inner else []
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    if raw in ("true", "false"):
        return raw == "true"
    return raw


def _strip_comment(line: str) -> str:
    out, q = [], None
    for i, ch in enumerate(line):
        if q:
            out.append(ch)
            if ch == q:
                q = None
            continue
        if ch in ("'", '"'):
            q = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def load_yaml_subset(text: str) -> dict:
    """Parse: top-level `key: scalar` and `key:` followed by a list of flat maps."""
    data: dict = {}
    cur_list: Optional[list] = None
    cur_item: Optional[dict] = None
    for n, line in enumerate(text.splitlines(), 1):
        line = _strip_comment(line)
        if not line.strip():
            continue
        if not line.startswith(" ") and not line.startswith("-"):
            key, _, val = line.partition(":")
            if val.strip():
                data[key.strip()] = _scalar(val)
                cur_list = None
            else:
                cur_list = []
                data[key.strip()] = cur_list
            cur_item = None
            continue
        s = line.strip()
        if s.startswith("- "):
            if cur_list is None:
                raise ValueError(f"patterns.yaml:{n}: list item outside a list")
            cur_item = {}
            cur_list.append(cur_item)
            s = s[2:]
        if cur_item is None:
            raise ValueError(f"patterns.yaml:{n}: cannot parse: {line}")
        key, _, val = s.partition(":")
        cur_item[key.strip()] = _scalar(val)
    return data


def load_patterns(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError:
        return load_yaml_subset(text)


# ------------------------------------------------------------------ data types
@dataclass
class Rule:
    id: str
    kind: str = "regex"
    pattern: str = ""
    severity: str = "medium"
    category: str = ""
    lang: str = "any"
    message: str = ""
    hint: str = ""
    scope: str = "line"
    flags: str = ""
    escalate_at: int = 0
    escalate_to: str = "high"
    profiles: List[str] = field(default_factory=list)
    raw: bool = False
    check: str = ""
    params: Dict[str, float] = field(default_factory=dict)
    compiled: Optional[re.Pattern] = None


@dataclass
class Hit:
    file: str
    line: int
    col: int
    rule: str
    severity: str
    category: str
    message: str
    hint: str
    match: str
    note: str = ""


@dataclass
class Para:
    start_line: int
    lines: List[Tuple[int, str]]

    @property
    def text(self) -> str:
        return "".join(t.strip() if CJK_RE.search(t) else " " + t.strip() for _, t in self.lines).strip()


# ------------------------------------------------------------- preprocessing
URL_RE = re.compile(r"https?://[^\s)>\]]+")
LINK_TARGET_RE = re.compile(r"\]\(([^)]*)\)")
INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*)$")
BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def _blank(m: re.Match) -> str:
    return " " * len(m.group(0))


def mask_text(text: str, skip_quotes: bool) -> List[str]:
    """Return lines with non-prose regions replaced by spaces (columns kept)."""
    lines = text.splitlines()
    out: List[str] = []
    in_fence: Optional[str] = None
    in_front = bool(lines) and lines[0].strip() == "---"
    in_comment = False
    ignore_block = False
    for idx, line in enumerate(lines):
        s = line.strip()
        if in_front:
            out.append("")
            if idx > 0 and s in ("---", "..."):
                in_front = False
            continue
        if "ai-taste: off" in s:
            ignore_block = True
        if "ai-taste: on" in s:
            ignore_block = False
            out.append("")
            continue
        if ignore_block or "ai-taste-ignore" in s:
            out.append("")
            continue
        fence = re.match(r"^\s*(```+|~~~+)", line)
        if in_fence:
            out.append("")
            if fence and fence.group(1)[0] == in_fence[0] and len(fence.group(1)) >= len(in_fence):
                in_fence = None
            continue
        if fence:
            in_fence = fence.group(1)
            out.append("")
            continue
        if in_comment:
            out.append("")
            if "-->" in line:
                in_comment = False
            continue
        if "<!--" in line and "-->" not in line:
            in_comment = True
            out.append("")
            continue
        line = re.sub(r"<!--.*?-->", _blank, line)
        if skip_quotes and s.startswith(">"):
            out.append("")
            continue
        if line.startswith("    ") and not BULLET_RE.match(line) and (not out or out[-1].strip() == "" or out[-1].startswith("    ")):
            # indented code block
            if not CJK_RE.search(line):
                out.append("")
                continue
        line = INLINE_CODE_RE.sub(_blank, line)
        line = LINK_TARGET_RE.sub(lambda m: "]" + " " * (len(m.group(0)) - 1), line)
        line = URL_RE.sub(_blank, line)
        out.append(line)
    return out


def is_prose_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if HEADING_RE.match(line) or s.startswith("|") or BULLET_RE.match(line):
        return False
    if re.fullmatch(r"[-=*_]{3,}", s):
        return False
    return True


def paragraphs(lines: List[str]) -> List[Para]:
    paras: List[Para] = []
    cur: List[Tuple[int, str]] = []
    for i, line in enumerate(lines, 1):
        if is_prose_line(line):
            s = line.strip()
            if s.startswith(">"):
                s = s.lstrip("> ")
            cur.append((i, s))
        else:
            if cur:
                paras.append(Para(cur[0][0], cur))
                cur = []
    if cur:
        paras.append(Para(cur[0][0], cur))
    return paras


SENT_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])|(?<=[.?!])\s+(?=[A-Z\"'“‘(])")


def sentences(text: str) -> List[str]:
    parts = [p.strip() for p in SENT_SPLIT_RE.split(text) if p and p.strip()]
    return [p for p in parts if measure(p) >= 2]


def measure(s: str) -> int:
    """Length unit: CJK characters + Latin words."""
    return len(CJK_RE.findall(s)) + len(re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*", s))


def line_lang(line: str) -> str:
    return "zh" if CJK_RE.search(line) else "en"


# --------------------------------------------------------------- rule loading
def build_rules(data: dict, profile: str, langs: Optional[str]) -> List[Rule]:
    rules: List[Rule] = []
    for raw in data.get("rules", []) or []:
        r = Rule(id=str(raw.get("id")))
        for k, v in raw.items():
            if k == "id":
                continue
            if k in Rule.__dataclass_fields__:
                setattr(r, k, v)
            else:
                r.params[k] = v
        if isinstance(r.profiles, str):
            r.profiles = [r.profiles]
        if r.profiles and profile != "all" and profile not in r.profiles:
            continue
        if langs and r.lang not in ("any", langs):
            continue
        if r.severity not in SEV_RANK:
            raise ValueError(f"rule {r.id}: bad severity {r.severity}")
        if r.kind == "regex":
            fl = re.IGNORECASE if "i" in str(r.flags) else 0
            fl |= re.MULTILINE
            try:
                r.compiled = re.compile(r.pattern, fl)
            except re.error as exc:
                raise ValueError(f"rule {r.id}: bad regex: {exc}") from exc
        rules.append(r)
    return rules


# ------------------------------------------------------------- structural checks
def _cv(values: List[int]) -> float:
    if len(values) < 2:
        return 1.0
    mean = statistics.mean(values)
    return statistics.pstdev(values) / mean if mean else 1.0


def run_structural(rule: Rule, fname: str, masked: List[str], paras: List[Para], allow: List[str]) -> List[Hit]:
    p = rule.params
    hits: List[Hit] = []

    def mk(line: int, match: str, note: str = "") -> Hit:
        return Hit(fname, line, 1, rule.id, rule.severity, rule.category, rule.message, rule.hint, match, note)

    if rule.check == "sentence_uniformity":
        sents = [s for para in paras for s in sentences(para.text)]
        lens = [measure(s) for s in sents]
        if len(lens) >= int(p.get("min_sentences", 8)):
            cv = _cv(lens)
            if cv < float(p.get("threshold", 0.3)):
                hits.append(mk(paras[0].start_line, f"{len(lens)} 句，均长 {statistics.mean(lens):.1f}，CV={cv:.2f}"))
    elif rule.check == "paragraph_uniformity":
        prose = [para for para in paras if measure(para.text) >= 15]
        lens = [measure(para.text) for para in prose]
        if len(lens) >= int(p.get("min_paragraphs", 5)):
            cv = _cv(lens)
            if cv < float(p.get("threshold", 0.25)):
                hits.append(mk(prose[0].start_line, f"{len(lens)} 段，均长 {statistics.mean(lens):.0f}，CV={cv:.2f}"))
    elif rule.check == "one_line_paragraphs":
        prose = [para for para in paras if measure(para.text) >= 4]
        if len(prose) >= int(p.get("min_paragraphs", 6)):
            singles = [para for para in prose if len(sentences(para.text)) <= 1]
            ratio = len(singles) / len(prose)
            if ratio >= float(p.get("threshold", 0.5)):
                hits.append(mk(singles[0].start_line, f"{len(singles)}/{len(prose)} 段只有一句"))
    elif rule.check == "bold_label_list":
        pat = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\*\*[^*]{1,40}\*\*\s*[:：]")
        run: List[int] = []
        min_run = int(p.get("min_run", 3))
        for i, line in enumerate(masked + [""], 1):
            if pat.match(line):
                run.append(i)
            else:
                if len(run) >= min_run:
                    hits.append(mk(run[0], f"连续 {len(run)} 条「**标签**：」列表"))
                run = []
    elif rule.check == "emoji_decor":
        for i, line in enumerate(masked, 1):
            m = HEADING_RE.match(line)
            body = m.group(2) if m else (BULLET_RE.sub("", line, count=1) if BULLET_RE.match(line) else None)
            if body is not None and EMOJI_RE.match(body.strip()[:1] or " "):
                hits.append(mk(i, body.strip()[:20]))
    elif rule.check == "repeated_openers":
        n = int(p.get("run", 3))
        for para in paras:
            sents = sentences(para.text)
            keys = []
            for s in sents:
                s2 = s.lstrip("“\"'（(")
                keys.append(s2[:2] if CJK_RE.match(s2[:1] or " ") else (s2.split()[0].lower() if s2.split() else ""))
            for j in range(len(keys) - n + 1):
                window = keys[j : j + n]
                if window[0] and all(k == window[0] for k in window):
                    hits.append(mk(para.start_line, f"连续 {n} 句以「{window[0]}」开头"))
                    break
    elif rule.check == "heading_density":
        heads = [i for i, line in enumerate(masked, 1) if HEADING_RE.match(line)]
        body = sum(measure(line) for line in masked if line.strip() and not HEADING_RE.match(line))
        if len(heads) >= int(p.get("min_headings", 5)) and body:
            per_k = len(heads) / body * 1000
            if per_k > float(p.get("threshold", 8)):
                hits.append(mk(heads[0], f"{len(heads)} 个标题 / {body} 字词，约每 {body // len(heads)} 字词一个"))
    elif rule.check == "title_case_heading":
        for i, line in enumerate(masked, 1):
            m = HEADING_RE.match(line)
            if not m or CJK_RE.search(m.group(2)):
                continue
            words = re.findall(r"[A-Za-z][A-Za-z'-]*", m.group(2))
            big = [w for w in words if len(w) > 3]
            if len(big) >= 3 and all(w[0].isupper() for w in big):
                hits.append(mk(i, m.group(2).strip()[:40]))
    else:
        raise ValueError(f"rule {rule.id}: unknown structural check {rule.check}")
    return hits


# ------------------------------------------------------------------- scanning
def scan_text(fname: str, text: str, rules: List[Rule], allow: List[str], skip_quotes: bool, structure: bool) -> Tuple[List[Hit], int]:
    masked = mask_text(text, skip_quotes)
    raw_lines = text.splitlines()
    paras = paragraphs(masked)
    hits: List[Hit] = []
    allow_re = re.compile("|".join(re.escape(a) for a in allow)) if allow else None

    def allowed(s: str) -> bool:
        return bool(allow_re and allow_re.search(s))

    for rule in rules:
        if rule.kind == "structural":
            if structure:
                hits.extend(run_structural(rule, fname, masked, paras, allow))
            continue
        rx = rule.compiled
        assert rx is not None
        if rule.scope in ("line", "heading", "bullet"):
            src = raw_lines if rule.raw else masked
            for i, line in enumerate(src, 1):
                if not line.strip():
                    continue
                target = line
                offset = 0
                if rule.scope == "heading":
                    m = HEADING_RE.match(line)
                    if not m:
                        continue
                    target, offset = m.group(2).strip(), line.find(m.group(2))
                elif rule.scope == "bullet":
                    if not BULLET_RE.match(line):
                        continue
                if rule.lang != "any" and line_lang(line) != rule.lang:
                    continue
                for m in rx.finditer(target):
                    if allowed(m.group(0)):
                        continue
                    hits.append(Hit(fname, i, offset + m.start() + 1, rule.id, rule.severity, rule.category, rule.message, rule.hint, m.group(0)[:60]))
        elif rule.scope in ("para_end", "para_start", "doc_start"):
            targets = paras[:1] if rule.scope == "doc_start" else paras
            for para in targets:
                if rule.lang != "any" and line_lang(para.text) != rule.lang:
                    continue
                sents = sentences(para.text)
                if not sents:
                    continue
                if rule.scope == "para_end":
                    if len(sents) < 2:
                        continue
                    s = sents[-1]
                    m = rx.match(s.lstrip("“\"（("))
                    line_no = para.lines[-1][0]
                elif rule.scope == "para_start":
                    s = sents[0]
                    m = rx.match(s)
                    line_no = para.start_line
                else:
                    s = para.text
                    m = rx.search(s)
                    line_no = para.start_line
                if m and not allowed(m.group(0)):
                    hits.append(Hit(fname, line_no, 1, rule.id, rule.severity, rule.category, rule.message, rule.hint, s[:60]))
        else:
            raise ValueError(f"rule {rule.id}: unknown scope {rule.scope}")

    # escalation by count per document
    by_rule: Dict[str, List[Hit]] = defaultdict(list)
    for h in hits:
        by_rule[h.rule].append(h)
    rmap = {r.id: r for r in rules}
    for rid, group in by_rule.items():
        r = rmap[rid]
        if r.escalate_at and len(group) >= int(r.escalate_at) and SEV_RANK[r.escalate_to] > SEV_RANK[r.severity]:
            for h in group:
                h.severity = r.escalate_to
                h.note = f"全文 {len(group)} 处，已升级为 {r.escalate_to}"
    hits.sort(key=lambda h: (h.line, h.col, -SEV_RANK[h.severity]))
    size = sum(measure(line) for line in masked)
    return hits, size


def verdict(score: float) -> str:
    if score < 3:
        return "clean"
    if score < 8:
        return "light"
    if score < 16:
        return "moderate"
    return "heavy"


# --------------------------------------------------------------------- ngrams
def ngram_report(texts: Dict[str, str], n: int, top: int, min_count: int) -> List[Tuple[str, int, int]]:
    counts: Counter = Counter()
    docs: Dict[str, set] = defaultdict(set)
    for fname, text in texts.items():
        masked = "\n".join(mask_text(text, False))
        for run in re.findall(r"[\u3400-\u9fff]+", masked):
            for i in range(len(run) - n + 1):
                g = run[i : i + n]
                counts[g] += 1
                docs[g].add(fname)
        words = re.findall(r"[a-z]+(?:'[a-z]+)?", masked.lower())
        wn = max(2, n - 1)
        for i in range(len(words) - wn + 1):
            g = " ".join(words[i : i + wn])
            counts[g] += 1
            docs[g].add(fname)
    rows = [(g, c, len(docs[g])) for g, c in counts.items() if c >= min_count]
    rows.sort(key=lambda x: (-x[2], -x[1]))
    return rows[:top]


# ----------------------------------------------------------------------- main
def iter_inputs(paths: List[str]) -> Iterable[Tuple[str, str]]:
    for p in paths:
        if p == "-":
            yield "<stdin>", sys.stdin.read()
        elif os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in sorted(files):
                    if os.path.splitext(f)[1].lower() in TEXT_EXT:
                        fp = os.path.join(root, f)
                        with open(fp, encoding="utf-8", errors="replace") as fh:
                            yield fp, fh.read()
        elif os.path.isfile(p):
            with open(p, encoding="utf-8", errors="replace") as fh:
                yield p, fh.read()
        else:
            raise FileNotFoundError(p)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Static AI-taste scanner (CN+EN). A lint, not a classifier.")
    ap.add_argument("paths", nargs="*", help="files, directories, or - for stdin")
    ap.add_argument("--patterns", default=DEFAULT_PATTERNS, help="patterns.yaml path")
    ap.add_argument("--profile", default="generic", choices=["generic", "gpt-6.1-sol", "deepseek-flash", "all"], help="model profile adds model-specific rules")
    ap.add_argument("--lang", choices=["zh", "en"], help="only load rules for one language")
    ap.add_argument("--fail-on", default="high", choices=["high", "medium", "low", "never"])
    ap.add_argument("--show", default="low", choices=SEVERITIES, help="minimum severity to print")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--allow", action="append", default=[], help="phrase to ignore (repeatable); use for the author's own voice")
    ap.add_argument("--allow-file", help="file with one allowed phrase per line")
    ap.add_argument("--skip-quotes", action="store_true", help="skip > blockquote lines (quoted sources)")
    ap.add_argument("--no-structure", action="store_true", help="skip structural/statistical checks")
    ap.add_argument("--ngrams", type=int, metavar="N", help="print top repeated N-grams across inputs, then exit 0")
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--min-count", type=int, default=3)
    ap.add_argument("--list-rules", action="store_true")
    args = ap.parse_args(argv)

    try:
        data = load_patterns(args.patterns)
        rules = build_rules(data, args.profile, args.lang)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.list_rules:
        for r in rules:
            prof = ",".join(r.profiles) if r.profiles else "generic"
            print(f"{r.id:7} {r.severity:6} {r.lang:3} {prof:16} {r.category}: {r.message}")
        return 0
    if not args.paths:
        ap.print_usage(sys.stderr)
        print("error: no input (pass a file, a directory, or -)", file=sys.stderr)
        return 2

    allow = list(args.allow)
    if args.allow_file:
        with open(args.allow_file, encoding="utf-8") as fh:
            allow += [x.strip() for x in fh if x.strip() and not x.startswith("#")]

    try:
        inputs = dict(iter_inputs(args.paths))
    except FileNotFoundError as exc:
        print(f"error: not found: {exc}", file=sys.stderr)
        return 2
    if not inputs:
        print("error: no text files found", file=sys.stderr)
        return 2

    if args.ngrams:
        rows = ngram_report(inputs, args.ngrams, args.top, args.min_count)
        if args.json:
            print(json.dumps([{"ngram": g, "count": c, "docs": d} for g, c, d in rows], ensure_ascii=False, indent=2))
        else:
            print(f"# top repeated n-grams across {len(inputs)} file(s): count / files")
            for g, c, d in rows:
                print(f"{c:5}  {d:3}  {g}")
        return 0

    fail_rank = SEV_RANK.get(args.fail_on, 99)
    show_rank = SEV_RANK[args.show]
    report = []
    failed = False
    for fname, text in inputs.items():
        hits, size = scan_text(fname, text, rules, allow, args.skip_quotes, not args.no_structure)
        counts = Counter(h.severity for h in hits)
        score = sum(SEV_WEIGHT[h.severity] for h in hits) / max(size, 1) * 1000
        if any(SEV_RANK[h.severity] >= fail_rank for h in hits):
            failed = True
        report.append({"file": fname, "units": size, "score_per_1k": round(score, 1), "verdict": verdict(score), "counts": dict(counts), "hits": hits})

    if args.json:
        out = [{**r, "hits": [asdict(h) for h in r["hits"]]} for r in report]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 1 if failed else 0

    for r in report:
        print(f"== {r['file']}  units={r['units']}  score/1k={r['score_per_1k']}  verdict={r['verdict']}  "
              f"high={r['counts'].get('high', 0)} medium={r['counts'].get('medium', 0)} low={r['counts'].get('low', 0)}")
        for h in r["hits"]:
            if SEV_RANK[h.severity] < show_rank:
                continue
            note = f" [{h.note}]" if h.note else ""
            print(f"{h.file}:{h.line}:{h.col}: {h.severity.upper():6} {h.rule} {h.category}: {h.message} 「{h.match.strip()}」{note}")
            if h.hint:
                print(f"    -> {h.hint}")
    total = Counter()
    for r in report:
        total.update(r["counts"])
    print(f"-- {len(report)} file(s); high={total.get('high', 0)} medium={total.get('medium', 0)} low={total.get('low', 0)}; "
          f"fail-on={args.fail_on}; result={'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
