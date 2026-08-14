#!/usr/bin/env python3
"""AI maintainability audit: project shape, context surface, verification surface,
decision artifacts, drift markers, hotspot ownership, markdown links.

Run as: python3 check_maintainability.py [ROOT] [summary|deep]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.parse
from collections import Counter
from pathlib import Path


# Mechanical definitions (excluded dirs, source extensions, marker regex,
# minified filter) are kept identical with skills/check/scripts/audit_signals.py
# by tests/python/test_auditor_alignment.py; thresholds stay per-product.
EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "dist", "build", ".next",
    "__pycache__", ".turbo", "target", ".venv", "venv", "vendor",
    "coverage", ".cache", ".parcel-cache", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", "Pods", "Carthage", ".swiftpm", ".gradle",
}

SOURCE_EXTS = {
    ".bash", ".c", ".cc", ".cpp", ".cs", ".css", ".go", ".h", ".hpp",
    ".html", ".java", ".js", ".jsx", ".kt", ".lua", ".m", ".mjs", ".mm",
    ".md", ".php", ".py", ".rb", ".rs", ".scss", ".sh", ".swift", ".ts",
    ".tsx", ".vue", ".yaml", ".yml", ".zsh",
}

MARKER_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
MARKER_EXAMPLE_RE = re.compile(r"\b(example|placeholder|fixture|marker|taxonomy)\b", re.IGNORECASE)
MINIFIED_RE = re.compile(r"\.min\.[a-z]+$", re.IGNORECASE)
MAKE_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*:(?![=])")
MAKE_CMD_RE = re.compile(r"\bmake\s+([A-Za-z0-9_.-]+)\b")
NPM_CMD_RE = re.compile(r"\b(?:npm|pnpm|yarn|bun)\s+run\s+([A-Za-z0-9:_-]+)\b")
COMMAND_LINE_RE = re.compile(r"^(?:make|npm|pnpm|yarn|bun)\s+")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
URL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
HOTSPOT_WORD_RE = re.compile(
    r"(hotspot|large file|ownership|owner|boundary|module|owned|owns|"
    r"负责|边界|模块|热点|大文件)",
    re.IGNORECASE,
)
VERIFICATION_WORD_RE = re.compile(
    r"(verification|verify|test|check|make\s+\w+|pytest|go test|cargo test|"
    r"npm test|npm run|pnpm|yarn|swift test|xcodebuild|验证|测试)",
    re.IGNORECASE,
)
MAX_TEXT_BYTES = 2_000_000
MAX_MIRROR_DIGEST_BYTES = 16_000_000


# The file-walk helpers below are deliberately duplicated in
# skills/check/scripts/audit_signals.py. Both scripts ship standalone
# (see packaging.allowlist) and run inside an arbitrary target project, so
# they import only stdlib. Do not hoist them into a shared scripts/
# module: it is dev-only, not on the ship allowlist, and would couple a
# standalone tool to the install layout.
def rel(path: Path, root: Path) -> str:
    try:
        value = path.resolve().relative_to(root).as_posix()
    except ValueError:
        value = path.as_posix()
    return safe_label(value)


def safe_label(value: str, limit: int = 500) -> str:
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        value = json.dumps(value, ensure_ascii=False)
    return value if len(value) <= limit else f"{value[: limit - 3]}..."


def is_excluded(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts if path.is_absolute() else path.parts
    if any(part in EXCLUDED_DIRS for part in parts):
        return True
    return bool(MINIFIED_RE.search(path.name))


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
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                return False
        return current.is_dir()
    except OSError:
        return False


def is_safe_repo_reference(path: Path, root: Path) -> bool:
    """Allow documentation symlinks only when their final target stays in-repo."""
    try:
        path.relative_to(root)
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve())
        return resolved.is_file() or resolved.is_dir()
    except (OSError, RuntimeError, ValueError):
        return False


def read_text(path: Path, root: Path, limit: int | None = None) -> str:
    if not is_repo_file(path, root):
        return ""
    byte_limit = limit or MAX_TEXT_BYTES
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
    except OSError:
        return ""
    try:
        chunks: list[bytes] = []
        remaining = byte_limit
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


def file_digest(path: Path, root: Path) -> tuple[int, bytes] | None:
    """Hash a stable regular file without trusting a shared prefix."""
    if not is_repo_file(path, root):
        return None
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
    except OSError:
        return None
    try:
        before = os.fstat(descriptor)
        if before.st_size > MAX_MIRROR_DIGEST_BYTES:
            return None
        digest = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, 65_536)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(descriptor)
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            return None
        return before.st_size, digest.digest()
    except OSError:
        return None
    finally:
        os.close(descriptor)


def iter_files(root: Path) -> list[Path]:
    try:
        proc = subprocess.run(
            [
                "git",
                "-c",
                "core.fsmonitor=false",
                "-C",
                str(root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout:
            files = []
            for raw_path in proc.stdout.split(b"\0"):
                if not raw_path:
                    continue
                path = root / os.fsdecode(raw_path)
                if is_repo_file(path, root) and not is_excluded(path, root):
                    files.append(path)
            return files
    except OSError:
        pass

    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = [
            name for name in dirnames
            if name not in EXCLUDED_DIRS and is_repo_dir(current / name, root)
        ]
        if is_excluded(current, root):
            continue
        for filename in filenames:
            path = current / filename
            if is_repo_file(path, root) and not is_excluded(path, root):
                files.append(path)
    return files


def collapse_generated_mirrors(
    files: list[Path], root: Path
) -> tuple[list[Path], int, list[str], list[str]]:
    """Fold byte-identical Codex plugin mirrors into their source files."""
    file_set = set(files)
    digests: dict[Path, tuple[int, bytes] | None] = {}

    def digest(path: Path) -> tuple[int, bytes] | None:
        if path not in digests:
            digests[path] = file_digest(path, root)
        return digests[path]

    logical: list[Path] = []
    collapsed = 0
    drifted: list[str] = []
    coverage_gaps: list[str] = []
    for path in files:
        try:
            parts = path.relative_to(root).parts
        except ValueError:
            logical.append(path)
            continue
        source: Path | None = None
        if len(parts) >= 4 and parts[0] == "plugins" and parts[2] in {"skills", "rules"}:
            source = root.joinpath(*parts[2:])
        if source is not None and source in file_set:
            mirror_digest = digest(path)
            source_digest = digest(source)
            if mirror_digest is None or source_digest is None:
                coverage_gaps.append(
                    f"{rel(path, root)} -> {rel(source, root)}"
                )
            elif mirror_digest == source_digest:
                collapsed += 1
                continue
            else:
                drifted.append(f"{rel(path, root)} -> {rel(source, root)}")
        logical.append(path)
    return logical, collapsed, drifted, coverage_gaps


def line_count(path: Path, root: Path) -> int:
    if not is_repo_file(path, root):
        return 0
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags), "rb") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def print_list(items: list[str], empty: str = "(none)", limit: int | None = None) -> None:
    shown = items if limit is None else items[:limit]
    if not shown:
        print(f"  {empty}")
        return
    for item in shown:
        print(f"  {safe_label(item)}")
    if limit is not None and len(items) > limit:
        print(f"  ... {len(items) - limit} more")


def instruction_paths(root: Path) -> list[Path]:
    candidates = [
        root / "AGENTS.md",
        root / "CLAUDE.md",
        root / ".github" / "copilot-instructions.md",
        root / "GEMINI.md",
    ]
    instructions_dir = root / ".github" / "instructions"
    if is_repo_dir(instructions_dir, root):
        candidates.extend(sorted(instructions_dir.glob("*.md")))
    rules_dir = root / ".claude" / "rules"
    if is_repo_dir(rules_dir, root):
        candidates.extend(sorted(rules_dir.glob("*.md")))
    return [
        path for path in candidates
        if is_repo_file(path, root) and not is_excluded(path, root)
    ]


def find_text_signal(paths: list[Path], patterns: list[str], root: Path) -> bool:
    regexes = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for path in paths:
        text = read_text(path, root, 200_000)
        if any(regex.search(text) for regex in regexes):
            return True
    return False


def parse_makefile(root: Path) -> tuple[set[str], list[str]]:
    makefile = root / "Makefile"
    targets: set[str] = set()
    commands: list[str] = []
    if not is_repo_file(makefile, root):
        return targets, commands
    for line in read_text(makefile, root).splitlines():
        match = MAKE_RE.match(line)
        if not match:
            continue
        target = match.group(1)
        if target.startswith("."):
            continue
        targets.add(target)
        if re.search(r"(test|check|lint|type|build|package|verify|smoke)", target, re.IGNORECASE):
            commands.append(f"make {target}")
    return targets, commands


def parse_package_json(root: Path) -> tuple[set[str], list[str]]:
    package = root / "package.json"
    script_names: set[str] = set()
    commands: list[str] = []
    if not is_repo_file(package, root):
        return script_names, commands
    try:
        data = json.loads(read_text(package, root))
    except json.JSONDecodeError:
        return script_names, commands
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return script_names, commands
    for name in sorted(scripts):
        script_names.add(name)
        if re.search(r"(test|check|lint|type|build|verify)", name, re.IGNORECASE):
            commands.append(f"npm run {name}")
    return script_names, commands


def parse_ci_commands(root: Path) -> list[str]:
    workflows_dir = root / ".github" / "workflows"
    workflows = (
        sorted(path for path in workflows_dir.glob("*.yml") if is_repo_file(path, root))
        if is_repo_dir(workflows_dir, root) else []
    )
    workflows += (
        sorted(path for path in workflows_dir.glob("*.yaml") if is_repo_file(path, root))
        if is_repo_dir(workflows_dir, root) else []
    )
    commands: list[str] = []
    for workflow in workflows:
        for raw in read_text(workflow, root).splitlines():
            line = raw.strip()
            if line.startswith("- run:"):
                command = line.split("- run:", 1)[1].strip().strip("'\"")
            elif line.startswith("run:"):
                command = line.split("run:", 1)[1].strip().strip("'\"")
            else:
                continue
            if command and command != "|":
                commands.append(f"{rel(workflow, root)}: {command}")
    return commands


def scan_markdown_links(files: list[Path], root: Path) -> list[str]:
    missing: list[str] = []
    markdown_files = [path for path in files if path.suffix.lower() == ".md"]
    for path in markdown_files:
        for lineno, line in enumerate(read_text(path, root).splitlines(), 1):
            for raw in MARKDOWN_LINK_RE.findall(line):
                target = raw.strip().split()[0].strip("<>")
                if not target or target.startswith("#") or URL_RE.match(target):
                    continue
                target = urllib.parse.unquote(target.split("#", 1)[0])
                if not target:
                    continue
                # A leading slash is a site-root route, not a filesystem-relative
                # Markdown reference. Its validity belongs to the site's route or
                # link checker; treating it as /path/on/the/audit-host is a false
                # broken-doc finding.
                if target.startswith("/"):
                    continue
                full = path.parent / target
                if not is_safe_repo_reference(full, root):
                    missing.append(f"{rel(path, root)}:{lineno} -> {target}")
    return missing


def verification_surface(
    root: Path, instruction_files: list[Path]
) -> tuple[list[str], list[str], set[str], set[str]]:
    make_targets, make_commands = parse_makefile(root)
    package_scripts, package_commands = parse_package_json(root)
    commands = make_commands + package_commands + parse_ci_commands(root)

    if is_repo_file(root / "Cargo.toml", root):
        commands.extend(["cargo test", "cargo check"])
    if is_repo_file(root / "go.mod", root):
        commands.append("go test ./...")
    if is_repo_file(root / "pyproject.toml", root) or is_repo_file(root / "pytest.ini", root):
        commands.append("pytest")
    if is_repo_file(root / "pom.xml", root):
        commands.append("mvn test")
    if is_repo_file(root / "deno.json", root) or is_repo_file(root / "deno.jsonc", root):
        commands.append("deno test")

    missing: list[str] = []
    for path in instruction_files:
        text = read_text(path, root, 200_000)
        snippets: list[str] = []
        for raw_line in text.splitlines():
            snippets.extend(re.findall(r"`([^`]+)`", raw_line))
            stripped = raw_line.strip().strip("`")
            if COMMAND_LINE_RE.match(stripped):
                snippets.append(stripped)
        for snippet in snippets:
            for target in MAKE_CMD_RE.findall(snippet):
                if target not in make_targets:
                    missing.append(f"{rel(path, root)} references missing make target: {target}")
            for script in NPM_CMD_RE.findall(snippet):
                if script not in package_scripts:
                    missing.append(f"{rel(path, root)} references missing package script: {script}")

    unique_commands = list(dict.fromkeys(commands))
    unique_missing = list(dict.fromkeys(missing))
    return unique_commands, unique_missing, make_targets, package_scripts


def hotspot_ownership_surface(
    records: list[tuple[int, int, Path]],
    instruction_files: list[Path],
    mode: str,
    root: Path,
) -> tuple[str, list[str], list[str], list[str]]:
    if not records:
        return "PASS", [], [], []

    snippets: list[str] = []
    for path in instruction_files:
        snippets.append(f"\n# {rel(path, root)}\n{read_text(path, root, 200_000)}")
    instruction_text = "\n".join(snippets)
    lower_text = instruction_text.lower()
    instruction_lines = instruction_text.splitlines()

    documented: list[str] = []
    missing: list[str] = []
    for lines, _size, path in records:
        relative = rel(path, root)
        relative_path = Path(relative)
        lower_parts = tuple(part.lower() for part in relative_path.parts)
        if any(part in {"test", "tests", "spec", "specs", "fixtures"} for part in lower_parts):
            continue
        lower_name = relative_path.name.lower()
        if re.search(r"(?:^|[._-])(?:test|tests|spec|specs)(?:[._-]|$)", lower_name):
            continue

        relative_lower = relative.lower()
        candidates = [relative_lower]
        # A hotspot entry commonly owns a directory or subsystem rather than
        # repeating every large filename. Match the deepest documented parent,
        # but do not accept a single top-level directory as useful ownership.
        parent = relative_path.parent
        while len(parent.parts) >= 2:
            candidates.append(parent.as_posix().lower().rstrip("/") + "/")
            parent = parent.parent
        indices: list[int] = []
        for candidate in candidates:
            pattern = re.compile(
                rf"(?<![a-z0-9_.-]){re.escape(candidate)}(?=$|[\s`'\"),:;])"
            )
            indices.extend(match.start() for match in pattern.finditer(lower_text))

        if not indices:
            missing.append(f"{relative} lines={lines} reason=not mentioned in agent instructions")
            continue

        saw_hotspot_context = False
        saw_verification_context = False
        has_documented_entry = False
        for index in indices:
            window = lower_text[max(0, index - 700): index + len(relative_lower) + 700]
            line_no = lower_text[:index].count("\n")
            local_lines = instruction_lines[max(0, line_no - 1): line_no + 4]
            local_context = "\n".join(local_lines)
            section_heading = ""
            for prior_line in reversed(instruction_lines[: line_no + 1]):
                if prior_line.lstrip().startswith("#"):
                    section_heading = prior_line
                    break
            has_hotspot_context = bool(
                HOTSPOT_WORD_RE.search(window)
                or HOTSPOT_WORD_RE.search(section_heading)
            )
            has_verification_context = bool(VERIFICATION_WORD_RE.search(local_context))
            saw_hotspot_context = saw_hotspot_context or has_hotspot_context
            saw_verification_context = saw_verification_context or has_verification_context
            if has_hotspot_context and has_verification_context:
                has_documented_entry = True
                break

        if has_documented_entry:
            documented.append(f"{relative} lines={lines}")
        else:
            reasons = []
            if not saw_hotspot_context:
                reasons.append("missing ownership/boundary context")
            if not saw_verification_context:
                reasons.append("missing verification context")
            if saw_hotspot_context and saw_verification_context:
                reasons.append("ownership and verification are not in the same hotspot entry")
            missing.append(f"{relative} lines={lines} reason={'; '.join(reasons)}")

    findings: list[str] = []
    if missing:
        findings.append("large source files lack hotspot ownership or verification map")
    return ("WARN" if missing else "PASS"), documented, missing, findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="Repo root (default: cwd)")
    parser.add_argument(
        "mode", nargs="?", default="summary", choices=("summary", "deep"),
        help="Output detail level",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    mode = args.mode

    if not root.is_dir():
        print(f"Repo root not found: {safe_label(root.as_posix())}", file=sys.stderr)
        return 2

    files = iter_files(root)
    (
        logical_files,
        generated_mirror_files_collapsed,
        generated_mirror_drift,
        generated_mirror_coverage_gaps,
    ) = collapse_generated_mirrors(files, root)
    tracked_count = len(files)
    extensions = Counter(path.suffix.lower() or "(none)" for path in files)
    detected_manifests = [
        name
        for name in [
            "Makefile", "package.json", "Cargo.toml", "go.mod", "pyproject.toml",
            "pytest.ini", "pom.xml", "deno.json", "deno.jsonc",
        ]
        if is_repo_file(root / name, root)
    ]
    workflows_dir = root / ".github" / "workflows"
    workflow_count = 0
    if is_repo_dir(workflows_dir, root):
        workflow_count = sum(
            1
            for path in list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
            if is_repo_file(path, root)
        )
    if workflow_count:
        detected_manifests.append(f".github/workflows ({workflow_count})")

    source_files = [path for path in logical_files if path.suffix.lower() in SOURCE_EXTS]
    source_stats: list[tuple[int, int, Path]] = []
    for path in source_files:
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        source_stats.append((line_count(path, root), size, path))
    source_stats.sort(key=lambda item: (item[0], item[1]), reverse=True)

    dir_counts: Counter[str] = Counter()
    for path in files:
        relative_parts = Path(rel(path, root)).parts
        top = relative_parts[0] if len(relative_parts) > 1 else "."
        dir_counts[top] += 1

    instruction_files = instruction_paths(root)
    project_map = find_text_signal(
        instruction_files,
        [r"repository map", r"project map", r"repo map", r"\bproject\b", r"目录", r"仓库", r"结构"],
        root,
    )
    instruction_verification = find_text_signal(
        instruction_files,
        [r"verification", r"test plan", r"make test", r"npm test", r"pytest", r"cargo test", r"验证", r"测试"],
        root,
    )
    boundaries = find_text_signal(
        instruction_files,
        [r"not for", r"do not", r"non-?goals?", r"scope", r"boundar", r"never", r"avoid", r"边界", r"非目标", r"不要"],
        root,
    )
    commands, missing_references, make_targets, _package_scripts = verification_surface(root, instruction_files)
    stable_make_targets = sorted(make_targets & {"check", "test", "verify"})
    wrapper_warnings: list[str] = []
    if len(commands) >= 2 and is_repo_file(root / "Makefile", root) and not stable_make_targets:
        wrapper_warnings.append(
            "multiple verification commands discovered but Makefile lacks check/test/verify wrapper"
        )

    decision_artifacts = {
        "docs_dir": is_repo_dir(root / "docs", root),
        "specs_dir": is_repo_dir(root / "specs", root),
        "specify_dir": is_repo_dir(root / ".specify", root),
        "handoff_md": any(
            path.name.upper() == "HANDOFF.MD" and is_repo_file(path, root)
            for path in root.glob("*.md")
        ),
        "changelog": any(
            path.name.upper().startswith("CHANGELOG") and is_repo_file(path, root)
            for path in root.glob("*")
        ),
        "issue_templates": is_repo_dir(root / ".github" / "ISSUE_TEMPLATE", root),
        "pr_template": any(
            is_repo_file(path, root)
            for path in [
                root / ".github" / "pull_request_template.md",
                root / ".github" / "PULL_REQUEST_TEMPLATE.md",
            ]
        ),
    }

    todo_counts: Counter[str] = Counter()
    todo_total = 0
    fixture_marker_lines_ignored = 0
    for path in source_files:
        text = read_text(path, root, 200_000)
        # Count marker-bearing lines, not marker words. Documentation often names
        # the full marker family in one rule line; treating that as four issues
        # makes the checker flag itself instead of real open-task piles.
        relative = Path(rel(path, root))
        is_fixture = (
            any(part in {"test", "tests", "spec", "specs", "fixtures"} for part in relative.parts)
            or bool(re.search(r"(?:^|[._-])(?:test|tests|spec|specs)(?:[._-]|$)", relative.name.lower()))
        )
        count = 0
        for line in text.splitlines():
            if not MARKER_RE.search(line):
                continue
            marker_taxonomy = all(marker in line.upper() for marker in ("TODO", "FIXME", "HACK", "XXX"))
            documented_example = (
                path.suffix.lower() == ".md" and MARKER_EXAMPLE_RE.search(line)
            )
            if is_fixture or marker_taxonomy or documented_example:
                fixture_marker_lines_ignored += 1
                continue
            count += 1
        if count:
            todo_counts[rel(path, root)] += count
            todo_total += count

    large_line_limit = 1200 if mode == "summary" else 800
    large_file_records = [
        (lines, size, path) for lines, size, path in source_stats if lines >= large_line_limit
    ]
    large_files = [f"{rel(path, root)} lines={lines} bytes={size}" for lines, size, path in large_file_records]
    todo_hotspots = [
        f"{path} markers={count}" for path, count in todo_counts.most_common(8 if mode == "deep" else 5)
    ]

    doc_ref_status = "unavailable"
    doc_ref_detail = ""
    checker = Path(__file__).with_name("check_doc_refs.py")
    if checker.is_file():
        proc = subprocess.run(
            [sys.executable, "-I", str(checker), str(root)],
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        doc_ref_status = "pass" if proc.returncode == 0 else "fail"
        if proc.stdout.strip():
            first_lines = proc.stdout.strip().splitlines()[:8]
            doc_ref_detail = " | ".join(first_lines)

    has_instruction_surface = bool(instruction_files)
    has_command_surface = bool(commands)
    context_warnings: list[str] = []
    verification_warnings: list[str] = []
    drift_warnings: list[str] = []

    if not has_instruction_surface:
        context_warnings.append("no agent instruction surface")
    if has_instruction_surface and not project_map:
        context_warnings.append("instructions lack project map")
    if has_instruction_surface and not instruction_verification:
        context_warnings.append("instructions lack verification guidance")
    if has_instruction_surface and not boundaries:
        context_warnings.append("instructions lack scope/boundary language")
    if not has_command_surface:
        verification_warnings.append("no executable verification command discovered")
    if missing_references:
        verification_warnings.append("instruction references missing commands")
    if todo_total >= (50 if mode == "summary" else 25):
        drift_warnings.append("TODO/FIXME/HACK/XXX markers are concentrated")
    if generated_mirror_drift:
        drift_warnings.append("generated mirrors differ from their source files")
    if generated_mirror_coverage_gaps:
        drift_warnings.append("generated mirror comparison exceeded the bounded digest surface")
    hotspot_status, documented_hotspots, missing_hotspot_ownership, hotspot_findings = (
        hotspot_ownership_surface(large_file_records, instruction_files, mode, root)
    )
    if hotspot_status == "WARN":
        drift_warnings.extend(hotspot_findings)
    if doc_ref_status == "fail":
        drift_warnings.append("broken documentation references")

    markdown_missing: list[str] = []
    markdown_link_status = "SKIPPED"
    if mode == "deep":
        markdown_missing = scan_markdown_links(files, root)
        markdown_link_status = "WARN" if markdown_missing else "PASS"
        if markdown_missing:
            drift_warnings.append("broken Markdown links")

    context_status = "FAIL" if not has_instruction_surface else ("WARN" if context_warnings else "PASS")
    verification_status = "FAIL" if not has_command_surface else ("WARN" if verification_warnings else "PASS")
    decision_status = "PASS"
    wrapper_status = "WARN" if wrapper_warnings else "PASS"
    drift_status = "WARN" if drift_warnings else "PASS"

    if context_status == "FAIL" or verification_status == "FAIL" or doc_ref_status == "fail":
        overall = "FAIL"
    elif "WARN" in {
        context_status, verification_status, decision_status, wrapper_status,
        drift_status, markdown_link_status, hotspot_status,
    }:
        overall = "WARN"
    else:
        overall = "PASS"

    top_ext = [f"{ext} files={count}" for ext, count in extensions.most_common(10)]
    largest_sources = [
        f"{rel(path, root)} lines={lines} bytes={size}"
        for lines, size, path in source_stats[: (10 if mode == "deep" else 5)]
    ]
    largest_dirs = [f"{directory} files={count}" for directory, count in dir_counts.most_common(8)]

    print("=== PROJECT SHAPE ===")
    print(f"maintainability_status: {overall}")
    print(f"mode: {mode}")
    print(f"tracked_files: {tracked_count}")
    print(f"generated_mirror_files_collapsed: {generated_mirror_files_collapsed}")
    print(f"generated_mirror_files_drifted: {len(generated_mirror_drift)}")
    print(f"generated_mirror_comparison_gaps: {len(generated_mirror_coverage_gaps)}")
    print("generated_mirror_drift:")
    print_list(generated_mirror_drift, limit=10)
    print("generated_mirror_coverage_gaps:")
    print_list(generated_mirror_coverage_gaps, limit=10)
    print("top_extensions:")
    print_list(top_ext)
    print("largest_source_files:")
    print_list(largest_sources)
    print("largest_directories:")
    print_list(largest_dirs)

    print("=== AI CONTEXT SURFACE ===")
    print(f"context_status: {context_status}")
    print(f"AGENTS.md: {'yes' if is_repo_file(root / 'AGENTS.md', root) else 'no'}")
    print(f"CLAUDE.md: {'yes' if is_repo_file(root / 'CLAUDE.md', root) else 'no'}")
    print(f".github/copilot-instructions.md: {'yes' if is_repo_file(root / '.github' / 'copilot-instructions.md', root) else 'no'}")
    github_instruction_count = (
        sum(
            1
            for path in (root / ".github" / "instructions").glob("*.md")
            if is_repo_file(path, root)
        )
        if is_repo_dir(root / ".github" / "instructions", root) else 0
    )
    print(f".github/instructions/*.md: {github_instruction_count}")
    print(f"GEMINI.md: {'yes' if is_repo_file(root / 'GEMINI.md', root) else 'no'}")
    print(f"project_map: {'yes' if project_map else 'no'}")
    print(f"verification_guidance: {'yes' if instruction_verification else 'no'}")
    print(f"boundary_guidance: {'yes' if boundaries else 'no'}")
    print("context_findings:")
    print_list(context_warnings)
    print("instruction_files:")
    print_list([rel(path, root) for path in instruction_files])

    print("=== VERIFICATION SURFACE ===")
    print(f"verification_status: {verification_status}")
    print("detected_manifests:")
    print_list(detected_manifests)
    print("commands:")
    print_list(commands, limit=12 if mode == "summary" else None)
    print("missing_referenced_commands:")
    print_list(missing_references, limit=10 if mode == "summary" else None)
    print("verification_findings:")
    print_list(verification_warnings)

    print("=== VERIFICATION WRAPPER SURFACE ===")
    print(f"wrapper_status: {wrapper_status}")
    print(f"makefile_present: {'yes' if is_repo_file(root / 'Makefile', root) else 'no'}")
    print("stable_make_targets:")
    print_list([f"make {target}" for target in stable_make_targets])
    print("wrapper_findings:")
    print_list(wrapper_warnings)

    print("=== DECISION ARTIFACTS ===")
    print(f"decision_artifacts_status: {decision_status}")
    for key, value in decision_artifacts.items():
        print(f"{key}: {'yes' if value else 'no'}")

    print("=== DRIFT MARKERS ===")
    print(f"drift_status: {drift_status}")
    print(f"todo_markers: {todo_total}")
    print(f"fixture_or_instruction_marker_lines_ignored: {fixture_marker_lines_ignored}")
    print("todo_hotspots:")
    print_list(todo_hotspots)
    print("large_source_files:")
    print_list(large_files[: (10 if mode == "deep" else 5)])
    print(f"broken_doc_references: {doc_ref_status}")
    if doc_ref_detail and (mode == "deep" or doc_ref_status == "fail"):
        print(f"broken_doc_reference_detail: {safe_label(doc_ref_detail)}")
    print("drift_findings:")
    print_list(drift_warnings)

    print("=== HOTSPOT OWNERSHIP SURFACE ===")
    print(f"hotspot_ownership_status: {hotspot_status}")
    print(f"large_hotspot_threshold_lines: {large_line_limit}")
    print("documented_hotspots:")
    print_list(documented_hotspots)
    print("missing_hotspot_ownership:")
    print_list(missing_hotspot_ownership)
    print("hotspot_ownership_findings:")
    print_list(hotspot_findings)

    print("=== MARKDOWN LINK SURFACE ===")
    print(f"markdown_link_status: {markdown_link_status}")
    print("missing_markdown_links:")
    if mode == "deep":
        print_list(markdown_missing, limit=20)
    else:
        print("  (skipped: deep mode only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
