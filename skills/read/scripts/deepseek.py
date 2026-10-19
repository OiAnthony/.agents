#!/usr/bin/env python3
"""Web search and page fetch through the DeepSeek Search/Fetch API.

Opt-in third-party tier: the query or URL is sent to DeepSeek and billed per
successful request. Needs DEEPSEEK_API_KEY; without it the script exits 2 and
nothing leaves the machine.

Usage:
  deepseek.py search "<query>" [--count N] [--content] [--json]
  deepseek.py fetch <url> [--json]

Every run writes one structured stderr line:
  [fetch] tier=deepseek status=<ok|fail> reason="..."
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.deepseek.com/v1/tools/"
TIMEOUT = 60


def log(status, reason=""):
    suffix = f' reason="{reason}"' if reason else ""
    print(f"[fetch] tier=deepseek status={status}{suffix}", file=sys.stderr)


def call(endpoint, body, key):
    req = urllib.request.Request(
        API + endpoint,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def api_error(exc):
    try:
        return json.loads(exc.read())["error"]["message"]
    except Exception:
        return f"HTTP {exc.code}"


def render_search(results):
    if not results:
        return "No results."
    lines = []
    for n, r in enumerate(results, 1):
        meta = [r.get("site_name") or "", (r.get("date") or "")[:10]]
        if r.get("authority", -1) >= 0:
            meta.append(f"authority {r['authority']}")
        if r.get("rerank_score") is not None:
            meta.append(f"score {r['rerank_score']:.2f}")
        lines.append(f"{n}. {r.get('title') or '(untitled)'}")
        lines.append(f"   {r.get('url', '')}")
        lines.append("   " + " · ".join(m for m in meta if m))
        text = (r.get("summary") or r.get("snippet") or "").strip()
        if text:
            lines.append("   " + " ".join(text.split()))
        if r.get("content"):
            lines.append("")
            lines.append(r["content"].strip())
        lines.append("")
    return "\n".join(lines).rstrip()


def render_fetch(url, data):
    title = data.get("title") or ""
    head = f"# {title}\n\nSource: {url}\n\n" if title else f"Source: {url}\n\n"
    return head + (data.get("content") or "").strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--count", type=int, default=10)
    s.add_argument("--content", action="store_true", help="include page bodies")
    s.add_argument("--json", action="store_true")
    f = sub.add_parser("fetch")
    f.add_argument("url")
    f.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        log("skip", "DEEPSEEK_API_KEY is not set")
        return 2

    if args.cmd == "search":
        if not 1 <= len(args.query) <= 128:
            log("fail", "query must be 1-128 characters")
            return 2
        body = {"query": args.query, "count": max(1, min(args.count, 50))}
        if args.content:
            body["need_content"] = True
    else:
        body = {"url": args.url}

    try:
        data = call(args.cmd, body, key)
    except urllib.error.HTTPError as exc:
        log("fail", api_error(exc))
        return 1
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        log("fail", type(exc).__name__)
        return 1

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
    elif args.cmd == "search":
        print(render_search(data.get("results", [])))
    else:
        print(render_fetch(args.url, data))
    log("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
