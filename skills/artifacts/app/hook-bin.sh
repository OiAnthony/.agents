# shellcheck shell=bash
# Claude Code can run hooks with an empty PATH, so these use bash builtins only.

ryugi_plugin_version() {
  local line rest manifest
  manifest="$1/package.json"
  [ -r "$manifest" ] || manifest="$1/.codex-plugin/plugin.json"
  [ -r "$manifest" ] || return 1
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      '  "version"'*)
        rest="${line#*\"version\"}"
        rest="${rest#*\"}"
        rest="${rest%%\"*}"
        [ -n "$rest" ] || return 1
        printf '%s\n' "$rest"
        return 0
        ;;
    esac
  done < "$manifest"
  return 1
}

ryugi_dev_plugin() {
  local line rest link
  link="${RYUGI_DEV_LINK:-${HOME:-}/.ryugi/dev.json}"
  [ -r "$link" ] || return 1
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      '  "plugin": "'*)
        rest="${line#  \"plugin\": \"}"
        rest="${rest%\"*}"
        [ -n "$rest" ] || return 1
        printf '%s\n' "$rest"
        return 0
        ;;
    esac
  done < "$link"
  return 1
}

ryugi_hook_bin() {
  local version candidate dev
  if [ -n "${RYUGI_HOOK_BIN:-}" ]; then
    [ -f "$RYUGI_HOOK_BIN" ] && [ -x "$RYUGI_HOOK_BIN" ] || return 1
    printf '%s\n' "$RYUGI_HOOK_BIN"
    return 0
  fi
  if dev="$(ryugi_dev_plugin)"; then
    candidate="$dev/hook/target/release/ryugi-hook"
    if [ -f "$candidate" ] && [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  fi
  candidate="$1/hook/target/release/ryugi-hook"
  if [ -f "$candidate" ] && [ -x "$candidate" ]; then
    printf '%s\n' "$candidate"
    return 0
  fi
  version="$(ryugi_plugin_version "$1")" || return 1
  candidate="${HOME:-}/.ryugi/hook/$version/ryugi-hook"
  if [ -f "$candidate" ] && [ -x "$candidate" ]; then
    printf '%s\n' "$candidate"
    return 0
  fi
  return 1
}
