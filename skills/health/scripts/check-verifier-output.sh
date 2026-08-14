#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]}"
case "$SCRIPT_PATH" in
  */*) SCRIPT_BASE="${SCRIPT_PATH%/*}" ;;
  *) SCRIPT_BASE="." ;;
esac
SCRIPT_DIR="$(cd "$SCRIPT_BASE" && pwd -P)"
unset WAZA_PYTHON DOC_REF_CHECKER GIT_INSTALL_ROOT BASH_ENV ENV

sanitize_health_path() {
  local target="$1"
  local entry physical safe=""
  local -a path_entries=()
  target=$(cd "$target" 2>/dev/null && pwd -P) || target=$(pwd -P)
  IFS=: read -r -a path_entries <<< "${PATH:-}"
  for entry in "${path_entries[@]}"; do
    [ -n "$entry" ] || continue
    case "$entry" in
      /*) ;;
      *) continue ;;
    esac
    [ -d "$entry" ] || continue
    physical=$(cd "$entry" 2>/dev/null && pwd -P) || continue
    case "$physical/" in
      "$target/"*) continue ;;
    esac
    safe="${safe:+$safe:}$physical"
  done
  printf '%s\n' "$safe"
}

canonical_health_executable() {
  local current="$1"
  local parent name link readlink_bin=""
  local depth=0
  case "$current" in
    /*) ;;
    *) return 1 ;;
  esac
  while [ "$depth" -lt 32 ]; do
    parent="${current%/*}"
    name="${current##*/}"
    [ -n "$parent" ] || parent="/"
    parent=$(cd "$parent" 2>/dev/null && pwd -P) || return 1
    if [ "$parent" = "/" ]; then
      current="/$name"
    else
      current="$parent/$name"
    fi
    if [ ! -L "$current" ]; then
      [ -f "$current" ] && [ -x "$current" ] || return 1
      printf '%s\n' "$current"
      return 0
    fi
    if [ -z "$readlink_bin" ]; then
      if [ -x /usr/bin/readlink ]; then
        readlink_bin=/usr/bin/readlink
      else
        readlink_bin=$(type -P readlink 2>/dev/null || true)
      fi
      [ -n "$readlink_bin" ] || return 1
    fi
    link=$("$readlink_bin" "$current") || return 1
    case "$link" in
      /*) current="$link" ;;
      *) current="$parent/$link" ;;
    esac
    depth=$((depth + 1))
  done
  return 1
}

HEALTH_TARGET=$(cd "${1:-$PWD}" 2>/dev/null && pwd -P) || HEALTH_TARGET=$(pwd -P)
PATH="$(sanitize_health_path "$HEALTH_TARGET")"
export PATH
PYTHON_BIN=""
for candidate in python3 python; do
  resolved=$(type -P "$candidate" 2>/dev/null || true)
  [ -n "$resolved" ] || continue
  resolved=$(canonical_health_executable "$resolved" 2>/dev/null || true)
  [ -n "$resolved" ] || continue
  if [ "$HEALTH_TARGET" = "/" ]; then
    continue
  fi
  case "$resolved/" in
    "$HEALTH_TARGET/"*) continue ;;
  esac
  "$resolved" --version >/dev/null 2>&1 || continue
  "$resolved" -I -c 'import sys; raise SystemExit(sys.version_info < (3, 9))' \
    >/dev/null 2>&1 || continue
  PYTHON_BIN="$resolved"
  break
done
[ -n "$PYTHON_BIN" ] || exit 127
exec "$PYTHON_BIN" -I "$SCRIPT_DIR/check_verifier_output.py" "$@"
