#!/usr/bin/env python3
"""Validate an incident ledger and print the replay plan for review evals.

An incident ledger is a Markdown table, one row per defect that reached users
or a published build. Each row names the fix commit, the introducing commit
when known, the earliest layer that should have caught it, and the test or
gate that catches it now. This helper checks that every row still holds:

- the ID is unique and the Reported cell, when present, is a YYYY-MM-DD date;
- Fixed is a commit that resolves, and Introduced is `unknown` or a commit;
- Layer is one of the ledger's declared layers;
- every backticked catcher in "Caught by" is a tracked file path, or a name
  that a test file defines (an identifier followed by `(`, or a quoted test
  title such as Bats `@test "..."` or JS `it("...")`).

In a shallow clone commits cannot be resolved, so they are shape-checked and
the summary says so. `--plan` prints, per row, the pre-fix revision and the
files the fix touched, which is what a review replay runs against.

Layers come from `--layers a,b,c`, else from a `<!-- layers: a, b, c -->`
comment in the ledger, else DEFAULT_LAYERS. Prose that explains the layers
is not parsed; the comment is the declaration.

Pure stdlib. Read-only. Exit 0 when every row holds, 1 when any row fails,
2 on usage errors or a missing ledger.

Run as: python3 <skill-base-dir>/scripts/incident_ledger.py --root <project>
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


DEFAULT_LEDGER = "docs/incidents.md"
DEFAULT_LAYERS = ("write-time", "unit", "integration", "review", "e2e", "release", "field")
REQUIRED_COLUMNS = ("ID", "Fixed", "Layer", "Caught by")
SHA = re.compile(r"^[0-9a-f]{7,40}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
TEST_DIR_PARTS = {"test", "tests", "spec", "specs", "__tests__", "testing"}
TEST_NAME = re.compile(
    r"(^test_.*|.*_test\.[^.]+$|.*\.(test|spec)\.[^.]+$|.*Tests?\.[^.]+$|.*\.bats$)"
)
SKIP_PARTS = {".git", "node_modules", "vendor", "dist", "build", "target", ".venv"}
MAX_TEST_BYTES = 2_000_000


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def table(text: str):
    """Header cells and (line number, cells) rows of the first table under
    `## Incidents`, or of the first table in the file when no such section."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "## Incidents"), -1) + 1
    header: list[str] = []
    body: list[tuple[int, list[str]]] = []
    for index in range(start, len(lines)):
        line = lines[index]
        if header and not line.startswith("|"):
            break
        if start and line.startswith("## "):
            break
        if not line.startswith("|"):
            continue
        cells = split_row(line)
        if not header:
            header = cells
        elif set("".join(cells)) <= set("-: "):
            continue
        else:
            body.append((index + 1, cells))
    return header, body


def declared_layers(text: str) -> tuple[str, ...]:
    match = re.search(r"<!--\s*layers:\s*(.*?)\s*-->", text, re.IGNORECASE | re.DOTALL)
    if match:
        names = tuple(name.strip() for name in match.group(1).split(",") if name.strip())
        if names:
            return names
    return DEFAULT_LAYERS


def tracked_files(root: Path) -> list[str]:
    out = git(root, "ls-files", "-z")
    if out.returncode == 0:
        return [p for p in out.stdout.split("\0") if p]
    return [
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and not SKIP_PARTS.intersection(p.relative_to(root).parts)
    ]


def is_test_file(path: str) -> bool:
    parts = path.split("/")
    if SKIP_PARTS.intersection(parts):
        return False
    if TEST_DIR_PARTS.intersection(part.lower() for part in parts[:-1]):
        return True
    return bool(TEST_NAME.match(parts[-1]))


def test_corpus(root: Path, files: list[str]) -> str:
    chunks = []
    for rel in files:
        if not is_test_file(rel):
            continue
        path = root / rel
        try:
            if path.is_symlink() or path.stat().st_size > MAX_TEST_BYTES:
                continue
            chunks.append(path.read_text("utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(chunks)


def catcher_defined(name: str, corpus: str, files: set[str]) -> bool:
    if name in files:
        return True
    if IDENTIFIER.match(name):
        return re.search(r"\b" + re.escape(name) + r"\s*\(", corpus) is not None
    quoted = re.escape(name)
    return re.search(r"([\"'`])" + quoted + r"\1", corpus) is not None


def problems(text: str, label: str, layers: tuple[str, ...], corpus: str,
             files: set[str], resolve) -> list[str]:
    header, body = table(text)
    if not header:
        return [f"{label}: no incident table found"]
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        return [f"{label}: table is missing column(s): {', '.join(missing)}"]
    found: list[str] = []
    seen: set[str] = set()
    for number, cells in body:
        where = f"{label}:{number}"
        if len(cells) != len(header):
            found.append(f"{where}: expected {len(header)} cells, found {len(cells)}")
            continue
        row = dict(zip(header, cells))
        if row["ID"] in seen:
            found.append(f"{where}: {row['ID']} repeats")
        seen.add(row["ID"])
        if "Reported" in row and not DATE.match(row["Reported"]):
            found.append(f"{where}: Reported is not a date: {row['Reported']}")
        for column in ("Fixed", "Introduced"):
            if column not in row or (column == "Introduced" and row[column] == "unknown"):
                continue
            value = row[column]
            if not SHA.match(value):
                found.append(f"{where}: {column} is not a commit: {value}")
            elif resolve is not None and not resolve(value):
                found.append(f"{where}: {column} {value} does not resolve")
        if row["Layer"] not in layers:
            found.append(f"{where}: layer {row['Layer']} is not one of {', '.join(layers)}")
        catchers = re.findall(r"`([^`]+)`", row["Caught by"])
        if not catchers:
            found.append(f"{where}: no catcher named")
        found.extend(
            f"{where}: catcher `{name}` is not a tracked file or a test defined in a test file"
            for name in catchers
            if not catcher_defined(name, corpus, files)
        )
    return found


def plan(root: Path, text: str) -> list[str]:
    header, body = table(text)
    if "Fixed" not in header:
        return []
    lines = []
    for _, cells in body:
        if len(cells) != len(header):
            continue
        row = dict(zip(header, cells))
        out = git(root, "show", "--name-only", "--format=", row["Fixed"])
        touched = " ".join(p for p in out.stdout.split() if p) if out.returncode == 0 else "(unresolved)"
        lines.append(f"{row['ID']}: review {row['Fixed']}^ files: {touched}")
    return lines


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate an incident ledger.")
    parser.add_argument("--root", default=".", help="project root (default: .)")
    parser.add_argument("--ledger", default=DEFAULT_LEDGER, help=f"ledger path (default: {DEFAULT_LEDGER})")
    parser.add_argument("--layers", help="comma-separated allowed layers; overrides the ledger's Layers line")
    parser.add_argument("--plan", action="store_true", help="print the replay plan after validating")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    ledger = (root / args.ledger) if not Path(args.ledger).is_absolute() else Path(args.ledger)
    if not ledger.is_file():
        print(f"incident ledger not found: {args.ledger}", file=sys.stderr)
        return 2
    text = ledger.read_text("utf-8", errors="replace")
    layers = tuple(x.strip() for x in args.layers.split(",") if x.strip()) if args.layers else declared_layers(text)

    in_git = git(root, "rev-parse", "--git-dir").returncode == 0
    shallow = in_git and git(root, "rev-parse", "--is-shallow-repository").stdout.strip() == "true"
    resolve = None
    if in_git and not shallow:
        def resolve(sha: str) -> bool:
            return git(root, "cat-file", "-e", sha + "^{commit}").returncode == 0

    files = tracked_files(root)
    try:
        label = ledger.resolve().relative_to(root).as_posix()
    except ValueError:
        label = str(ledger)
    found = problems(text, label, layers, test_corpus(root, files), set(files), resolve)
    for line in found:
        print(line)
    if args.plan and not found:
        for line in plan(root, text):
            print(line)
    count = len(table(text)[1])
    note = "" if resolve else (", commits shape-checked only (shallow clone)" if shallow else ", commits shape-checked only (not a git repository)")
    print(f"incident-ledger: {count} rows, {len(found)} problems{note}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
