#!/usr/bin/env python3
"""Summarize the agent-instruction surface for a project.

Inventories AGENTS.md / CLAUDE.md / Codex / Copilot / Gemini instruction files,
parses Codex config.toml for project trust + plugin/feature state (with sensitive
values redacted), and flags drift between Claude and Codex surfaces.

Run as: python3 check_agent_context.py [ROOT] [summary|deep]
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shlex
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

SENSITIVE_RE = re.compile(r"(api[_-]?key|token|secret|password|credential)", re.IGNORECASE)
PROJECT_RE = re.compile(r'^\[projects\."(.+)"\]\s*$')
TABLE_RE = re.compile(r'^\[([A-Za-z0-9_.@"\-/]+)\]\s*$')
OPERATIONAL_RULE_RE = re.compile(
    r"(Git Safety|Public Issue Replies|Investigation Honesty|Verification|Response Style|Commit|Security)",
    re.IGNORECASE,
)
CJK_CONTEXT_RE = re.compile(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]")
MAX_FILE_BYTES = 2_000_000
MAX_CONTEXT_PROJECT_FILES = 50_000
MAX_CONTEXT_MATCH_EVALUATIONS = 2_000_000
_AUDIT_ROOT: Optional[Path] = None
_AUDIT_HOME: Optional[Path] = None
_TRUSTED_SCRIPT_ROOT = Path(__file__).resolve().parent


def contained(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def sensitive_path(path: Path, home: Path) -> bool:
    for protected in (
        home / ".ssh",
        home / ".aws",
        home / ".gnupg",
        home / ".config" / "gh",
    ):
        if path == protected or contained(path, protected):
            return True
    for part in path.parts:
        lowered = part.lower()
        if lowered == "secrets":
            return True
        if "credential" in lowered:
            return True
        if lowered == ".env" or lowered.startswith(".env."):
            return True
    return False


def audit_scope(path: Path) -> Optional[Path]:
    absolute = path if path.is_absolute() else Path.cwd() / path
    for root in (_AUDIT_ROOT, _AUDIT_HOME, _TRUSTED_SCRIPT_ROOT):
        if root is not None and contained(absolute, root):
            return root
    return None


def resolve_audit_file(path: Path) -> Optional[Path]:
    scope = audit_scope(path)
    if scope is None:
        return None
    absolute = path if path.is_absolute() else Path.cwd() / path
    home = _AUDIT_HOME or Path.home().resolve()
    if any(ord(char) < 32 or ord(char) == 127 for char in str(absolute)):
        return None
    if sensitive_path(absolute, home):
        return None
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return None
    if not contained(resolved, scope) or sensitive_path(resolved, home):
        return None
    return resolved if resolved.is_file() else None


def resolve_audit_dir(path: Path) -> Optional[Path]:
    scope = audit_scope(path)
    if scope is None:
        return None
    absolute = path if path.is_absolute() else Path.cwd() / path
    home = _AUDIT_HOME or Path.home().resolve()
    if any(ord(char) < 32 or ord(char) == 127 for char in str(absolute)):
        return None
    if sensitive_path(absolute, home):
        return None
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return None
    if not contained(resolved, scope) or sensitive_path(resolved, home):
        return None
    return resolved if resolved.is_dir() else None


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


def read_bytes(path: Path, limit: Optional[int] = None) -> bytes:
    resolved = resolve_audit_file(path)
    if resolved is None:
        return b""
    byte_limit = limit or MAX_FILE_BYTES
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(resolved, flags)
    except OSError:
        return b""
    try:
        chunks: list[bytes] = []
        remaining = byte_limit
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)
    except OSError:
        return b""
    finally:
        os.close(descriptor)


def read(path: Path, limit: Optional[int] = None) -> str:
    return read_bytes(path, limit).decode("utf-8", errors="replace")


def yes(path: Path) -> str:
    return "yes" if resolve_audit_file(path) is not None else "no"


def print_list(
    title: str,
    items: list[str],
    empty: str = "(none)",
    limit: Optional[int] = None,
) -> None:
    print(f"{title}:")
    shown = items if limit is None else items[:limit]
    if not shown:
        print(f"  {empty}")
        return
    for item in shown:
        print(f"  {safe_label(item)}")
    if limit is not None and len(items) > limit:
        print(f"  ... {len(items) - limit} more")


def load_json(path: Path) -> tuple[Optional[object], Optional[str]]:
    if resolve_audit_file(path) is None:
        return None, None
    try:
        return json.loads(read(path)), None
    except json.JSONDecodeError as exc:
        return None, f"{path.name}: invalid JSON at line {exc.lineno}"


def redact_sensitive_entries(value: object, prefix: str = "") -> list[str]:
    entries: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            if SENSITIVE_RE.search(str(key)):
                entries.append(f"{safe_label(child_prefix)}=[REDACTED]")
                continue
            entries.extend(redact_sensitive_entries(child, child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            entries.extend(redact_sensitive_entries(child, f"{prefix}[{index}]"))
    return entries


def string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [
            safe_label(str(item)) if not SENSITIVE_RE.search(str(item)) else "[REDACTED]"
            for item in value
        ]
    if isinstance(value, dict):
        return sorted(safe_label(str(key)) for key in value)
    if isinstance(value, str):
        return ["[REDACTED]" if SENSITIVE_RE.search(value) else safe_label(value)]
    return []


def skill_root_count(path: Path, include_root_md: bool) -> int:
    directory = resolve_audit_dir(path)
    if directory is None:
        return 0
    count = sum(
        1
        for candidate in directory.rglob("SKILL.md")
        if resolve_audit_file(candidate) is not None
    )
    if include_root_md:
        count += sum(
            1
            for candidate in directory.glob("*.md")
            if candidate.name != "SKILL.md" and resolve_audit_file(candidate) is not None
        )
    return count


def same_physical_file(left: Path, right: Path) -> bool:
    left_resolved = resolve_audit_file(left)
    right_resolved = resolve_audit_file(right)
    if left_resolved is None or right_resolved is None:
        return False
    try:
        return left_resolved.samefile(right_resolved)
    except OSError:
        return False


def unique_physical_files(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[tuple[int, int]] = set()
    for path in paths:
        canonical = resolve_audit_file(path)
        if canonical is None:
            continue
        try:
            stat = canonical.stat()
        except OSError:
            continue
        identity = (stat.st_dev, stat.st_ino)
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(path)
    return unique


def project_instruction_files(root: Path) -> list[Path]:
    files = [
        root / "AGENTS.md",
        root / "CLAUDE.md",
        root / ".github" / "copilot-instructions.md",
        root / "GEMINI.md",
    ]
    instructions_dir = root / ".github" / "instructions"
    if resolve_audit_dir(instructions_dir) is not None:
        files.extend(sorted(instructions_dir.glob("*.md")))
    return unique_physical_files(files)


def claude_delegates_to_agents(path: Path) -> bool:
    text = read(path, 20_000)
    if not text:
        return False
    meaningful = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return any("AGENTS.md" in line for line in meaningful)


def has_operational_rules(path: Path) -> bool:
    text = read(path, 40_000)
    if not text:
        return False
    return len(set(m.group(1).lower() for m in OPERATIONAL_RULE_RE.finditer(text))) >= 2


def looks_identity_only(path: Path) -> bool:
    text = read(path, 40_000)
    if not text:
        return False
    return "nian-identity:start" in text and not has_operational_rules(path)


def rule_paths(text: str) -> list[str]:
    if not text.startswith("---"):
        return []
    lines = text.splitlines()
    paths: list[str] = []
    in_paths = False
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if stripped == "paths:":
            in_paths = True
            continue
        if in_paths and stripped.startswith("-"):
            value = stripped[1:].strip().strip('"\'')
            if value:
                paths.append(value)
            continue
        if in_paths and stripped and not line.startswith((" ", "\t")):
            in_paths = False
    return paths


def selector_pattern(selector: str) -> re.Pattern[str]:
    """Compile Claude's slash-aware * / ** path glob subset."""
    pattern = ["^"]
    index = 0
    while index < len(selector):
        char = selector[index]
        if char == "*":
            if index + 1 < len(selector) and selector[index + 1] == "*":
                if index + 2 < len(selector) and selector[index + 2] == "/":
                    pattern.append("(?:.*/)?")
                    index += 3
                else:
                    pattern.append(".*")
                    index += 2
            else:
                pattern.append("[^/]*")
                index += 1
        elif char == "?":
            pattern.append("[^/]")
            index += 1
        else:
            pattern.append(re.escape(char))
            index += 1
    pattern.append("$")
    return re.compile("".join(pattern))


def context_units(text: str) -> int:
    """Conservative language-neutral context estimate for rule budgeting."""
    cjk_characters = len(CJK_CONTEXT_RE.findall(text))
    non_cjk_words = len(CJK_CONTEXT_RE.sub(" ", text).split())
    return non_cjk_words + cjk_characters


def project_relative_files(root: Path) -> tuple[list[str], bool]:
    excluded = {
        ".git", ".hg", ".svn", "node_modules", "dist", "build", ".next",
        "__pycache__", ".venv", "venv", "target", "coverage", ".cache",
        ".pytest_cache", ".mypy_cache", ".ruff_cache", "Pods", "Carthage",
        ".swiftpm", ".gradle",
    }
    paths: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in excluded and not (current / name).is_symlink()
        )
        for filename in sorted(filenames):
            path = current / filename
            if path.is_symlink() or not path.is_file():
                continue
            try:
                relative = path.relative_to(root).as_posix()
            except ValueError:
                continue
            if any(ord(char) < 32 or ord(char) == 127 for char in relative):
                continue
            paths.append(relative)
            if len(paths) >= MAX_CONTEXT_PROJECT_FILES:
                return paths, True
    return paths, False


def summarize_rule_context(
    rule_roots: list[tuple[str, Path]], root: Path
) -> tuple[str, list[str]]:
    path_counts: Counter[str] = Counter()
    path_words: Counter[str] = Counter()
    path_units: Counter[str] = Counter()
    rule_entries: list[tuple[str, int, int, list[re.Pattern[str]]]] = []
    scoped_files = 0
    scoped_words = 0
    scoped_units = 0
    always_files = 0
    always_words = 0
    always_units = 0
    rule_files: list[tuple[str, Path]] = []
    seen_rules: set[Path] = set()
    for scope, rule_root in rule_roots:
        if resolve_audit_dir(rule_root) is None:
            continue
        for path in sorted(rule_root.glob("*.md")):
            canonical = resolve_audit_file(path)
            if canonical is None or canonical in seen_rules:
                continue
            seen_rules.add(canonical)
            rule_files.append((scope, path))
    selector_count = 0
    for scope, path in rule_files:
        text = read(path)
        words = len(text.split())
        units = context_units(text)
        paths = rule_paths(text)
        if paths:
            scoped_files += 1
            scoped_words += words
            scoped_units += units
            selector_count += len(paths)
            rule_entries.append(
                (
                    f"{scope}:{path.name}",
                    words,
                    units,
                    [selector_pattern(selector) for selector in paths],
                )
            )
            for selector in paths:
                path_counts[selector] += 1
                path_words[selector] += words
                path_units[selector] += units
        else:
            always_files += 1
            always_words += words
            always_units += units
    ranked = sorted(
        path_counts,
        key=lambda selector: (path_units[selector], path_counts[selector], selector),
        reverse=True,
    )
    effective_loads: list[tuple[int, int, str, list[str]]] = []
    project_files, project_files_truncated = project_relative_files(root)
    match_evaluations = 0
    match_budget_exhausted = False
    for relative in project_files:
        matching: list[tuple[str, int, int]] = []
        for name, words, units, patterns in rule_entries:
            matched = False
            for pattern in patterns:
                if match_evaluations >= MAX_CONTEXT_MATCH_EVALUATIONS:
                    match_budget_exhausted = True
                    break
                match_evaluations += 1
                if pattern.fullmatch(relative):
                    matched = True
                    break
            if match_budget_exhausted:
                break
            if matched:
                matching.append((name, words, units))
        if match_budget_exhausted:
            break
        if matching:
            effective_loads.append(
                (
                    sum(units for _, _, units in matching),
                    sum(words for _, words, _ in matching),
                    relative,
                    [name for name, _, _ in matching],
                )
            )
    effective_loads.sort(key=lambda item: (item[0], item[2]), reverse=True)
    findings: list[str] = []
    oversized_files: list[str] = []
    for scope, path in rule_files:
        text = read(path)
        words = len(text.split())
        units = context_units(text)
        if units > 5_000:
            oversized_files.append(
                f"{scope}:{path.name} words={words} context_units={units}"
            )
    if always_units > 5_000:
        findings.append(
            "always-loaded rules exceed 5000 context units: "
            f"words={always_words} context_units={always_units}"
        )
    if ranked and path_units[ranked[0]] > 10_000:
        findings.append(
            "one path selector loads more than 10000 context units: "
            f"{ranked[0]} words={path_words[ranked[0]]} "
            f"context_units={path_units[ranked[0]]}"
        )
    if effective_loads and effective_loads[0][0] > 10_000:
        units, words, relative, matching_rules = effective_loads[0]
        findings.append(
            "one project path loads more than 10000 effective context units: "
            f"{relative} words={words} context_units={units} "
            f"rules={','.join(matching_rules)}"
        )
    if oversized_files:
        findings.append("oversized path rules: " + ", ".join(oversized_files[:5]))
    if project_files_truncated:
        findings.append(
            f"project path inventory exceeded {MAX_CONTEXT_PROJECT_FILES} files"
        )
    if match_budget_exhausted:
        findings.append(
            "path rule matching exceeded "
            f"{MAX_CONTEXT_MATCH_EVALUATIONS} evaluations"
        )
    status = "WARN" if findings else "PASS"
    lines = [
        "=== PATH-SCOPED CONTEXT ===",
        f"path_context_status: {status}",
        f"path_context_rule_roots_scanned: {len(rule_roots)}",
        f"path_context_selectors: {selector_count}",
        f"path_context_project_files: {len(project_files)}",
        f"path_context_project_files_truncated: {'yes' if project_files_truncated else 'no'}",
        f"path_context_match_evaluations: {match_evaluations}",
        f"path_context_match_budget_exhausted: {'yes' if match_budget_exhausted else 'no'}",
        f"path_scoped_rule_files: {scoped_files}",
        f"path_scoped_rule_words: {scoped_words}",
        f"path_scoped_rule_context_units: {scoped_units}",
        f"always_loaded_rule_files: {always_files}",
        f"always_loaded_rule_words: {always_words}",
        f"always_loaded_rule_context_units: {always_units}",
        "largest_path_triggers:",
    ]
    if not ranked:
        lines.append("  (none)")
    else:
        for selector in ranked[:10]:
            lines.append(
                f"  selector={safe_label(selector)} files={path_counts[selector]} "
                f"combined_words={path_words[selector]} "
                f"combined_context_units={path_units[selector]}"
            )
    lines.append("largest_effective_paths:")
    if not effective_loads:
        lines.append("  (none)")
    else:
        for units, words, relative, matching_rules in effective_loads[:10]:
            lines.append(
                f"  path={safe_label(relative)} words={words} "
                f"context_units={units} "
                f"rules={safe_label(','.join(matching_rules))}"
            )
    lines.append("path_context_findings:")
    lines.extend(f"  {item}" for item in (findings or ["(none)"]))
    return status, lines


def skill_name(path: Path) -> str:
    for line in read(path, 8_000).splitlines()[:40]:
        match = re.match(r"^name:\s*[\"']?([^\"']+?)[\"']?\s*$", line.strip())
        if match:
            return safe_label(match.group(1).strip())
    return ""


def display_path(path: Path, root: Path, home: Path) -> str:
    for base, prefix in ((root, "project:/"), (home, "~/")):
        try:
            return safe_label(prefix + path.relative_to(base).as_posix())
        except ValueError:
            continue
    return safe_label(path.as_posix())


def candidate_skill_files(root: Path, home: Path) -> list[Path]:
    roots = [
        root / ".claude" / "skills",
        root / ".agents" / "skills",
        root / ".codex" / "skills",
        home / ".claude" / "skills",
        home / ".agents" / "skills",
        home / ".codex" / "skills",
    ]
    candidates: list[Path] = []
    repository_roots: set[Path] = set()
    for skill_root in roots:
        if resolve_audit_dir(skill_root) is None:
            continue
        candidates.extend(skill_root.glob("*/SKILL.md"))
        for child in skill_root.iterdir():
            if not child.is_symlink():
                continue
            try:
                resolved = child.resolve(strict=True)
            except OSError:
                continue
            if resolve_audit_dir(resolved) is None:
                continue
            if (
                resolve_audit_dir(resolved / "skills") is not None
                or resolve_audit_dir(resolved / "plugins") is not None
            ):
                repository_roots.add(resolved)
    for repository in repository_roots:
        candidates.extend(repository.glob("skills/*/SKILL.md"))
    unique: dict[Path, Path] = {}
    for path in candidates:
        canonical = resolve_audit_file(path)
        if canonical is None:
            continue
        unique[canonical] = path
    return sorted(unique)


def skill_runtime(path: Path, root: Path, home: Path) -> str:
    for base, runtime in (
        (root / ".claude" / "skills", "claude"),
        (home / ".claude" / "skills", "claude"),
        (root / ".agents" / "skills", "agents"),
        (home / ".agents" / "skills", "agents"),
        (root / ".codex" / "skills", "codex"),
        (home / ".codex" / "skills", "codex"),
    ):
        try:
            path.relative_to(base)
            return runtime
        except ValueError:
            continue
    return "other"


def summarize_skill_duplicates(root: Path, home: Path) -> tuple[str, list[str]]:
    by_name: dict[str, list[tuple[Path, str, str]]] = defaultdict(list)
    for path in candidate_skill_files(root, home):
        name = skill_name(path)
        if not name:
            continue
        try:
            raw = read_bytes(path)
            if not raw:
                continue
            digest = hashlib.sha256(raw).hexdigest()
        except OSError:
            continue
        by_name[name].append((path, digest, skill_runtime(path, root, home)))
    duplicate_lines: list[str] = []
    cross_runtime_lines: list[str] = []
    cross_runtime_conflicts: list[str] = []
    for name, entries in sorted(by_name.items()):
        if len(entries) < 2:
            continue
        by_runtime: dict[str, list[tuple[Path, str]]] = defaultdict(list)
        for path, digest, runtime in entries:
            by_runtime[runtime].append((path, digest))
        same_runtime = {
            runtime: runtime_entries
            for runtime, runtime_entries in by_runtime.items()
            if len(runtime_entries) > 1
        }
        if same_runtime:
            flattened = [item for group in same_runtime.values() for item in group]
            digest_counts = Counter(digest for _, digest in flattened)
            exact_duplicate = any(count > 1 for count in digest_counts.values())
            kind = "exact-copy" if exact_duplicate else "name-collision"
            surfaces = ", ".join(
                display_path(path, root, home) for path, _ in flattened[:6]
            )
            duplicate_lines.append(f"{name}: kind={kind} surfaces={surfaces}")
        elif len(by_runtime) > 1:
            runtimes = ",".join(sorted(by_runtime))
            digests = {digest for _path, digest, _runtime in entries}
            content = "identical" if len(digests) == 1 else "divergent"
            line = f"{name}: runtimes={runtimes} content={content}"
            cross_runtime_lines.append(line)
            if content == "divergent":
                cross_runtime_conflicts.append(line)
    source_skill_files = (
        unique_physical_files(list((root / "skills").glob("*/SKILL.md")))
        if resolve_audit_dir(root / "skills") is not None
        else []
    )
    lines = [
        "=== SKILL ROUTING DUPLICATES ===",
        f"skill_files_scanned: {sum(len(entries) for entries in by_name.values())}",
        f"source_skill_files_scanned: {len(source_skill_files)}",
        f"duplicate_skill_names: {len(duplicate_lines)}",
        "duplicate_skills:",
    ]
    lines.extend(f"  {line}" for line in (duplicate_lines or ["(none)"]))
    lines.append(f"cross_runtime_shared_skill_names: {len(cross_runtime_lines)}")
    lines.append("cross_runtime_skills:")
    lines.extend(f"  {line}" for line in (cross_runtime_lines or ["(none)"]))
    lines.append(f"cross_runtime_conflicts: {len(cross_runtime_conflicts)}")
    return ("WARN" if duplicate_lines or cross_runtime_conflicts else "PASS"), lines


def parse_codex_config(
    path: Path,
) -> tuple[dict[str, str], list[str], list[str], list[str], list[str]]:
    projects: dict[str, str] = {}
    features: list[str] = []
    plugins: list[str] = []
    marketplaces: list[str] = []
    redacted: list[str] = []
    if resolve_audit_file(path) is None:
        return projects, features, plugins, marketplaces, redacted

    section = ""
    for raw in read(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        project_match = PROJECT_RE.match(line)
        if project_match:
            section = f'projects."{project_match.group(1)}"'
            projects.setdefault(project_match.group(1), "")
            continue
        table_match = TABLE_RE.match(line)
        if table_match:
            section = table_match.group(1)
            marketplace_match = re.match(r'marketplaces\.([A-Za-z0-9_.@-]+)$', section)
            plugin_match = re.match(r'plugins\."?([^"]+)"?$', section)
            if marketplace_match:
                marketplaces.append(marketplace_match.group(1))
            if plugin_match:
                plugins.append(plugin_match.group(1))
            continue

        if SENSITIVE_RE.search(line):
            key = line.split("=", 1)[0].strip() if "=" in line else "sensitive"
            redacted.append(f"{key}=[REDACTED]")
            continue

        if "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        if section == "features" and value.split("#", 1)[0].strip().strip('"').lower() == "true":
            features.append(key)
        elif section.startswith('projects."') and key == "trust_level":
            project = section[len('projects."'): -1]
            projects[project] = value.strip('"')

    return (
        projects,
        sorted(set(features)),
        sorted(set(plugins)),
        sorted(set(marketplaces)),
        sorted(set(redacted)),
    )


def permission_rules(data: object, key: str) -> list[str]:
    if not isinstance(data, dict):
        return []
    permissions = data.get("permissions")
    if not isinstance(permissions, dict):
        return []
    value = permissions.get(key)
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def parse_permission_rule(rule: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"([A-Za-z][A-Za-z0-9_]*)\((.*)\)", rule.strip())
    if not match:
        return None
    return match.group(1), match.group(2).strip()


def normalized_rule_targets(rules: list[str], tool: str) -> list[str]:
    targets: list[str] = []
    for rule in rules:
        parsed = parse_permission_rule(rule)
        if parsed is None or parsed[0].lower() != tool.lower():
            continue
        targets.append(parsed[1].replace("\\", "/").lower())
    return targets


def expand_permission_target(target: str, home: Path) -> str:
    normalized = target.strip().replace("\\", "/")
    home_text = home.resolve().as_posix().lower()
    lowered = normalized.lower()
    for prefix in ("${home}", "$home", "~"):
        if lowered == prefix:
            return home_text
        if lowered.startswith(prefix + "/"):
            return home_text + normalized[len(prefix):].lower()
    return lowered


def target_covers_samples(target: str, home: Path, samples: tuple[str, ...]) -> bool:
    pattern = expand_permission_target(target, home)
    home_text = home.resolve().as_posix().lower()
    return all(
        fnmatch.fnmatchcase(f"{home_text}/{sample.lower()}", pattern)
        for sample in samples
    )


def target_covers_command(target: str, command: str) -> bool:
    escaped = re.escape(command.lower())
    return re.fullmatch(rf"{escaped}(?::\*|\s+\*.*)", target.strip()) is not None


def resolve_command_path(token: str, home: Path, project_root: Path) -> Path | None:
    if token.startswith("~/"):
        candidate = home / token[2:]
    elif token.startswith("$HOME/"):
        candidate = home / token[6:]
    elif token.startswith("${HOME}/"):
        candidate = home / token[8:]
    else:
        candidate = Path(token)
        if not candidate.is_absolute():
            candidate = project_root / candidate
    return resolve_audit_file(candidate)


def resolve_hook_handler(command: str, home: Path, project_root: Path) -> Path | None:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return None
    if not tokens:
        return None

    command_index = 0
    if Path(tokens[0]).name == "env":
        command_index += 1
        while command_index < len(tokens) and (
            tokens[command_index] in {"-i", "--ignore-environment"}
            or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[command_index])
        ):
            command_index += 1
    if command_index >= len(tokens):
        return None

    executable = tokens[command_index]
    if Path(executable).name in {"python", "python3"}:
        safe_flags = {"-B", "-E", "-I", "-O", "-OO", "-P", "-q", "-s", "-S", "-u", "-v"}
        for index, token in enumerate(tokens[command_index + 1 :], command_index + 1):
            if token == "--":
                continue
            if token.startswith("-"):
                if token not in safe_flags:
                    return None
                continue
            if index != len(tokens) - 1:
                return None
            resolved = resolve_command_path(token, home, project_root)
            return resolved if resolved is not None and resolved.suffix == ".py" else None
        return None
    return None


def hook_handler_enforces_pipe_block(path: Path) -> bool:
    canonical = Path(__file__).with_name("block-pipe-to-shell.py")
    candidate_bytes = read_bytes(path)
    canonical_bytes = read_bytes(canonical)
    return bool(candidate_bytes) and candidate_bytes == canonical_bytes


def has_pretool_bash_hook(
    data: object,
    home: Path,
    project_root: Path,
) -> bool:
    if not isinstance(data, dict):
        return False
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return False
    pretool = hooks.get("PreToolUse")
    if not isinstance(pretool, list):
        return False
    for group in pretool:
        if not isinstance(group, dict) or group.get("matcher") != "Bash":
            continue
        handlers = group.get("hooks")
        if not isinstance(handlers, list):
            continue
        for handler in handlers:
            if not isinstance(handler, dict) or handler.get("type") != "command":
                continue
            command = handler.get("command")
            if not isinstance(command, str):
                continue
            path = resolve_hook_handler(command, home, project_root)
            if path is not None and hook_handler_enforces_pipe_block(path):
                return True
    return False


def deny_category_status(
    rules: list[str],
    hook_present: bool,
    home: Path,
) -> dict[str, bool]:
    reads = normalized_rule_targets(rules, "Read")
    bash = normalized_rule_targets(rules, "Bash")
    return {
        "ssh_directory": any(
            target_covers_samples(target, home, (".ssh/id_key", ".ssh/config"))
            for target in reads
        ),
        "aws_directory": any(
            target_covers_samples(target, home, (".aws/credentials", ".aws/config"))
            for target in reads
        ),
        "gnupg_directory": any(
            target_covers_samples(
                target,
                home,
                (".gnupg/private-keys-v1.d/key", ".gnupg/gpg.conf"),
            )
            for target in reads
        ),
        "gh_directory": any(
            target_covers_samples(
                target,
                home,
                (".config/gh/hosts.yml", ".config/gh/config.yml"),
            )
            for target in reads
        ),
        "env_files": any(
            target_covers_samples(
                target,
                home,
                ("project/.env", "project/.env.local"),
            )
            for target in reads
        ),
        "credential_files": any(
            target_covers_samples(
                target,
                home,
                ("project/credentials.json", "project/service-credentials.txt"),
            )
            for target in reads
        ),
        "secrets_directories": any(
            target_covers_samples(
                target,
                home,
                ("project/secrets/token", "project/secrets/nested/key"),
            )
            for target in reads
        ),
        "outbound_shell": all(
            any(target_covers_command(target, command) for target in bash)
            for command in ("ssh", "scp", "nc")
        ),
        "pipe_to_shell": hook_present,
        "git_reset_hard": any(
            target_covers_command(target, "git reset --hard") for target in bash
        ),
    }


def has_task_scoped_env_policy(paths: list[Path]) -> bool:
    for path in paths:
        text = read(path, 200_000).lower()
        if ".env" not in text:
            continue
        if re.search(
            r"task.scoped|current task|task needs|read when needed|"
            r"当前任务|确需|外传|写出|不进产出|"
            r"do not (?:print|output|commit|exfiltrate)",
            text,
        ):
            return True
    return False


def summarize_claude_permissions(
    global_path: Path,
    shared_path: Path,
    local_path: Path,
    env_instruction_policy: bool,
) -> tuple[str, list[str], list[str]]:
    sources = [
        ("global", global_path),
        ("shared", shared_path),
        ("local", local_path),
    ]
    loaded: dict[str, object] = {}
    errors: list[str] = []
    for label, path in sources:
        data, error = load_json(path)
        if error:
            errors.append(f"{label}: {error}")
        loaded[label] = data

    rules = {
        label: {
            key: permission_rules(loaded[label], key)
            for key in ("allow", "deny", "ask")
        }
        for label, _path in sources
    }
    combined_allow = [
        rule for label, _path in sources for rule in rules[label]["allow"]
    ]
    combined_deny = [
        rule for label, _path in sources for rule in rules[label]["deny"]
    ]
    home = global_path.parent.parent
    hook_present = any(
        has_pretool_bash_hook(
            loaded[label],
            home,
            path.parent.parent,
        )
        for label, path in sources
    )
    categories = deny_category_status(combined_deny, hook_present, home)
    required_categories = {
        name: present for name, present in categories.items() if name != "env_files"
    }
    missing = [name for name, present in required_categories.items() if not present]
    env_policy_complete = categories["env_files"] or env_instruction_policy
    if not env_policy_complete:
        missing.append("env_policy")
    broad_read_allow = any(
        "**" in target
        for target in normalized_rule_targets(combined_allow, "Read")
    )
    credential_floor = all(required_categories.values()) and env_policy_complete
    settings_surface_present = any(yes(path) == "yes" for _label, path in sources)
    findings: list[str] = list(errors)
    if settings_surface_present and not credential_floor:
        findings.append(
            "configured global + shared project + local project deny floor is incomplete: "
            + ", ".join(missing)
        )
    lines = [
        "=== CLAUDE PERMISSION SURFACE ===",
        f"global_settings_json: {yes(global_path)}",
        f"shared_project_settings_json: {yes(shared_path)}",
        f"local_project_settings_json: {yes(local_path)}",
    ]
    for label, _path in sources:
        lines.extend(
            f"{label}_{key}_count: {len(rules[label][key])}"
            for key in ("allow", "deny", "ask")
        )
    lines.extend([
        f"broad_read_allow_present: {'yes' if broad_read_allow else 'no'}",
        f"pretool_pipe_to_shell_hook: {'yes' if hook_present else 'no'}",
        f"env_instruction_policy: {'yes' if env_instruction_policy else 'no'}",
        "configured_sensitive_deny_floor_complete: "
        + (
            "not_applicable"
            if not settings_surface_present
            else ("yes" if credential_floor else "no")
        ),
    ])
    lines.extend(
        f"deny_{name}: {'yes' if present else 'no'}"
        for name, present in categories.items()
    )
    lines.append("permission_findings:")
    lines.extend(f"  {item}" for item in (findings or ["(none)"]))
    status = "WARN" if findings else "PASS"
    return status, lines, findings


def project_trust(projects: dict[str, str], root: Path) -> str:
    root_text = root.as_posix()
    if root_text in projects:
        return f"exact:{safe_label(projects[root_text] or 'configured')}"
    candidates = []
    for project, level in projects.items():
        try:
            project_path = Path(project).expanduser().resolve()
        except OSError:
            continue
        if project_path == root:
            return f"exact:{safe_label(level or 'configured')}"
        try:
            root.relative_to(project_path)
        except ValueError:
            continue
        candidates.append(
            (len(project_path.as_posix()), level or "configured", project_path.as_posix())
        )
    if candidates:
        _, level, project = sorted(candidates, reverse=True)[0]
        return f"inherited:{safe_label(level)} from {safe_label(project)}"
    return "missing"


def summarize_pi_surface(root: Path, home: Path) -> tuple[str, list[str]]:
    global_settings = home / ".pi" / "agent" / "settings.json"
    project_settings = root / ".pi" / "settings.json"
    settings_sources = [
        ("global_settings", global_settings),
        ("project_settings", project_settings),
    ]

    configured_skills: list[str] = []
    configured_packages: list[str] = []
    redacted_entries: list[str] = []
    findings: list[str] = []
    malformed = False

    for label, path in settings_sources:
        data, error = load_json(path)
        if error:
            malformed = True
            findings.append(error)
            continue
        if not isinstance(data, dict):
            continue
        configured_skills.extend(
            f"{label}.skills: {item}" for item in string_list(data.get("skills"))
        )
        configured_packages.extend(
            f"{label}.packages: {item}" for item in string_list(data.get("packages"))
        )
        redacted_entries.extend(
            f"{label}.{item}" for item in redact_sensitive_entries(data)
        )

    package_path = root / "package.json"
    package_pi_skills: list[str] = []
    data, error = load_json(package_path)
    if error:
        findings.append(error)
    elif isinstance(data, dict):
        pi_manifest = data.get("pi")
        if isinstance(pi_manifest, dict):
            package_pi_skills = string_list(pi_manifest.get("skills"))

    pi_skill_dirs = [
        ("global_pi_skill_roots", home / ".pi" / "agent" / "skills", True),
        ("project_pi_skill_roots", root / ".pi" / "skills", True),
        ("global_agents_skill_roots", home / ".agents" / "skills", False),
        ("project_agents_skill_roots", root / ".agents" / "skills", False),
    ]
    skill_counts = [
        f"{label}: {skill_root_count(path, include_root_md)}"
        for label, path, include_root_md in pi_skill_dirs
    ]

    has_pi_surface = (
        yes(global_settings) == "yes"
        or yes(project_settings) == "yes"
        or bool(package_pi_skills)
        or any(not line.endswith(": 0") for line in skill_counts)
        or bool(configured_skills)
        or bool(configured_packages)
    )
    if not has_pi_surface:
        findings.append("no Pi settings, package manifest, or skill directories found")

    status = "WARN" if malformed else "PASS"
    lines = [
        "=== PI SURFACE ===",
        f"pi_status: {status}",
        f"global_settings_json: {yes(global_settings)}",
        f"project_settings_json: {yes(project_settings)}",
        f"package_json: {yes(package_path)}",
    ]
    lines.extend(skill_counts)
    lines.append("package_pi_skills:")
    lines.extend(f"  {item}" for item in (package_pi_skills or ["(none)"]))
    lines.append("configured_skills:")
    lines.extend(f"  {item}" for item in (configured_skills or ["(none)"]))
    lines.append("configured_packages:")
    lines.extend(f"  {item}" for item in (configured_packages or ["(none)"]))
    lines.append("redacted_pi_entries:")
    lines.extend(f"  {item}" for item in (redacted_entries or ["(none)"]))
    lines.append("pi_findings:")
    lines.extend(f"  {item}" for item in (findings or ["(none)"]))
    return status, lines


def main() -> int:
    global _AUDIT_ROOT, _AUDIT_HOME
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="Repo root (default: cwd)")
    parser.add_argument(
        "mode", nargs="?", default="summary", choices=("summary", "deep"),
        help="Output detail level",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    mode = args.mode
    home = Path(os.environ.get("HOME", str(Path.home()))).expanduser().resolve()
    _AUDIT_ROOT = root
    _AUDIT_HOME = home

    if not root.is_dir():
        print(f"Repo root not found: {safe_label(root.as_posix())}", file=sys.stderr)
        return 2

    instruction_files = project_instruction_files(root)
    agents = root / "AGENTS.md"
    claude = root / "CLAUDE.md"
    claude_aliases_agents = (
        yes(agents) == "yes" and yes(claude) == "yes" and same_physical_file(agents, claude)
    )
    claude_delegates = claude_aliases_agents or claude_delegates_to_agents(claude)
    github_instructions_dir = root / ".github" / "instructions"
    github_instruction_count = (
        len(unique_physical_files(list(github_instructions_dir.glob("*.md"))))
        if resolve_audit_dir(github_instructions_dir) is not None else 0
    )

    instruction_findings: list[str] = []
    if not instruction_files:
        instruction_findings.append("no project agent instruction files")
    if yes(agents) == "yes" and yes(claude) == "yes" and not claude_delegates:
        claude_lines = len(read(claude).splitlines())
        agents_lines = len(read(agents).splitlines())
        if claude_lines > 20 and agents_lines > 20:
            instruction_findings.append(
                "AGENTS.md and CLAUDE.md both contain substantial guidance without delegation"
            )

    global_codex_agents = home / ".codex" / "AGENTS.md"
    codex_config = home / ".codex" / "config.toml"
    projects, features, plugins, marketplaces, redacted = parse_codex_config(codex_config)
    trust = project_trust(projects, root) if yes(codex_config) == "yes" else "unavailable"
    codex_findings: list[str] = []
    if yes(global_codex_agents) == "no" and yes(codex_config) == "no":
        codex_findings.append("Codex surface not found")
    elif yes(codex_config) == "yes" and trust == "missing":
        codex_findings.append("current project is not configured in Codex trust table")

    global_claude = home / ".claude" / "CLAUDE.md"
    global_claude_settings = home / ".claude" / "settings.json"
    shared_project_settings = root / ".claude" / "settings.json"
    local_project_settings = root / ".claude" / "settings.local.json"
    project_rules = root / ".claude" / "rules"
    global_rules = home / ".claude" / "rules"
    project_skill_roots = [
        root / ".claude" / "skills",
        root / ".agents" / "skills",
        root / ".codex" / "skills",
    ]
    global_skills = home / ".claude" / "skills"
    claude_findings: list[str] = []
    if yes(claude) == "yes" and claude_delegates:
        if claude_aliases_agents:
            claude_findings.append("CLAUDE.md resolves to the same physical file as AGENTS.md")
        else:
            claude_findings.append("CLAUDE.md delegates to AGENTS.md")
    if yes(global_claude) == "no" and yes(claude) == "no":
        claude_findings.append("Claude instruction surface not found")

    if (
        yes(global_claude) == "yes"
        and has_operational_rules(global_claude)
        and yes(global_codex_agents) == "yes"
        and looks_identity_only(global_codex_agents)
    ):
        codex_findings.append(
            "global Codex AGENTS.md has identity/memory context but lacks operational rules present in global Claude CLAUDE.md"
        )
    codex_config_text = read(codex_config) if yes(codex_config) == "yes" else ""
    if (
        'sandbox_mode = "danger-full-access"' in codex_config_text
        and 'approval_policy = "never"' in codex_config_text
    ):
        codex_findings.append(
            "Codex runs danger-full-access with approval_policy=never; Codex has no command-level deny mechanism, so the only levers are sandbox_mode and approval_policy -- surface once as a user tradeoff, not a per-project fix"
        )

    permission_status, permission_lines, permission_findings = summarize_claude_permissions(
        global_claude_settings,
        shared_project_settings,
        local_project_settings,
        has_task_scoped_env_policy([global_claude, global_codex_agents, agents, claude]),
    )
    duplicate_status, duplicate_lines = summarize_skill_duplicates(root, home)
    path_context_status, path_context_lines = summarize_rule_context(
        [("project", project_rules), ("global", global_rules)], root
    )

    conflict_findings: list[str] = []
    if yes(agents) == "yes" and yes(claude) == "yes" and not claude_delegates:
        conflict_findings.append("AGENTS.md and CLAUDE.md both exist; verify they do not diverge")
    if duplicate_status == "WARN":
        conflict_findings.append("active skill names collide or diverge across routing surfaces")

    instruction_status = "FAIL" if not instruction_files else ("WARN" if instruction_findings else "PASS")
    codex_status = "WARN" if codex_findings else "PASS"
    claude_status = (
        "WARN"
        if (
            (claude_findings and "surface not found" in " ".join(claude_findings))
            or permission_status == "WARN"
            or path_context_status == "WARN"
        )
        else "PASS"
    )
    conflict_status = "WARN" if conflict_findings else "PASS"

    print("=== AGENT INSTRUCTION SURFACE ===")
    print(f"agent_instruction_status: {instruction_status}")
    print(f"mode: {mode}")
    print(f"AGENTS.md: {yes(agents)}")
    print(f"CLAUDE.md: {yes(claude)}")
    print(f"claude_aliases_agents: {'yes' if claude_aliases_agents else 'no'}")
    print(f"claude_delegates_to_agents: {'yes' if claude_delegates else 'no'}")
    print(f".github/copilot-instructions.md: {yes(root / '.github' / 'copilot-instructions.md')}")
    print(f".github/instructions/*.md: {github_instruction_count}")
    print(f"GEMINI.md: {yes(root / 'GEMINI.md')}")
    print_list("instruction_files", [rel(path, root) for path in instruction_files])
    print_list("instruction_findings", instruction_findings)

    print("=== CODEX SURFACE ===")
    print(f"codex_status: {codex_status}")
    print(f"global_agents_md: {yes(global_codex_agents)}")
    print(f"global_config_toml: {yes(codex_config)}")
    print(f"project_trust: {trust}")
    print_list("features", features, limit=20 if mode == "summary" else None)
    print_list("enabled_plugins", plugins, limit=20 if mode == "summary" else None)
    print_list("marketplaces", marketplaces, limit=20 if mode == "summary" else None)
    print_list("redacted_config_entries", redacted)
    print_list("codex_findings", codex_findings)

    print("=== CLAUDE SURFACE ===")
    print(f"claude_status: {claude_status}")
    print(f"global_claude_md: {yes(global_claude)}")
    print(f"global_settings_json: {yes(global_claude_settings)}")
    print(f"project_claude_md: {yes(claude)}")
    print(f"shared_settings_json: {yes(shared_project_settings)}")
    print(f"settings_local_json: {yes(local_project_settings)}")
    rule_count = len(unique_physical_files(list(project_rules.glob("*.md"))))
    local_skill_count = len(unique_physical_files([
        path
        for skill_root in project_skill_roots
        if resolve_audit_dir(skill_root) is not None
        for path in skill_root.glob("*/SKILL.md")
    ]))
    global_skill_count = len(
        unique_physical_files(list(global_skills.glob("*/SKILL.md")))
    )
    print(f"project_rules: {rule_count}")
    print(f"project_skills: {local_skill_count}")
    source_skill_count = (
        len(unique_physical_files(list((root / "skills").glob("*/SKILL.md"))))
        if resolve_audit_dir(root / "skills") is not None
        else 0
    )
    print(f"source_skills: {source_skill_count}")
    print(f"global_skills: {global_skill_count}")
    print_list("claude_findings", claude_findings)

    for line in permission_lines:
        print(safe_label(line, 2_000))

    for line in path_context_lines:
        print(safe_label(line, 2_000))

    for line in duplicate_lines:
        print(safe_label(line, 2_000))

    _, pi_lines = summarize_pi_surface(root, home)
    for line in pi_lines:
        print(safe_label(line, 2_000))

    print("=== INSTRUCTION CONFLICTS ===")
    print(f"conflict_status: {conflict_status}")
    print_list("conflict_findings", conflict_findings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
