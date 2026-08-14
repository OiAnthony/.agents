#!/usr/bin/env python3
"""Print one bounded SKILL.md description, including YAML block scalars."""

from __future__ import annotations

import argparse
from pathlib import Path


MAX_BYTES = 1_048_576
MAX_DESCRIPTION_CHARS = 4_000


def parse_description(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    index = 1
    while index < len(lines):
        line = lines[index]
        if line.strip() == "---":
            return ""
        if not line.startswith("description:"):
            index += 1
            continue
        raw = line.split(":", 1)[1].strip()
        if raw not in {">", ">-", ">+", "|", "|-", "|+"}:
            return raw.strip("\"'")[:MAX_DESCRIPTION_CHARS]
        index += 1
        chunks: list[str] = []
        while index < len(lines):
            continuation = lines[index]
            if continuation.strip() == "---" or (
                continuation and not continuation[0].isspace()
            ):
                break
            chunks.append(continuation.strip())
            index += 1
        return " ".join(chunk for chunk in chunks if chunk)[:MAX_DESCRIPTION_CHARS]
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        if args.path.stat().st_size > MAX_BYTES:
            return 2
        text = args.path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 2
    description = parse_description(text)
    if description:
        print(description)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
