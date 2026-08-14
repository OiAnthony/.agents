#!/usr/bin/env python3
"""Claude PreToolUse hook that blocks remote-download-to-shell pipelines."""

from __future__ import annotations

import json
import os
import re
import shlex
import sys


DOWNLOADERS = {"curl", "wget"}
SHELLS = {"bash", "dash", "sh", "zsh"}
PIPE_OPERATORS = {"|", "|&"}
GROUP_OPERATORS = {"&", "&&", ";", "||"}
COMPOUND_OPENERS = {"(", "{"}
COMPOUND_CLOSERS = {")", "}"}
COMMAND_SEPARATORS = GROUP_OPERATORS | COMPOUND_OPENERS | COMPOUND_CLOSERS
CONTROL_OPENERS = {"case": "esac", "for": "done", "if": "fi", "select": "done", "until": "done", "while": "done"}
CONTROL_CLOSERS = set(CONTROL_OPENERS.values())
COMMAND_BOUNDARIES = COMMAND_SEPARATORS | {"do", "elif", "else", "then"}
CONTROL_WORDS = set(CONTROL_OPENERS) | CONTROL_CLOSERS
ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
LAUNCH_WRAPPERS = {"builtin", "exec", "nohup", "setsid"}
APPLET_WRAPPERS = {"busybox", "toybox"}
DYNAMIC_SHELL_NAMES = {"$BASH", "$SHELL", "${BASH}", "${SHELL}"}
CHROOT_OPTIONS_WITH_VALUES = {"--groups", "--userspec"}
SUDO_OPTIONS_WITH_VALUES = {
    "-C", "--chdir", "--close-from", "-D", "-g", "--group", "-h", "--host",
    "-p", "--prompt", "-r", "--role", "-t", "--type", "-u", "--user",
}
TIMEOUT_OPTIONS_WITH_VALUES = {"-k", "--kill-after", "-s", "--signal"}
TIME_OPTIONS_WITH_VALUES = {"-f", "--format", "-o", "--output"}
XARGS_OPTIONS_WITH_VALUES = {
    "-a", "--arg-file", "-d", "--delimiter", "-E", "--eof", "-I", "--replace",
    "-L", "--max-lines", "-n", "--max-args", "-P", "--max-procs",
    "--process-slot-var", "-s", "--max-chars",
}
STDBUF_OPTIONS_WITH_VALUES = {
    "-e", "--error", "-i", "--input", "-o", "--output",
}
ENV_OPTIONS_WITH_VALUES = {
    "-C", "--chdir", "-u", "--unset", "-a", "--argv0",
}


def command_token_names(tokens: list[str]) -> set[str]:
    """Return executable candidates without treating ordinary arguments as commands."""
    leading = list(tokens)
    while leading and (
        leading[0] in CONTROL_WORDS or ASSIGNMENT_RE.match(leading[0])
    ):
        leading.pop(0)
    if leading:
        first = leading[0]
        dynamic = " ".join(leading)
        if first in DYNAMIC_SHELL_NAMES or (
            (first == "$" or first.startswith("`"))
            and re.search(r"\b(?:BASH|SHELL|bash|dash|sh|zsh)\b", dynamic)
        ):
            return {"sh"}

    names: set[str] = set()
    chunks: list[list[str]] = []
    chunk: list[str] = []
    for token in tokens:
        if token in COMMAND_BOUNDARIES:
            if chunk:
                chunks.append(chunk)
                chunk = []
        else:
            chunk.append(token)
    if chunk:
        chunks.append(chunk)

    for candidate in chunks:
        names.update(effective_command_names(candidate))
    return names


def option_name(token: str) -> str:
    return token.split("=", 1)[0]


def effective_command_names(tokens: list[str]) -> set[str]:
    """Unwrap known launchers and return the commands they would execute."""
    pending = list(tokens)
    while pending:
        while pending and (
            pending[0] in CONTROL_WORDS or ASSIGNMENT_RE.match(pending[0])
        ):
            pending.pop(0)
        if not pending:
            return set()

        raw_name = pending.pop(0)
        if raw_name in DYNAMIC_SHELL_NAMES:
            return {"sh"}
        if raw_name == "$" and pending:
            dynamic = " ".join(pending)
            if re.search(r"\b(?:BASH|SHELL|bash|dash|sh|zsh)\b", dynamic):
                return {"sh"}
        if raw_name.startswith("`"):
            dynamic = " ".join([raw_name, *pending])
            if re.search(r"\b(?:bash|dash|sh|zsh)\b", dynamic):
                return {"sh"}
        name = os.path.basename(raw_name)
        if name in LAUNCH_WRAPPERS:
            while pending and pending[0].startswith("-"):
                pending.pop(0)
            continue

        if name in APPLET_WRAPPERS:
            while pending and pending[0].startswith("-"):
                pending.pop(0)
            continue

        if name == "chroot":
            while pending and pending[0].startswith("-"):
                token = pending.pop(0)
                if token == "--":
                    break
                if option_name(token) in CHROOT_OPTIONS_WITH_VALUES and "=" not in token:
                    if pending:
                        pending.pop(0)
            if pending:
                pending.pop(0)
            continue

        if name == "command":
            query_only = False
            while pending and pending[0].startswith("-"):
                token = pending.pop(0)
                if token == "--":
                    break
                query_only = query_only or "v" in token[1:] or "V" in token[1:]
            if query_only:
                return set()
            continue

        if name == "eval":
            if not pending:
                return set()
            try:
                return command_token_names(expanded_shell_tokens(" ".join(pending)))
            except ValueError:
                return set()

        if name == "time":
            while pending and pending[0].startswith("-"):
                token = pending.pop(0)
                if option_name(token) in TIME_OPTIONS_WITH_VALUES and "=" not in token:
                    if pending:
                        pending.pop(0)
            continue

        if name in {"stdbuf", "xargs"}:
            options_with_values = (
                STDBUF_OPTIONS_WITH_VALUES if name == "stdbuf" else XARGS_OPTIONS_WITH_VALUES
            )
            while pending and pending[0].startswith("-"):
                token = pending.pop(0)
                if token == "--":
                    break
                if option_name(token) in options_with_values and "=" not in token:
                    if pending:
                        pending.pop(0)
            continue

        if name == "sudo":
            while pending:
                token = pending[0]
                if token == "--":
                    pending.pop(0)
                    break
                if not token.startswith("-"):
                    break
                pending.pop(0)
                if option_name(token) in SUDO_OPTIONS_WITH_VALUES and "=" not in token:
                    if pending:
                        pending.pop(0)
            continue

        if name == "env":
            while pending:
                token = pending[0]
                if token == "--":
                    pending.pop(0)
                    break
                if token in {"-S", "--split-string"}:
                    pending.pop(0)
                    if not pending:
                        return set()
                    payload = pending.pop(0)
                    try:
                        pending = shlex.split(payload, posix=True) + pending
                    except ValueError:
                        return set()
                    break
                if token.startswith("--split-string="):
                    pending.pop(0)
                    try:
                        pending = shlex.split(token.split("=", 1)[1], posix=True) + pending
                    except ValueError:
                        return set()
                    break
                if option_name(token) in ENV_OPTIONS_WITH_VALUES:
                    pending.pop(0)
                    if "=" not in token and pending:
                        pending.pop(0)
                    continue
                if token.startswith("-") or ASSIGNMENT_RE.match(token):
                    pending.pop(0)
                    continue
                break
            continue

        if name == "timeout":
            while pending and pending[0].startswith("-"):
                token = pending.pop(0)
                if option_name(token) in TIMEOUT_OPTIONS_WITH_VALUES and "=" not in token:
                    if pending:
                        pending.pop(0)
            if pending:
                pending.pop(0)
            continue

        if name == "nice":
            while pending and pending[0].startswith("-"):
                token = pending.pop(0)
                if token in {"-n", "--adjustment"} and pending:
                    pending.pop(0)
            continue

        return {name}
    return set()


def expanded_shell_tokens(command: str) -> list[str]:
    punctuation = "(){}<>|;&"
    lexer = shlex.shlex(command, posix=True, punctuation_chars=punctuation)
    lexer.whitespace_split = True
    tokens: list[str] = []
    for token in lexer:
        if token and all(char in punctuation for char in token):
            index = 0
            while index < len(token):
                pair = token[index : index + 2]
                if pair in {"&&", "||", "|&"}:
                    tokens.append(pair)
                    index += 2
                else:
                    tokens.append(token[index])
                    index += 1
        else:
            tokens.append(token)
    return tokens


def pipeline_groups(command: str) -> list[list[list[str]]]:
    normalized = command.replace("\\\r\n", " ").replace("\\\n", " ")
    tokens = expanded_shell_tokens(normalized)
    groups: list[list[list[str]]] = []
    group: list[list[str]] = []
    segment: list[str] = []
    compound_depth = 0
    control_stack: list[str] = []
    for token in tokens:
        if token in CONTROL_OPENERS:
            control_stack.append(CONTROL_OPENERS[token])
            segment.append(token)
            continue
        if token in CONTROL_CLOSERS:
            if control_stack and control_stack[-1] == token:
                control_stack.pop()
            segment.append(token)
            continue
        if token in COMPOUND_OPENERS:
            compound_depth += 1
            segment.append(token)
            continue
        if token in COMPOUND_CLOSERS:
            compound_depth = max(0, compound_depth - 1)
            segment.append(token)
            continue
        if token in PIPE_OPERATORS:
            group.append(segment)
            segment = []
        elif token in GROUP_OPERATORS and compound_depth == 0 and not control_stack:
            group.append(segment)
            if group:
                groups.append(group)
            group = []
            segment = []
        else:
            segment.append(token)
    group.append(segment)
    if group:
        groups.append(group)
    return groups


def pipes_download_to_shell(command: str) -> bool:
    try:
        groups = pipeline_groups(command)
    except ValueError:
        return False
    for segments in groups:
        downloader_seen = False
        for segment in segments:
            names = command_token_names(segment)
            if downloader_seen and any(name in SHELLS for name in names):
                return True
            if any(name in DOWNLOADERS for name in names):
                downloader_seen = True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError, UnicodeError):
        return 0
    if not isinstance(payload, dict):
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    command = tool_input.get("command")
    if not isinstance(command, str) or not pipes_download_to_shell(command):
        return 0
    print(
        "Blocked: piping a remote download directly into a shell. "
        "Download to a file, review it, then run it explicitly.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
