#!/usr/bin/env python3
"""Check that doc references (@path, ~/.claude/..., docs/..., references/...) in
AGENTS.md, CLAUDE.md, .claude/rules/*.md, and .claude/skills/*/SKILL.md resolve
to real files. Prints `doc references: ok` on success, otherwise lists every
MISSING reference with source location.

Run as: python3 check_doc_refs.py [ROOT]
ROOT defaults to the current working directory.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


REF_RE = re.compile(
    r"(?<![\w/.-])("
    r"@[A-Za-z0-9_~/.-]+(?:\.md|/)|"
    r"~/\.claude/[A-Za-z0-9_/.-]+(?:\.md|/)|"
    r"(?:docs|references)/[A-Za-z0-9_/.-]+\.md"
    r")"
)
MAX_SOURCE_BYTES = 1_000_000


def safe_label(value: str, limit: int = 500) -> str:
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        value = json.dumps(value, ensure_ascii=False)
    return value if len(value) <= limit else f"{value[: limit - 3]}..."


def is_repo_file(path: Path, root: Path) -> bool:
    """Return true only for a regular file reached without any symlink hop."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    if not relative.parts:
        return False
    current = root
    try:
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                return False
        return current.is_file()
    except OSError:
        return False


def is_repo_dir(path: Path, root: Path) -> bool:
    """Return true only for a directory reached without any symlink hop."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    current = root
    try:
        if current.is_symlink():
            return False
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                return False
        return current.is_dir()
    except OSError:
        return False


def read_source(path: Path, root: Path) -> str:
    if not is_repo_file(path, root):
        return ""
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
    except OSError:
        return ""
    try:
        chunks: list[bytes] = []
        remaining = MAX_SOURCE_BYTES
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    except OSError:
        return ""
    finally:
        os.close(descriptor)
    return b"".join(chunks).decode("utf-8", errors="replace")


def resolve_ref(source: Path, raw: str, root: Path, home: Path) -> Path:
    ref = raw[1:] if raw.startswith("@") else raw

    if ref.startswith("~/"):
        return Path(os.path.abspath(home / ref[2:]))

    path = Path(ref)
    if path.is_absolute():
        return path

    if raw.startswith("@"):
        return Path(os.path.abspath(root / ref))

    if ref.startswith("docs/"):
        return Path(os.path.abspath(root / ref))

    if ref.startswith("references/"):
        source_parts = source.relative_to(root).parts
        if len(source_parts) >= 4 and source_parts[:2] == (".claude", "skills"):
            skill_root = root.joinpath(*source_parts[:3])
            return Path(os.path.abspath(skill_root / ref))
        return Path(os.path.abspath(root / ref))

    return Path(os.path.abspath(source.parent / ref))


def target_exists(target: Path, raw: str, root: Path, home: Path) -> bool:
    scope = home / ".claude" if raw.startswith("~/") else root
    if scope.is_symlink():
        return False
    if raw.endswith("/"):
        return is_repo_dir(target, scope)
    return is_repo_file(target, scope)


def collect_scan_files(root: Path) -> list[Path]:
    scan_files: list[Path] = []
    for candidate in (root / "AGENTS.md", root / "CLAUDE.md"):
        if is_repo_file(candidate, root):
            scan_files.append(candidate)
    for pattern in (".claude/rules/*.md", ".claude/skills/*/SKILL.md"):
        scan_files.extend(
            path for path in sorted(root.glob(pattern)) if is_repo_file(path, root)
        )
    return scan_files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="Project root (default: cwd)")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    home = Path(os.environ.get("HOME", "")).expanduser()

    scan_files = collect_scan_files(root)

    missing: list[str] = []
    seen: set[tuple[Path, int, str]] = set()
    for path in scan_files:
        in_fence = False
        for lineno, line in enumerate(
            read_source(path, root).splitlines(), start=1
        ):
            stripped = line.lstrip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue

            for match in REF_RE.finditer(line):
                raw = match.group(1)
                key = (path, lineno, raw)
                if key in seen:
                    continue
                seen.add(key)

                target = resolve_ref(path, raw, root, home)
                exists = target_exists(target, raw, root, home)
                if not exists:
                    source = path.relative_to(root)
                    missing.append(
                        f"MISSING: {safe_label(source.as_posix())}:{lineno} "
                        f"-> {safe_label(raw)}"
                    )

    if missing:
        print("\n".join(missing))
        return 1

    print("doc references: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
