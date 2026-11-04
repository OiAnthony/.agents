#!/usr/bin/env python3
"""Validate an incident ledger and print the replay plan for review evals.

An incident ledger is a Markdown table, one row per defect that reached users
or a published build. Each row names the fix commit, the introducing commit
when known, the earliest layer that should have caught it, and the test or
gate that catches it now. This helper checks that every row still holds:

- the ID is unique and the Reported cell, when present, is a YYYY-MM-DD date;
- Fixed is a commit that resolves, and Introduced is `unknown` or a commit;
- Layer is one of the ledger's declared layers;
- every backticked catcher in "Caught by" is an existing workspace file path
  or a recognized declaration in a Python, shell/Bats, or JS/TS test file.
  Unsupported declaration forms and languages require an explicit gate path.
  Declaration recognition does not prove that a test runs or catches a defect.

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
import ast
import shlex
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
    """Existing, contained worktree files, including non-ignored new files."""
    root = root.resolve()
    out = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    candidates = out.stdout.split("\0") if out.returncode == 0 else (
        p.relative_to(root).as_posix() for p in root.rglob("*")
    )
    files = set()
    for rel in candidates:
        if not rel or SKIP_PARTS.intersection(Path(rel).parts):
            continue
        path = root / rel
        try:
            path.resolve().relative_to(root)
            if path.is_file() and not path.is_symlink():
                files.add(rel)
        except (OSError, ValueError, RuntimeError):
            continue
    return sorted(files)


def is_test_file(path: str) -> bool:
    parts = path.split("/")
    if SKIP_PARTS.intersection(parts):
        return False
    if TEST_DIR_PARTS.intersection(part.lower() for part in parts[:-1]):
        return True
    return bool(TEST_NAME.match(parts[-1]))


def test_names(source: str, suffix: str) -> set[str]:
    """Recognize supported declarations, not arbitrary identifier mentions.

    Python uses its AST. JS/TS and shell use deliberately narrow declaration
    forms, not a syntax-validity proof. Unsupported forms need a gate path.
    """
    if suffix == ".py":
        try:
            return {node.name for node in ast.walk(ast.parse(source))
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        except (SyntaxError, ValueError):
            return set()
    names = set()
    if suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
        # Replace comments and literals before matching declaration shapes.
        # Keep literal positions separately for direct test registrations.
        literals = {}
        token = re.compile(r"//[^\n]*|/\*[\s\S]*?\*/|(['\"`])(?:\\[\s\S]|(?!\1)[^\\])*?\1")
        def mask(match):
            value = match.group()
            if value[0] in "'\"`":
                literals[match.start()] = (match.end(), value[1:-1])
            return "".join("\n" if char == "\n" else " " for char in value)
        clean = token.sub(mask, source)
        names.update(re.findall(r"(?m)^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", clean))
        names.update(re.findall(r"(?m)^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?(?:function\s*\(|\([^()]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)", clean))
        for pos, (end, title) in literals.items():
            # Only a literal first argument to a direct test registration.
            if re.search(r"(?:^|[;{}\n])\s*(?:it|test)(?:\.(?:only))?\s*\(\s*$", clean[:pos]) and re.match(r"\s*,", clean[end:]):
                if "\\" not in title and "${" not in title:
                    names.add(title)
    elif suffix in {".sh", ".bash", ".bats"}:
        # Heredoc bodies are shell data, not declarations. Prefer an explicit
        # gate path for these files rather than interpreting their contents.
        if "<<" in source:
            return set()
        try:
            tokens = shlex.shlex(source, posix=False)
            tokens.whitespace = " \t\r"
            tokens.whitespace_split = False
            tokens.commenters = "#"
            words = list(tokens)
        except ValueError:
            return set()
        for i, word in enumerate(words):
            boundary = i == 0 or words[i - 1] in {"\n", ";", "}"}
            if boundary and IDENTIFIER.fullmatch(word) and words[i + 1:i + 4] == ["(", ")", "{"]:
                names.add(word)
            if boundary and word == "function" and i + 2 < len(words):
                if IDENTIFIER.fullmatch(words[i + 1]) and words[i + 2] == "{":
                    names.add(words[i + 1])
            if boundary and words[i:i + 2] == ["@", "test"] and i + 3 < len(words) and words[i + 3] == "{":
                title = words[i + 2]
                if title.startswith(("'", '"')):
                    names.add(title[1:-1])
    return names


def test_corpus(root: Path, files: list[str]) -> set[str]:
    names = set()
    for rel in files:
        if not is_test_file(rel):
            continue
        path = root / rel
        try:
            path.resolve().relative_to(root.resolve())
            if path.is_symlink() or path.stat().st_size > MAX_TEST_BYTES:
                continue
            names.update(test_names(path.read_text("utf-8", errors="replace"), path.suffix))
        except (OSError, ValueError, RuntimeError):
            continue
    return names


def catcher_defined(name: str, corpus: set[str], files: set[str]) -> bool:
    return name in files or name in corpus


def problems(text: str, label: str, layers: tuple[str, ...], corpus: set[str],
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
            f"{where}: catcher `{name}` is not an existing workspace file or a recognized test declaration (use an explicit gate path for unsupported forms)"
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
