#!/usr/bin/env python3
"""Scan skill instruction surfaces and emit bounded, non-authoritative receipts."""

from __future__ import annotations

import argparse
import bisect
import hashlib
import os
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


MAX_FILE_BYTES = 1_048_576
MAX_SURFACE_FILES = 512
MAX_ISSUES = 8
MAX_MATCHES = 8
MAX_SKILL_RECEIPTS = 200
SURFACE_DIRS = ("references", "agents", "scripts")

PATTERNS = {
    "prompt_override": re.compile(
        r"ignore\s+(?:all\s+|any\s+)?(?:previous|prior)\s+instructions|"
        r"disregard\s+(?:the\s+)?(?:system|developer)\s+prompt|jailbreak",
        re.IGNORECASE | re.DOTALL,
    ),
    "destructive_command": re.compile(
        r"rm\s+-[A-Za-z]*r[A-Za-z]*f\s+(?:/|~|\$HOME)(?:\s|$)|"
        r"git\s+push\s+[^\n]*--force(?:-with-lease)?",
        re.IGNORECASE,
    ),
    "safety_bypass": re.compile(
        r"dangerously-skip-permissions|disable\s+(?:all\s+)?(?:safety|security)\s+checks|"
        r"bypass\s+(?:all\s+)?(?:safety|security)\s+checks",
        re.IGNORECASE | re.DOTALL,
    ),
}

SHELL_NETWORK_COMMAND_RE = re.compile(
    r"\b(?:curl|wget)\b(?:\\\r?\n|[^\r\n;&|]){0,960}",
    re.IGNORECASE | re.DOTALL,
)
CODE_NETWORK_CALL_RE = re.compile(
    r"\brequests\.(?:get|post|put|patch|delete|request)\s*\([^)]{0,960}\)|"
    r"\bfetch\s*\([^)]{0,960}\)",
    re.IGNORECASE | re.DOTALL,
)
SENSITIVE_ENV_NAME = (
    r"[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|PRIVATE_KEY|"
    r"CREDENTIAL|AUTHORIZATION|AUTH_TOKEN|COOKIE|SESSION_KEY)[A-Z0-9_]*"
)
SECRET_SOURCE_RE = re.compile(
    rf"os\.environ\b|process\.env\b|\$\{{?{SENSITIVE_ENV_NAME}\}}?",
    re.IGNORECASE,
)

PEM_RE = re.compile(
    r"-----BEGIN [^-\r\n]+-----.*?(?:-----END [^-\r\n]+-----|\Z)",
    re.IGNORECASE | re.DOTALL,
)
SECRET_RE = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{12,}|"
    r"github_pat_[A-Za-z0-9_]{12,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"AKIA[A-Z0-9]{16}|"
    r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b"
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?P<name>\b(?:authorization|password|passwd|pwd|token|secret|api[_-]?key)\b)"
    r"(?P<separator>\s*[:=]\s*)"
    r"(?:Bearer\s+|Basic\s+)?(?:\"[^\"\r\n]*(?:\"|(?=\r?\n|\Z))|'[^'\r\n]*(?:'|(?=\r?\n|\Z))|[^\s,;]+)",
    re.IGNORECASE,
)
ABS_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_])/(?:Users|home|private|tmp|var|etc|opt|Volumes)/[^\s`\"'<>]+"
)
TILDE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])~/(?:[^\s`\"'<>]+)")
WINDOWS_ABS_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:[A-Za-z]:\\|\\\\)[^\s`\"'<>]+"
)
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


@dataclass(frozen=True)
class SurfaceFile:
    path: Path
    relative: str
    surface: str
    identity: tuple[int, int]


@dataclass(frozen=True)
class ReadResult:
    raw: Optional[bytes]
    issue: Optional[str]


def safe_label(value: str, limit: int = 240) -> str:
    return re.sub(r"[^A-Za-z0-9._:/~+-]+", "_", value)[:limit]


def contained(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def display_path(path: Path, project_root: Optional[Path], home: Path) -> str:
    absolute = path if path.is_absolute() else Path.cwd() / path
    try:
        absolute = absolute.parent.resolve(strict=True) / absolute.name
    except OSError:
        pass
    for root, prefix in ((project_root, "project:/"), (home, "~/")):
        if root is None:
            continue
        try:
            return prefix + absolute.relative_to(root).as_posix()
        except ValueError:
            continue
    return "external:/" + safe_label(path.name or "unknown")


def sensitive_reason(path: Path, home: Path) -> Optional[str]:
    protected = {
        "ssh": home / ".ssh",
        "aws": home / ".aws",
        "gnupg": home / ".gnupg",
        "gh": home / ".config" / "gh",
    }
    for name, root in protected.items():
        if path == root or contained(path, root):
            return f"protected_{name}_path"
    for part in path.parts:
        lowered = part.lower()
        if lowered == "secrets":
            return "secrets_path"
        if "credential" in lowered:
            return "credentials_path"
        if lowered == ".env" or lowered.startswith(".env."):
            return "env_path"
    return None


def git_revision(root: Path) -> str:
    try:
        result = subprocess.run(
            [
                "git",
                "-c",
                "core.fsmonitor=false",
                "-C",
                str(root),
                "rev-parse",
                "--short",
                "HEAD",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    return result.stdout.strip()[:40] if result.returncode == 0 else "unversioned"


def safe_excerpt(text: str) -> str:
    text = PEM_RE.sub("[REDACTED PRIVATE KEY]", text)
    text = SECRET_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group('name')}{match.group('separator')}[REDACTED]",
        text,
    )
    text = SECRET_RE.sub("[REDACTED]", text)
    text = ABS_PATH_RE.sub("[PATH]", text)
    text = TILDE_PATH_RE.sub("[PATH]", text)
    text = WINDOWS_ABS_PATH_RE.sub("[PATH]", text)
    text = CONTROL_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:180]


def stable_read(path: Path, identity: tuple[int, int]) -> ReadResult:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        return ReadResult(None, f"read_unavailable:{error.__class__.__name__}")
    try:
        before = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != identity:
            return ReadResult(None, "identity_changed_before_read")
        chunks: list[bytes] = []
        remaining = MAX_FILE_BYTES + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(descriptor)
        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
        ):
            return ReadResult(None, "changed_during_read")
        raw = b"".join(chunks)
        if len(raw) > MAX_FILE_BYTES:
            return ReadResult(raw[:MAX_FILE_BYTES], "content_truncated")
        return ReadResult(raw, None)
    except OSError as error:
        return ReadResult(None, f"read_unavailable:{error.__class__.__name__}")
    finally:
        os.close(descriptor)


def discover_surfaces(
    entrypoint: Path,
    entry_identity: tuple[int, int],
    home: Path,
) -> tuple[list[SurfaceFile], list[str], dict[str, int]]:
    root = entrypoint.parent
    files = [SurfaceFile(entrypoint, "SKILL.md", "entry", entry_identity)]
    issues: list[str] = []
    counts = {"entry": 1, "references": 0, "agents": 0, "scripts": 0}
    seen = {entry_identity}
    entries_seen = 1
    traversal_limited = False

    def record_issue(issue: str) -> None:
        if len(issues) < MAX_ISSUES + 1:
            issues.append(issue)

    for surface in SURFACE_DIRS:
        directory = root / surface
        if not directory.exists() and not directory.is_symlink():
            continue
        try:
            resolved_directory = directory.resolve(strict=True)
        except OSError as error:
            record_issue(f"{surface}_unreadable:{error.__class__.__name__}")
            continue
        reason = sensitive_reason(resolved_directory, home)
        if reason:
            record_issue(f"{surface}_rejected:{reason}")
            continue
        if not contained(resolved_directory, root) or not resolved_directory.is_dir():
            record_issue(f"{surface}_outside_skill_root")
            continue

        def walk_error(error: OSError) -> None:
            record_issue(f"{surface}_walk_unavailable:{error.__class__.__name__}")

        for current, directories, names in os.walk(
            directory,
            topdown=True,
            followlinks=False,
            onerror=walk_error,
        ):
            current_path = Path(current)
            kept_directories: list[str] = []
            for name in sorted(directories):
                entries_seen += 1
                if entries_seen > MAX_SURFACE_FILES:
                    traversal_limited = True
                    break
                candidate_directory = current_path / name
                if candidate_directory.is_symlink():
                    record_issue(
                        f"directory_symlink_rejected:{safe_label(candidate_directory.relative_to(root).as_posix())}"
                    )
                    continue
                if sensitive_reason(candidate_directory, home):
                    record_issue(
                        f"sensitive_directory_rejected:{safe_label(candidate_directory.relative_to(root).as_posix())}"
                    )
                    continue
                kept_directories.append(name)
            if traversal_limited:
                directories[:] = []
                record_issue("surface_entry_limit_reached")
                break
            directories[:] = kept_directories
            for name in sorted(names):
                entries_seen += 1
                if entries_seen > MAX_SURFACE_FILES:
                    traversal_limited = True
                    record_issue("surface_entry_limit_reached")
                    directories[:] = []
                    break
                candidate = current_path / name
                relative = candidate.relative_to(root).as_posix()
                if candidate.is_symlink():
                    record_issue(f"leaf_symlink_rejected:{safe_label(relative)}")
                    continue
                try:
                    resolved = candidate.resolve(strict=True)
                    stat = candidate.stat()
                except OSError as error:
                    record_issue(
                        f"unreadable:{safe_label(relative)}:{error.__class__.__name__}"
                    )
                    continue
                reason = sensitive_reason(resolved, home)
                if reason:
                    record_issue(f"sensitive_file_rejected:{safe_label(relative)}:{reason}")
                    continue
                if not contained(resolved, root):
                    record_issue(f"outside_skill_root:{safe_label(relative)}")
                    continue
                if not resolved.is_file():
                    continue
                identity = (stat.st_dev, stat.st_ino)
                if identity in seen:
                    continue
                seen.add(identity)
                files.append(SurfaceFile(resolved, relative, surface, identity))
                counts[surface] += 1
            if traversal_limited:
                break
    return files, issues, counts


def scan_text(text: str) -> list[tuple[str, int, str]]:
    matches: list[tuple[str, int, str]] = []
    line_starts = [0]
    line_starts.extend(match.end() for match in re.finditer("\n", text))
    for name, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            line_number = bisect.bisect_right(line_starts, match.start())
            excerpt_start = text.rfind("\n", 0, match.start()) + 1
            excerpt_end = text.find("\n", match.end())
            if excerpt_end < 0:
                excerpt_end = len(text)
            matches.append(
                (name, line_number, safe_excerpt(text[excerpt_start:excerpt_end]))
            )
            if len(matches) >= MAX_MATCHES + 1:
                return matches
    network_calls = list(SHELL_NETWORK_COMMAND_RE.finditer(text))
    network_calls.extend(CODE_NETWORK_CALL_RE.finditer(text))
    network_calls.sort(key=lambda match: match.start())
    for command_match in network_calls:
        command_text = command_match.group(0)
        secret_match = SECRET_SOURCE_RE.search(command_text)
        if secret_match is None:
            continue
        line_number = bisect.bisect_right(line_starts, command_match.start())
        excerpt_start = text.rfind("\n", 0, command_match.start()) + 1
        absolute_secret_end = command_match.start() + secret_match.end()
        excerpt_end = text.find("\n", absolute_secret_end)
        if excerpt_end < 0:
            excerpt_end = len(text)
        matches.append(
            (
                "secret_exfiltration",
                line_number,
                safe_excerpt(text[excerpt_start:excerpt_end]),
            )
        )
        if len(matches) >= MAX_MATCHES + 1:
            return matches
    return matches


def print_unreadable(path_label: str, issue: str) -> None:
    print(
        f"path={path_label} scan_status=unreadable files_scanned=0 "
        f"bytes_scanned=0 coverage_issues=1"
    )
    print(f"  coverage_issue={safe_label(issue)}")


def scan_skill(
    path_label: str,
    entrypoint: Path,
    entry_identity: tuple[int, int],
    home: Path,
    emit: bool = True,
) -> str:
    surfaces, issues, counts = discover_surfaces(entrypoint, entry_identity, home)
    matches: list[tuple[str, str, int, str]] = []
    bytes_scanned = 0
    entry_digest = "unavailable"
    read_files = 0
    for surface_file in surfaces:
        result = stable_read(surface_file.path, surface_file.identity)
        if result.issue:
            issues.append(
                f"{safe_label(surface_file.relative)}:{safe_label(result.issue)}"
            )
        if result.raw is None:
            continue
        raw = result.raw
        if surface_file.relative == "SKILL.md":
            entry_digest = hashlib.sha256(raw).hexdigest()
        bytes_scanned += len(raw)
        read_files += 1
        text = raw.decode("utf-8", errors="replace")
        for name, line_number, excerpt in scan_text(text):
            matches.append((surface_file.relative, name, line_number, excerpt))

    if matches and issues:
        status = "review_matches_and_gaps"
    elif matches:
        status = "review_matches"
    elif issues:
        status = "coverage_gap"
    else:
        status = "no_pattern_match"
    counts_text = ",".join(f"{name}:{count}" for name, count in counts.items())
    if emit:
        print(
            f"path={path_label} sha256={entry_digest} "
            f"source_revision={git_revision(entrypoint.parent)} scan_status={status} "
            f"files_scanned={read_files} bytes_scanned={bytes_scanned} "
            f"surfaces={counts_text} coverage_issues={len(issues)}"
        )
        for issue in issues[:MAX_ISSUES]:
            print(f"  coverage_issue={safe_label(issue)}")
        if len(issues) > MAX_ISSUES:
            print(f"  additional_coverage_issues={len(issues) - MAX_ISSUES}")
        for relative, name, line_number, excerpt in matches[:MAX_MATCHES]:
            print(
                f"  file={safe_label(relative)} match={name} "
                f"line={line_number} excerpt={excerpt}"
            )
        if len(matches) > MAX_MATCHES:
            print(f"  additional_matches={len(matches) - MAX_MATCHES}")
    return status


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--health-entrypoint", type=Path)
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args(list(argv) if argv is not None else None)

    home = Path.home().resolve()
    project_root = args.project_root.resolve() if args.project_root else None
    health_identity: Optional[tuple[int, int]] = None
    if args.health_entrypoint:
        try:
            health_stat = args.health_entrypoint.stat()
            health_identity = (health_stat.st_dev, health_stat.st_ino)
        except OSError:
            health_identity = None

    seen_roots: set[tuple[int, int]] = set()
    receipts = 0
    suppressed = 0
    statuses: Counter[str] = Counter()
    for raw_path in args.paths:
        candidate = Path(raw_path)
        label = display_path(candidate, project_root, home)
        if candidate.is_symlink():
            if receipts < MAX_SKILL_RECEIPTS:
                print_unreadable(label, "leaf_symlink_rejected")
            else:
                suppressed += 1
            statuses["unreadable"] += 1
            receipts += 1
            continue
        try:
            entrypoint = candidate.resolve(strict=True)
            entry_stat = candidate.stat()
            root_stat = entrypoint.parent.stat()
        except OSError as error:
            if receipts < MAX_SKILL_RECEIPTS:
                print_unreadable(label, f"entrypoint_unreadable:{error.__class__.__name__}")
            else:
                suppressed += 1
            statuses["unreadable"] += 1
            receipts += 1
            continue
        reason = sensitive_reason(entrypoint, home)
        if reason:
            if receipts < MAX_SKILL_RECEIPTS:
                print_unreadable(label, f"sensitive_entrypoint_rejected:{reason}")
            else:
                suppressed += 1
            statuses["unreadable"] += 1
            receipts += 1
            continue
        if project_root is not None:
            absolute_candidate = candidate if candidate.is_absolute() else Path.cwd() / candidate
            project_skill_roots = (
                project_root / "skills",
                project_root / ".claude" / "skills",
                project_root / ".agents" / "skills",
                project_root / ".codex" / "skills",
            )
            from_project_surface = any(
                contained(absolute_candidate, root) for root in project_skill_roots
            )
            if from_project_surface and not contained(entrypoint, project_root):
                if receipts < MAX_SKILL_RECEIPTS:
                    print_unreadable(label, "project_skill_escape_rejected")
                else:
                    suppressed += 1
                statuses["unreadable"] += 1
                receipts += 1
                continue
        identity = (entry_stat.st_dev, entry_stat.st_ino)
        root_identity = (root_stat.st_dev, root_stat.st_ino)
        if health_identity is not None and identity == health_identity:
            continue
        if entrypoint.name != "SKILL.md" or not entrypoint.is_file():
            if receipts < MAX_SKILL_RECEIPTS:
                print_unreadable(label, "not_a_skill_entrypoint")
            else:
                suppressed += 1
            statuses["unreadable"] += 1
            receipts += 1
            continue
        if root_identity in seen_roots:
            continue
        seen_roots.add(root_identity)
        emit = receipts < MAX_SKILL_RECEIPTS
        status = scan_skill(label, entrypoint, identity, home, emit=emit)
        statuses[status] += 1
        if not emit:
            suppressed += 1
        receipts += 1
    if receipts == 0:
        print("(none)")
    elif suppressed:
        print(f"skill_receipts_truncated: {suppressed}")
        print(
            "scan_status_totals: "
            + ",".join(f"{name}:{count}" for name, count in sorted(statuses.items()))
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
