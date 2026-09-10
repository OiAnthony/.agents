# Read Methods Reference

## Helper Directory

Resolve once for the built-in fetcher, Feishu, or WeChat helper. Replace `<skill-base-dir>` with the installed Read skill or Waza dispatcher directory:

```bash
READ_SCRIPT_DIR=""
for candidate in \
  "<skill-base-dir>/scripts" \
  "<skill-base-dir>/skills/read/scripts"; do
  if [ -f "$candidate/fetch.sh" ]; then
    READ_SCRIPT_DIR="$candidate"
    break
  fi
done
if [ -z "$READ_SCRIPT_DIR" ]; then
  echo "read helper scripts not found under the installed skill base; reinstall Waza" >&2
  exit 1
fi
```

## Built-in Fetcher

```bash
bash "$READ_SCRIPT_DIR/fetch.sh" "{url}"
```

The script owns extraction order and content checks: request the source site and extract locally first. On failure, inspect its structured stderr. Only when the user has opted into third-party extraction for a public URL, run:

```bash
bash "$READ_SCRIPT_DIR/fetch.sh" --use-proxy "{url}"
```

Do not send authenticated, internal, or otherwise sensitive URLs to third-party extraction services or reader plugins. An installed plugin is an optional reader under the same privacy boundary, not automatic permission to disclose a URL. If a reader returns JSON, extract its Markdown-bearing field before answering or saving.

## GitHub URLs

GitHub file URLs (`github.com/user/repo/blob/...`) render heavy HTML. The proxy cascade often returns partial or nav-heavy content. Prefer:

```bash
# Raw file content (fastest)
curl -sL "https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}"

# Via gh CLI (works with private repos)
gh api repos/{user}/{repo}/contents/{path} --jq '.content' | base64 -d
```

Use the built-in fetcher only as a fallback for public GitHub pages that are not raw file views (e.g., issue threads, README renders). Keep private content on the authenticated `gh` path.

## PDF to Markdown

### Remote PDF URL

Download from the source site into a session temp directory and extract locally:

```bash
READ_PDF_DIR=$(mktemp -d)
curl -fL "{pdf_url}" -o "$READ_PDF_DIR/input.pdf"
pdftotext -layout "$READ_PDF_DIR/input.pdf" -
```

If local extraction fails, a third-party PDF reader may be used only for a public URL with user opt-in, under the same boundary as the built-in fetcher. Never treat failure as consent.

### Local PDF file

```bash
# Best quality (requires: pip install marker-pdf)
marker_single /path/to/file.pdf --output_dir "${READ_OUTPUT_DIR:-/tmp/waza-read}"

# Fast, text-heavy PDFs (requires: brew install poppler)
pdftotext -layout /path/to/file.pdf - | sed 's/\f/\n---\n/g'

# Python fallback (requires pypdf)
python3 -c "
import pypdf, sys
r = pypdf.PdfReader(sys.argv[1])
print('\n\n'.join(p.extract_text() for p in r.pages))
" /path/to/file.pdf
```

Use `marker` when layout matters (papers, tables). Use `pdftotext` for speed.

## Feishu / Lark Document

Use `READ_SCRIPT_DIR` from [Helper Directory](#helper-directory).

Requires `requests` and Feishu app credentials:

```bash
pip install requests  # one-time setup
export FEISHU_APP_ID=your_app_id
export FEISHU_APP_SECRET=your_app_secret
python3 "$READ_SCRIPT_DIR/fetch_feishu.py" "{url}"
```

Supports: docx and wiki pages. Legacy `/docs/` pages are not supported by this script; convert them to docx first, or use a public-page fallback if the document is accessible without the API. App needs `docx:document:readonly` and `wiki:wiki:readonly` permissions.
Output: YAML frontmatter (title, document_id, url) + Markdown body.

Do not tell every user to install `lark-cli` up front. Use it as the user-login fallback when the API helper fails because app credentials are missing, or when the user explicitly prefers OAuth login over `FEISHU_APP_ID` / `FEISHU_APP_SECRET`:

```bash
npm install -g @larksuite/cli  # one-time setup if lark-cli is absent
lark-cli auth login            # one-time login
lark-cli docs +fetch --doc "{url}" --format json
```

`lark-cli docs +fetch` returns structured document JSON, not final Markdown. Extract and convert the useful content before answering; do not return raw JSON.

## WeChat Public Account

Use [Built-in Fetcher](#built-in-fetcher) first, including its opt-in boundary for third-party extraction.

If extraction fails, use the built-in Playwright script to read the source page in a local browser (requires ~300 MB one-time install):

```bash
pip install playwright beautifulsoup4 lxml && playwright install chromium
python3 "$READ_SCRIPT_DIR/fetch_weixin.py" "{url}"
```
