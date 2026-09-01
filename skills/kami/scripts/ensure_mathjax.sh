#!/usr/bin/env bash
# Ensure strict TeX -> SVG rendering is available for Kami.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_DIR="$SCRIPT_DIR/mathjax-runtime"

if ! command -v node >/dev/null 2>&1; then
  echo "ERROR: Node.js is required for strict LaTeX rendering" >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm is required to install the strict LaTeX renderer" >&2
  exit 1
fi
unset NODE_OPTIONS
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
if (( NODE_MAJOR < 20 || NODE_MAJOR == 21 )); then
  echo "ERROR: strict LaTeX rendering requires Node.js 20 or Node.js 22+" >&2
  exit 1
fi

if node "$SCRIPT_DIR/mathjax_svg.js" --probe >/dev/null 2>&1; then
  echo "OK: locked MathJax runtime available"
  exit 0
fi

if [[ "$(uname -s)" == "Darwin" ]]; then
  # shared.configure_weasyprint_runtime repurposes XDG_CACHE_HOME for fontconfig.
  # Keep MathJax in its own stable user cache instead.
  CACHE_HOME="$HOME/.cache"
else
  CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
fi
MATHJAX_VERSION="$(node -p 'require(process.argv[1]).dependencies["@mathjax/src"]' "$RUNTIME_DIR/package.json")"
MATH_ROOT="$CACHE_HOME/kami/mathjax/$MATHJAX_VERSION"
MATH_PARENT="$(dirname "$MATH_ROOT")"
mkdir -p "$MATH_PARENT"
LOCK_DIR="$MATH_PARENT/.install-$MATHJAX_VERSION.lock"
OWNER_FILE="$LOCK_DIR/pid"
STAGING_FILE="$LOCK_DIR/staging"
HAVE_LOCK=0
STAGING_ROOT=""

acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    printf '%s\n' "$$" > "$OWNER_FILE"
    HAVE_LOCK=1
    return 0
  fi
  return 1
}

reclaim_stale_lock() {
  local owner_pid stale_staging current_owner
  [[ -f "$OWNER_FILE" ]] || return 1
  owner_pid="$(sed -n '1p' "$OWNER_FILE" 2>/dev/null || true)"
  if [[ "$owner_pid" =~ ^[0-9]+$ ]] && kill -0 "$owner_pid" 2>/dev/null; then
    return 1
  fi
  current_owner="$(sed -n '1p' "$OWNER_FILE" 2>/dev/null || true)"
  [[ "$current_owner" == "$owner_pid" ]] || return 1
  stale_staging=""
  if [[ -f "$STAGING_FILE" ]]; then
    IFS= read -r stale_staging < "$STAGING_FILE" || true
  fi
  case "$stale_staging" in
    "$MATH_PARENT/.install-$MATHJAX_VERSION-"*)
      if [[ -d "$stale_staging" && ! -L "$stale_staging" ]]; then
        rm -rf -- "$stale_staging"
      fi
      ;;
  esac
  rm -f -- "$STAGING_FILE" "$OWNER_FILE"
  rmdir "$LOCK_DIR" 2>/dev/null
}

if ! acquire_lock; then
  for ((attempt = 0; attempt < 30; attempt++)); do
    if node "$SCRIPT_DIR/mathjax_svg.js" --probe >/dev/null 2>&1; then
      echo "OK: another process installed the locked MathJax runtime"
      exit 0
    fi
    if reclaim_stale_lock; then
      acquire_lock && break
    elif [[ ! -d "$LOCK_DIR" ]]; then
      acquire_lock && break
    fi
    sleep 1
  done
  if (( ! HAVE_LOCK )); then
    # A process killed between mkdir and writing its owner leaves an empty
    # directory. After the bounded wait, reclaim only that exact empty lock.
    if [[ ! -e "$OWNER_FILE" && ! -e "$STAGING_FILE" ]]; then
      rmdir "$LOCK_DIR" 2>/dev/null || true
      acquire_lock || true
    fi
  fi
  if (( ! HAVE_LOCK )); then
    echo "ERROR: timed out waiting for the concurrent MathJax install" >&2
    exit 1
  fi
fi
cleanup() {
  if [[ -n "$STAGING_ROOT" && -d "$STAGING_ROOT" ]]; then
    rm -rf -- "$STAGING_ROOT"
  fi
  if [[ -f "$OWNER_FILE" ]]; then
    local owner_pid
    owner_pid="$(sed -n '1p' "$OWNER_FILE" 2>/dev/null || true)"
    if [[ "$owner_pid" == "$$" ]]; then
      rm -f -- "$STAGING_FILE" "$OWNER_FILE"
      rmdir "$LOCK_DIR" 2>/dev/null || true
    fi
  fi
}
trap cleanup EXIT

if node "$SCRIPT_DIR/mathjax_svg.js" --probe >/dev/null 2>&1; then
  echo "OK: another process installed the locked MathJax runtime"
  exit 0
fi
if [[ -e "$MATH_ROOT" ]]; then
  echo "ERROR: incomplete or invalid MathJax cache already exists at $MATH_ROOT" >&2
  echo "Move that version directory aside, then run this command again." >&2
  exit 1
fi
STAGING_ROOT="$(mktemp -d "$MATH_PARENT/.install-$MATHJAX_VERSION-XXXXXX")"
printf '%s\n' "$STAGING_ROOT" > "$STAGING_FILE"

echo "Installing locked MathJax $MATHJAX_VERSION for strict LaTeX SVG rendering"
cp "$RUNTIME_DIR/package.json" "$RUNTIME_DIR/package-lock.json" "$STAGING_ROOT/"
(
  cd "$STAGING_ROOT"
  npm ci --ignore-scripts --no-audit --no-fund
)

node - "$STAGING_ROOT" "$MATHJAX_VERSION" <<'NODE'
const root = process.argv[2];
const expected = process.argv[3];
const found = require(require.resolve("@mathjax/src/package.json", { paths: [root] })).version;
if (found !== expected) {
  throw new Error(`expected @mathjax/src ${expected}, found ${found}`);
}
NODE

mv "$STAGING_ROOT" "$MATH_ROOT"
rm -f -- "$STAGING_FILE" "$OWNER_FILE"
rmdir "$LOCK_DIR"
STAGING_ROOT=""
trap - EXIT
node "$SCRIPT_DIR/mathjax_svg.js" --probe >/dev/null
echo "OK: locked MathJax runtime installed"
