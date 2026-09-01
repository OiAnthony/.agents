#!/usr/bin/env python3
"""Lightweight tests for scripts/build.py and scripts/shared.py.

Run with: python3 scripts/tests/test_build.py
The harness uses plain assertions and a tiny runner so it has no third-party
dependency (matching the rest of the repo's lean tooling).
"""
from __future__ import annotations

import contextlib
import builtins
import hashlib
import importlib.util
import inspect
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tracemalloc
import warnings
import zipfile
from pathlib import Path

# Make scripts/ importable when running this file directly.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build import (  # noqa: E402
    DIAGRAM_TARGETS,
    HTML_TARGETS,
    PPTX_TARGETS,
    SCREEN_TARGETS,
    main as build_main,
)
from checks import (  # noqa: E402
    _BG_B,
    _BG_G,
    _BG_R,
    _density_bucket,
    _last_content_y,
    _markdown_residue_issues,
    _orphan_last_line,
    _parse_slide_sequence,
    _resume_balance_issues,
    _rhythm_issues,
    check_markdown_residue,
    check_placeholders,
    scan_density,
)
from lint import (  # noqa: E402
    NEGATIVE_EXAMPLE_LINE,
    _blank_block,
    _documented_snippets,
    _emphasis_container_findings,
    _extract_root_vars,
    _off_palette_findings,
    _pair_names,
    _root_token_findings,
    _undefined_token_findings,
    check_all,
    check_cross_template_consistency,
    check_off_palette,
    scan_file,
    scan_text,
)
from optional_deps import MissingDepError, require_pymupdf  # noqa: E402
from shared import (  # noqa: E402
    DIAGRAMS,
    DIAGRAM_TEMPLATES,
    HTML_TEMPLATES,
    MARP_TEMPLATES,
    PARCHMENT_RGB,
    ROOT as REPO_ROOT,
    SCREEN_TEMPLATES,
    TEMPLATES,
    build_targets,
    diagram_targets,
    load_checks_thresholds,
    marp_targets,
    pptx_targets,
    screen_targets,
)
import highlight as highlight_mod  # noqa: E402
import shared as shared_mod  # noqa: E402
import verify as verify_mod  # noqa: E402
from highlight import highlight_code_blocks  # noqa: E402
from site_facts import (  # noqa: E402
    FULL_PUBLIC_FACT_FILES,
    REDIRECT_SITE_FILE,
    check_site_facts,
    site_fact_issues,
    site_structure_issues,
)
from tokens import _mermaid_theme_drift  # noqa: E402
from verify import (  # noqa: E402
    RECOGNIZABLE_FALLBACK_FONT_MARKERS,
    _classify_cjk_font,
    _font_family_key,
)


# --------------------------- helpers ---------------------------

_PASS = 0
_FAIL = 0
_SKIP = 0


def check(name: str, predicate: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if predicate:
        _PASS += 1
        print(f"OK: {name}")
    else:
        _FAIL += 1
        print(f"ERROR: {name}{(' - ' + detail) if detail else ''}")


def skip(name: str, detail: str = "", *, ci_required: bool = False) -> None:
    """Record an unavailable optional-dependency test without calling it a pass."""
    global _SKIP, _FAIL
    _SKIP += 1
    if ci_required and os.environ.get("CI"):
        _FAIL += 1
        print(f"ERROR: required CI test skipped: {name}{(' - ' + detail) if detail else ''}")
    else:
        print(f"SKIP: {name}{(' - ' + detail) if detail else ''}")


def write_temp_html(body: str, suffix: str = "-en.html") -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(body)
    f.close()
    return Path(f.name)


def silently(callable_, *args, **kwargs):
    """Run a function with stdout suppressed, return its result."""
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink):
        return callable_(*args, **kwargs)


def run_build_args(args: list[str]) -> tuple[int, str]:
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink):
        rc = build_main(["build.py", *args])
    return rc, sink.getvalue()


def site_fact_file_map() -> dict[str, str]:
    rels = (*FULL_PUBLIC_FACT_FILES, REDIRECT_SITE_FILE)
    return {
        rel: (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        for rel in rels
    }


# --------------------------- package archive ---------------------------

PACKAGE_MAX_BYTES = 6_000_000
PACKAGE_ROOT_NAME = "kami"
PACKAGE_FORBIDDEN_EXACT = {
    ".claude-plugin/marketplace.json",
    ".gitignore",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "assets/images/1.png",
    "assets/images/2.png",
    "assets/images/3.png",
    "assets/fonts/TsangerJinKai02-W04.ttf",
    "assets/fonts/TsangerJinKai02-W05.ttf",
    "assets/fonts/SourceHanSerifKR-Regular.otf",
    "assets/fonts/SourceHanSerifKR-Medium.otf",
    "index.html",
    "index-en.html",
    "index-ja.html",
    "index-ko.html",
    "index-tw.html",
    "index-zh.html",
    "llms.txt",
    "robots.txt",
    "scripts/build_metadata.py",
    "scripts/draft-release-notes.py",
    "scripts/package-skill.sh",
    "sitemap.xml",
    "styles.css",
    "vercel.json",
}
PACKAGE_FORBIDDEN_PREFIXES = (
    ".agents/",
    ".claude/",
    ".github/",
    "assets/demos/",
    "assets/examples/",
    "assets/illustrations/",
    "assets/showcase/",
    "plugins/",
    "scripts/tests/",
)
PACKAGE_REQUIRED_ENTRIES = {
    "SKILL.md",
    "CHEATSHEET.md",
    "VERSION",
    "LICENSE",
    "assets/images/logo.svg",
    "assets/fonts/JetBrainsMono.woff2",
    "assets/templates/resume.html",
    "assets/templates/landing-page.html",
    "assets/diagrams/sequence.html",
    "references/design.md",
    "scripts/build.py",
    "scripts/ensure-fonts.sh",
    "scripts/ensure_mathjax.sh",
    "scripts/math_render.py",
    "scripts/mathjax_svg.js",
    "scripts/mathjax-runtime/package.json",
    "scripts/mathjax-runtime/package-lock.json",
    "scripts/site_facts.py",
}


def test_dist_package_contents() -> None:
    archive = REPO_ROOT / "dist" / "kami.zip"
    check("dist/kami.zip exists", archive.exists(), f"missing {archive}")
    if not archive.exists():
        return

    size_bytes = archive.stat().st_size
    check("dist/kami.zip stays below 6MB",
          size_bytes <= PACKAGE_MAX_BYTES,
          f"{size_bytes} bytes > {PACKAGE_MAX_BYTES} bytes")

    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())

    bad_root = sorted(name for name in names if not name.startswith(f"{PACKAGE_ROOT_NAME}/"))
    check("dist/kami.zip uses a Claude-friendly top-level skill folder",
          not bad_root,
          f"entries outside {PACKAGE_ROOT_NAME}/: {', '.join(bad_root)}")

    payload_names = {
        name.removeprefix(f"{PACKAGE_ROOT_NAME}/")
        for name in names
        if name.startswith(f"{PACKAGE_ROOT_NAME}/")
    }
    forbidden = sorted(
        name for name in payload_names
        if name.startswith(PACKAGE_FORBIDDEN_PREFIXES)
        or name in PACKAGE_FORBIDDEN_EXACT
    )
    check("dist/kami.zip excludes site, CI, tests, demos, generated mirrors, and large bundled fonts",
          not forbidden,
          f"forbidden entries: {', '.join(forbidden)}")
    missing_required = sorted(PACKAGE_REQUIRED_ENTRIES - payload_names)
    check("dist/kami.zip keeps required runtime skill files",
          not missing_required,
          f"missing entries: {', '.join(missing_required)}")

    # Structure alone cannot tell a current package from a stale one. The
    # plugin mirror has `build_metadata.py --check`; the ZIP had no equivalent,
    # so editing a source file and forgetting `package-skill.sh` left every
    # check green while the archive Claude Desktop users download stayed on the
    # old content. Compare what is inside against what it was built from.
    stale: list[str] = []
    absent: list[str] = []
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            source = REPO_ROOT / name.removeprefix(f"{PACKAGE_ROOT_NAME}/")
            if not source.exists():
                absent.append(name)
                continue
            if hashlib.sha256(zf.read(name)).digest() != hashlib.sha256(source.read_bytes()).digest():
                stale.append(name)
    check("dist/kami.zip matches the sources it was built from",
          not stale,
          f"{len(stale)} stale entr(ies): {', '.join(sorted(stale)[:5])}"
          " -- run `bash scripts/package-skill.sh`")
    check("dist/kami.zip carries no entry missing from the repo",
          not absent,
          f"entries with no source: {', '.join(sorted(absent)[:5])}")


def test_package_failure_preserves_last_good_archive() -> None:
    """A failed audit must not replace the last archive users can install."""
    script = REPO_ROOT / "scripts" / "package-skill.sh"
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        out = root / "kami.zip"
        out.write_bytes(b"last-good")
        env = dict(os.environ, KAMI_PACKAGE_MAX_BYTES="1")
        result = subprocess.run(
            ["bash", str(script), str(out)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env=env,
        )
        leftovers = list(root.glob(".kami-package.*"))
        check("failed package audit preserves the last good archive",
              result.returncode == 1 and out.read_bytes() == b"last-good",
              (result.stdout + result.stderr).strip())
        check("failed package audit removes its candidate directory",
              leftovers == [], str(leftovers))


def test_plugin_metadata_generated() -> None:
    """Claude Code / Codex marketplaces and plugin mirrors must stay generated."""
    script = REPO_ROOT / "scripts" / "build_metadata.py"
    check("build_metadata.py exists", script.exists(), f"missing {script}")
    if not script.exists():
        return

    result = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    detail = (result.stdout + result.stderr).strip()
    check("plugin metadata matches generator", result.returncode == 0, detail)


def test_claude_plugin_marketplace_version_matches_version_file() -> None:
    """Claude Code uses this version instead of falling back to a commit hash."""
    version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    marketplace_file = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    check("Claude plugin marketplace metadata exists", marketplace_file.exists())
    if not marketplace_file.exists():
        return

    marketplace = json.loads(marketplace_file.read_text(encoding="utf-8"))
    plugins = marketplace.get("plugins", [])
    kami_plugin = next((plugin for plugin in plugins if plugin.get("name") == "kami"), None)
    check("Claude plugin marketplace includes kami", kami_plugin is not None)
    if not kami_plugin:
        return

    check("Claude plugin marketplace version matches VERSION",
          kami_plugin.get("version") == version,
          f"marketplace={kami_plugin.get('version')!r}, VERSION={version!r}")
    check("Claude plugin marketplace installs the lightweight plugin directory",
          kami_plugin.get("source") == "./plugins/kami",
          f"source={kami_plugin.get('source')!r}")

    plugin_file = REPO_ROOT / "plugins" / "kami" / ".claude-plugin" / "plugin.json"
    check("Claude plugin manifest exists in generated plugin tree", plugin_file.exists())
    if not plugin_file.exists():
        return

    plugin = json.loads(plugin_file.read_text(encoding="utf-8"))
    check("Claude plugin manifest version matches VERSION",
          plugin.get("version") == version,
          f"plugin={plugin.get('version')!r}, VERSION={version!r}")
    check("Claude plugin manifest exposes skills directory",
          plugin.get("skills") == "./skills/",
          f"skills={plugin.get('skills')!r}")


def test_build_metadata_reads_tokens_from_root_argument() -> None:
    from build_metadata import build_codex_plugin, read_token_value

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "references").mkdir()
        (root / "references" / "tokens.json").write_text('{"--brand":"#123456"}\n', encoding="utf-8")

        brand_color = read_token_value(root, "brand")
        plugin = build_codex_plugin("9.9.9", brand_color)
        check("build_metadata reads brand token from provided root",
              plugin["interface"]["brandColor"] == "#123456",
              f"brandColor={plugin['interface']['brandColor']}")


def test_catalog_lists_pptx_for_slides() -> None:
    from build_metadata import build_catalog_feed

    catalog = json.loads(build_catalog_feed(REPO_ROOT))
    slide = next(
        entry["item"]
        for entry in catalog["itemListElement"]
        if entry["item"].get("identifier") == "slides"
    )
    pptx_mime = (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    check("catalog advertises the editable PPTX slide format",
          pptx_mime in slide.get("encodingFormat", []),
          str(slide.get("encodingFormat")))


# --------------------------- shared registry ---------------------------

def test_registry_consistency() -> None:
    check("HTML_TEMPLATES has 24 entries", len(HTML_TEMPLATES) == 24,
          f"got {len(HTML_TEMPLATES)}")
    check("SCREEN_TARGETS has 3 entries", len(SCREEN_TARGETS) == 3,
          f"got {len(SCREEN_TARGETS)}")
    check("build_targets matches HTML_TEMPLATES key set",
          set(build_targets()) == set(HTML_TEMPLATES))
    check("screen_targets matches SCREEN_TARGETS key set",
          set(screen_targets()) == set(SCREEN_TARGETS))
    check("HTML_TARGETS in build.py matches build_targets()",
          dict(HTML_TARGETS) == build_targets())
    check("DIAGRAM_TARGETS has 18 entries", len(DIAGRAM_TARGETS) == 18,
          f"got {len(DIAGRAM_TARGETS)}")
    check("DIAGRAM_TARGETS in build.py matches shared.diagram_targets()",
          dict(DIAGRAM_TARGETS) == diagram_targets() == dict(DIAGRAM_TEMPLATES))
    check("PPTX_TARGETS has 2 entries", len(PPTX_TARGETS) == 2,
          f"got {len(PPTX_TARGETS)}")
    check("PPTX_TARGETS in build.py matches shared.pptx_targets()",
          dict(PPTX_TARGETS) == pptx_targets())
    registered_sources = {
        **{f"html:{name}": TEMPLATES / spec.source
           for name, spec in HTML_TEMPLATES.items()},
        **{f"screen:{name}": TEMPLATES / source
           for name, source in SCREEN_TEMPLATES.items()},
        **{f"pptx:{name}": TEMPLATES / source
           for name, source in pptx_targets().items()},
        **{f"diagram:{name}": DIAGRAMS / source
           for name, source in DIAGRAM_TEMPLATES.items()},
        **{f"marp:{name}": TEMPLATES / source
           for name, source in MARP_TEMPLATES.items()},
    }
    missing_sources = sorted(
        f"{name} -> {path.relative_to(REPO_ROOT)}"
        for name, path in registered_sources.items()
        if not path.is_file()
    )
    check("every registered template source exists",
          missing_sources == [], ", ".join(missing_sources))
    check("Marp registry maps authoring entries with matching CSS",
          marp_targets() == MARP_TEMPLATES
          and all(
              (TEMPLATES / source).exists()
              and (TEMPLATES / source).with_suffix(".css").exists()
              for source in MARP_TEMPLATES.values()
          ),
          str(MARP_TEMPLATES))
    check("PARCHMENT_RGB is canonical", PARCHMENT_RGB == (0xF5, 0xF4, 0xED))


def test_ci_builds_registered_hard_page_and_pptx_targets() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "check.yml").read_text(
        encoding="utf-8")
    check("CI installs the editable PPTX runtime dependency",
          "python-pptx" in workflow)
    check("CI derives hard-page verification from the shared registry",
          "from shared import HTML_TEMPLATES" in workflow
          and "if spec.build_max_pages" in workflow)
    check("CI verifies both editable PPTX targets",
          "--verify slides\n" in workflow and "--verify slides-en" in workflow)


def test_public_document_kinds_derive_new_registry_entries() -> None:
    from shared import TemplateSpec, public_document_template_kinds

    shared_mod.HTML_TEMPLATES["invoice"] = TemplateSpec("invoice.html", 1)
    try:
        kinds = public_document_template_kinds()
    finally:
        shared_mod.HTML_TEMPLATES.pop("invoice", None)
    check("new registry kinds cannot disappear behind the public-kind allowlist",
          "invoice" in kinds,
          str(sorted(kinds)))


def test_threshold_fallback_includes_resume_balance() -> None:
    original = shared_mod.CHECKS_THRESHOLDS_FILE
    with tempfile.TemporaryDirectory() as d:
        shared_mod.CHECKS_THRESHOLDS_FILE = Path(d) / "missing-thresholds.json"
        shared_mod.load_checks_thresholds.cache_clear()
        try:
            resume = shared_mod.load_checks_thresholds().get("resume_balance")
        finally:
            shared_mod.CHECKS_THRESHOLDS_FILE = original
            shared_mod.load_checks_thresholds.cache_clear()
    check("threshold fallback keeps the resume balance contract",
          resume == {
              "min_fill_pct": 0.83,
              "max_fill_pct": 0.95,
              "max_gap_pct": 0.12,
              "dpi": 36,
          },
          repr(resume))


def test_runner_auto_discovers_tests() -> None:
    names = [name for name, _ in _test_functions()]
    check("test runner auto-discovers Codex update command test",
          "test_check_update_uses_codex_plugin_update_command" in names)
    check("test runner auto-discovers this test",
          "test_runner_auto_discovers_tests" in names)


def test_build_cli_rejects_unexpected_flags() -> None:
    rc, out = run_build_args(["resume", "--verify"])
    check("build.py rejects flags after target",
          rc == 2 and "ERROR: unexpected argument: --verify" in out,
          out.strip())

    rc, out = run_build_args(["--check-density", "-v"])
    check("build.py rejects unknown flags for path-based checks",
          rc == 2 and "ERROR: unexpected argument: -v" in out,
          out.strip())

    rc, out = run_build_args(["--verify", "-v"])
    check("build.py rejects unknown --verify flags",
          rc == 2 and "ERROR: unexpected argument: -v" in out,
          out.strip())

    rc, out = run_build_args(["--check-markdown", "-v"])
    check("build.py rejects unknown --check-markdown flags",
          rc == 2 and "ERROR: unexpected argument: -v" in out,
          out.strip())


def test_long_doc_templates_use_rendered_toc_pages_and_chapter_headers() -> None:
    """Long-doc TOCs must use WeasyPrint target-counter, and running headers
    must follow chapter h1 titles instead of getting stuck on the TOC h2.
    """
    sources = ("long-doc.html", "long-doc-en.html", "long-doc-ko.html")
    required_ids = {
        "#ch-executive-summary",
        "#ch-background",
        "#ch-methodology",
        "#ch-conclusions",
        "#ch-appendix",
    }
    offenders: list[str] = []
    for source in sources:
        text = (TEMPLATES / source).read_text(encoding="utf-8")
        if "target-counter(attr(href), page)" not in text:
            offenders.append(f"{source}: missing target-counter")
        if ".toc-page" in text:
            offenders.append(f"{source}: still has obsolete toc-page wiring")
        missing_ids = sorted(href for href in required_ids if f'href="{href}"' not in text or f'id="{href[1:]}"' not in text)
        if missing_ids:
            offenders.append(f"{source}: missing TOC href/id pairs {missing_ids}")
        h1_block = re.search(r"(?m)^  h1\s*\{(?P<body>.*?)^  \}", text, re.S)
        if not h1_block or "string-set: section-title content();" not in h1_block.group("body"):
            offenders.append(f"{source}: h1 does not set running header")
        h2_block = re.search(r"(?m)^  h2\s*\{(?P<body>.*?)^  \}", text, re.S)
        if h2_block and "string-set:" in h2_block.group("body"):
            offenders.append(f"{source}: h2 still sets running header")

    check("long-doc templates use rendered TOC pages and chapter headers",
          not offenders,
          "; ".join(offenders))


def test_site_facts_repo_clean() -> None:
    rc = silently(check_site_facts, False)
    check("public site facts match shared constants and registries", rc == 0,
          f"check_site_facts returned {rc}")


def test_site_facts_flags_bad_diagram_count() -> None:
    files = site_fact_file_map()
    bad = files["index.html"]
    bad = bad.replace("18 inline SVG diagram types", "17 inline SVG diagram types")
    bad = bad.replace("Eighteen inline SVG diagram types", "Seventeen inline SVG diagram types")
    files["index.html"] = bad

    issues = site_fact_issues(files)
    check("public site facts flag stale diagram counts",
          any("index.html: missing diagram count 18" in issue for issue in issues),
          f"issues: {issues}")


def test_site_facts_cover_developer_install_docs() -> None:
    files = site_fact_file_map()
    command = "npx skills add tw93/kami/plugins/kami -a universal -g -y"
    files["developers.md"] = files["developers.md"].replace(command, "npx skills add stale/path")
    issues = site_fact_issues(files)
    check("public site facts flag stale developer install docs",
          any("developers.md: missing generic agent install command" in issue
              for issue in issues),
          f"issues: {issues}")


def test_site_structure_repo_clean() -> None:
    """Locale pages match index.html's DOM skeleton (redirect script exempt)."""
    issues = site_structure_issues()
    check("locale page structure matches index.html", not issues,
          f"issues: {issues}")


def test_site_structure_flags_locale_drift() -> None:
    files = site_fact_file_map()
    files["index-zh.html"] = files["index-zh.html"].replace(
        '<h2 class="section-title">', '<h3 class="section-title">', 1)

    issues = site_structure_issues(files)
    check("locale structure check flags a drifted heading",
          any("index-zh.html: DOM skeleton drifted" in issue for issue in issues),
          f"issues: {issues}")


def test_chinese_html_templates_keep_single_serif_stack() -> None:
    """Chinese templates must keep --sans pinned to --serif for PDF glyph safety."""
    offenders: list[str] = []
    for name, spec in HTML_TEMPLATES.items():
        source = spec.source
        if name.endswith("-en"):
            continue
        text = (TEMPLATES / source).read_text(encoding="utf-8")
        if "--sans: var(--serif)" not in text and "--sans:  var(--serif)" not in text:
            offenders.append(source)

    check("Chinese HTML templates keep --sans: var(--serif)",
          not offenders,
          f"offenders: {', '.join(offenders)}")


def _ko_stack_offenders(text: str) -> list[str]:
    """Return CSS declarations that reference the bare `"Source Han Serif K"`
    family inside a multi-name fallback stack but omit the real OTF family
    name `"Source Han Serif KR"`.

    The bare name `"Source Han Serif K"` is legitimate on its own only as the
    `@font-face` declared alias (a single-name `font-family: "Source Han Serif K";`
    with no comma, which loads via the file/CDN `src`). Anywhere it appears as a
    fallback item in a comma-separated stack (`--serif`, `--mono`, `@page`
    margin boxes, `code`/`pre`, ...), `"Source Han Serif KR"` MUST sit alongside
    it, or an offline Linux skill install cannot resolve the
    ensure-fonts.sh-downloaded font by name.

    Detection: scan only `font-family` / `--serif` / `--sans` / `--mono`
    declaration values (up to the next `;`, never crossing `{`/`}`). The token
    `"Source Han Serif K"` (closing quote after `K`) never matches
    `"Source Han Serif KR"`, so a value that contains the bare token AND a comma
    (i.e. a fallback stack, not a bare `@font-face` alias) must also contain KR.
    """
    bare = '"Source Han Serif K"'
    kr = '"Source Han Serif KR"'
    decl_re = re.compile(r"(?:font-family|--serif|--sans|--mono)\s*:\s*([^;{}]*)", re.IGNORECASE)
    offenders: list[str] = []
    for m in decl_re.finditer(text):
        value = m.group(1)
        if bare in value and "," in value and kr not in value:
            offenders.append(" ".join(value.split()))
    return offenders


def test_korean_templates_carry_resolvable_serif_name() -> None:
    """Every KO fallback stack that names `Source Han Serif K` must also name
    `Source Han Serif KR` (the actual family of the bundled OTFs), so the font
    resolves by name on an offline Linux skill install. Checks per-declaration,
    not just per-file, so a complete `--serif` cannot mask an incomplete local
    stack (page-margin header/footer, code/pre, mono).
    """
    offenders: list[str] = []
    ko_sources = [spec.source for name, spec in HTML_TEMPLATES.items() if name.endswith("-ko")]
    ko_sources += [source for name, source in SCREEN_TEMPLATES.items() if name.endswith("-ko")]
    # Guard against vacuous green: with zero -ko templates the offender loop
    # never runs and the check below would pass while enforcing nothing.
    check("Korean template set is non-empty", bool(ko_sources),
          "no -ko templates found in the registries")
    for source in ko_sources:
        text = (TEMPLATES / source).read_text(encoding="utf-8")
        for bad in _ko_stack_offenders(text):
            offenders.append(f"{source}: {bad}")

    check("Korean fallback stacks all carry Source Han Serif KR",
          not offenders,
          f"offenders: {'; '.join(offenders)}")


# ---------- sibling placeholder parity (issue #38 class) ----------

# Repeated template structures whose placeholder hints must repeat the first
# block verbatim. Hint richness degrading from block 1 to later siblings makes
# fillers (human or agent) produce degraded copy; see issue #38. Cycle length N
# means placeholders repeat in groups of N (e.g. Role/Actions/Impact rows).
_SIBLING_PARITY_SPECS = (
    ("resume*.html", r'class="proj-text">(\{\{.*?\}\})', 3),
    ("resume*.html", r'class="proj-role">(\{\{.*?\}\})', 1),
    ("resume*.html", r'class="conv-body">\s*(\{\{.*?\}\})', 1),
    ("resume*.html", r'class="os-desc">(\{\{.*?\}\})', 1),
    ("resume*.html", r'class="art-stats">(\{\{.*?\}\})', 1),
    ("portfolio*.html", r'class="project-block">\s*<h3>[^<]*</h3>\s*<p>(\{\{.*?\}\})</p>', 3),
    ("portfolio*.html", r'class="project-type">(\{\{.*?\}\})', 1),
    ("portfolio*.html", r'class="project-date">(\{\{.*?\}\})', 1),
    ("one-pager*.html", r'<li>(\{\{(?:短 bullet|Short bullet|짧은 bullet).*?\}\})</li>', 3),
    ("long-doc*.html", r'(\{\{(?:一段论述|A paragraph|한 단락 논술).*?\}\})', 1),
)


def test_sibling_placeholder_hints_stay_in_parity() -> None:
    """Same-structure sibling blocks must carry identical placeholder hints."""
    matched = 0
    offenders: list[str] = []
    for glob_pattern, regex, cycle in _SIBLING_PARITY_SPECS:
        rx = re.compile(regex, re.DOTALL)
        for path in sorted(TEMPLATES.glob(glob_pattern)):
            hits = rx.findall(path.read_text(encoding="utf-8"))
            if not hits:
                offenders.append(f"{path.name}: no match for {regex[:40]!r} (stale spec?)")
                continue
            matched += 1
            if len(hits) % cycle != 0:
                offenders.append(f"{path.name}: {len(hits)} hint(s) not divisible by cycle {cycle}")
                continue
            first = hits[:cycle]
            for start in range(cycle, len(hits), cycle):
                block = hits[start:start + cycle]
                if block != first:
                    offenders.append(
                        f"{path.name}: block {start // cycle + 1} diverges from block 1: "
                        f"{block} != {first}")
    check("sibling parity specs matched across template families", matched >= 30,
          f"only {matched} template/spec matches; spec table may be stale")
    check("repeated blocks carry identical placeholder hints", not offenders,
          "; ".join(offenders[:6]))


def test_font_fallback_markers_recognize_pt_serif() -> None:
    """macOS without Charter may render English fallbacks as PT Serif."""
    embedded = {"DROIWJ+PT-Serif", "ZBEAAE+JetBrains-Mono"}
    fallback_present = any(
        marker in font for font in embedded
        for marker in RECOGNIZABLE_FALLBACK_FONT_MARKERS
    )
    check("font fallback markers recognize PT-Serif",
          fallback_present,
          f"markers: {RECOGNIZABLE_FALLBACK_FONT_MARKERS}")


def test_font_probe_rejects_empty_and_truncated_bundles() -> None:
    import optional_deps as optional_deps_mod

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        font_dir = root / "assets" / "fonts"
        font_dir.mkdir(parents=True)
        (font_dir / "Empty.ttf").write_bytes(b"")
        (font_dir / "Truncated.otf").write_bytes(
            b"OTTO\x00\x01\x00\x00\x00\x00\x00\x00"
        )

        original_root = optional_deps_mod.ROOT
        original_which = optional_deps_mod.shutil.which
        try:
            optional_deps_mod.ROOT = root
            optional_deps_mod.shutil.which = lambda _name: None
            report = optional_deps_mod._probe_font(
                "Broken Font",
                ("Empty.ttf", "Truncated.otf"),
                "negative-control font",
            )
        finally:
            optional_deps_mod.ROOT = original_root
            optional_deps_mod.shutil.which = original_which

    check("font probe rejects empty and truncated bundled files",
          report["status"] == "degraded"
          and report["bundled"] == []
          and "Empty.ttf" in report["detail"]
          and "Truncated.otf" in report["detail"],
          str(report))


def test_print_surfaces_have_no_ornamental_brand_lines() -> None:
    """Print hierarchy comes from type, spacing, labels, and fill, not ticks."""
    patterns = {
        "brand side rule": re.compile(
            r"border-left:\s*[\d.]+(?:pt|px)\s+solid\s+var\(--brand\)"
        ),
        "eyebrow tick": re.compile(
            r"\.(?:eyebrow|ticker-eyebrow|cover-eyebrow)::before"
        ),
        "short cover or contact rule": re.compile(
            r"(?:class=[\"'](?:cover-line|contact-line)[\"']|"
            r"\.(?:cover-line|contact-line)\s*\{)"
        ),
    }
    offenders: list[str] = []
    sources = list(TEMPLATES.glob("*.html")) + list((REPO_ROOT / "assets" / "demos").glob("*.html"))
    for path in sorted(sources):
        text = path.read_text(encoding="utf-8")
        for label, pattern in patterns.items():
            if pattern.search(text):
                offenders.append(f"{path.name}: {label}")

    for name in ("slides.py", "slides-en.py"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        if "def add_line(" in text:
            offenders.append(f"{name}: generic decorative add_line helper")

    check("print surfaces contain no ornamental brand lines",
          not offenders,
          f"offenders: {', '.join(offenders)}")


def test_shipped_surfaces_keep_subtractive_defaults() -> None:
    """A default surface stays flat, small-radius, and free of filler motion."""
    offenders: list[str] = []

    print_sources = [
        path for path in TEMPLATES.glob("*.html")
        if not path.name.startswith("landing-page")
    ] + list((REPO_ROOT / "assets" / "demos").glob("*.html"))
    large_print_radius = re.compile(
        r"border-radius:\s*(?:[789]|[1-9][0-9])(?:\.[0-9]+)?pt"
    )
    for path in sorted(print_sources):
        if large_print_radius.search(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.name}: screen-sized print radius")

    landing_forbidden = (
        "filter: blur",
        "linear-gradient(",
        ".gallery-frame::after",
    )
    default_surface_selectors = (
        ".hero",
        ".section-head",
        ".demo-card",
        ".price-card",
        ".gallery-caption",
    )
    for path in sorted(TEMPLATES.glob("landing-page*.html")):
        text = path.read_text(encoding="utf-8")
        for token in landing_forbidden:
            if token in text:
                offenders.append(f"{path.name}: {token}")
        for selector in default_surface_selectors:
            match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", text, re.DOTALL)
            if match and "box-shadow" in match.group(1):
                offenders.append(f"{path.name}: {selector} shadow")

    public_pages = [
        REPO_ROOT / "index.html",
        REPO_ROOT / "index-zh.html",
        REPO_ROOT / "index-tw.html",
        REPO_ROOT / "index-ja.html",
        REPO_ROOT / "index-ko.html",
    ]
    public_forbidden = (
        "border-left: 1.4pt solid var(--brand)",
        "box-shadow: 0 4px 24px",
        'class="dash demo"',
        'class="tag brush"',
        'class="shadow-row"',
    )
    for path in public_pages:
        text = path.read_text(encoding="utf-8")
        for token in public_forbidden:
            if token in text:
                offenders.append(f"{path.name}: {token}")

    site_css = (REPO_ROOT / "styles.css").read_text(encoding="utf-8")
    for token in ("@keyframes fadeIn", "ul.dash", ".tag.brush", ".shadow-row"):
        if token in site_css:
            offenders.append(f"styles.css: {token}")

    for selector in (".family", ".comp", ".chart-card", ".quote"):
        match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", site_css, re.DOTALL)
        block = match.group(1) if match else ""
        if "box-shadow" in block:
            offenders.append(f"styles.css: {selector} shadow")
        if selector in {".family", ".comp", ".chart-card"} and re.search(
                r"\bborder:\s*1px", block):
            offenders.append(f"styles.css: {selector} stacked border")
        if selector == ".quote" and "border-left" in block:
            offenders.append("styles.css: quote side rule")

    check("shipped surfaces keep subtractive visual defaults",
          not offenders,
          f"offenders: {', '.join(offenders)}")


def test_print_radius_guidance_matches_shipped_range() -> None:
    """The quick reference must describe the same restrained range as templates."""
    cheatsheet = (REPO_ROOT / "CHEATSHEET.md").read_text(encoding="utf-8")
    design = (REPO_ROOT / "references" / "design.md").read_text(encoding="utf-8")
    check("print radius guidance matches shipped 2-6pt range",
          "within `2-6pt`" in cheatsheet
          and "within 2-6pt" in design
          and "Do not invent intermediate steps" not in cheatsheet,
          "radius guidance drifted from shipped template values")


def test_public_site_typography_contract_matches_templates() -> None:
    """Public prose must teach the one-serif contract templates actually ship."""
    pages = [
        REPO_ROOT / "index.html",
        REPO_ROOT / "index-zh.html",
        REPO_ROOT / "index-tw.html",
        REPO_ROOT / "index-ja.html",
        REPO_ROOT / "index-ko.html",
    ]
    stale = (
        "Chinese uses serif headlines and sans body",
        "中文标题用 serif、正文用 sans",
        "中文標題用 serif、正文用 sans",
        "중문은 제목에 세리프, 본문에 산세리프",
    )
    offenders = [
        path.name for path in pages
        if any(token in path.read_text(encoding="utf-8") for token in stale)
    ]
    design = (REPO_ROOT / "references" / "design.md").read_text(encoding="utf-8")
    check("public typography contract matches one-serif templates",
          not offenders
          and "One serif family per page for headlines and body" in design,
          f"offenders: {', '.join(offenders)}")


def test_landing_page_ctas_stack_at_320px() -> None:
    """Localized double CTAs must fit the smallest supported viewport."""
    offenders = []
    for path in sorted(TEMPLATES.glob("landing-page*.html")):
        text = path.read_text(encoding="utf-8")
        if not (
            "@media (max-width: 360px)" in text
            and ".hero-cta { flex-direction: column; align-items: stretch" in text
            and ".btn-ghost { width: 100%; }" in text
        ):
            offenders.append(path.name)
    check("landing page CTAs stack at 320px",
          not offenders,
          f"offenders: {', '.join(offenders)}")


def test_public_site_og_dimensions_match_showcase_image() -> None:
    """Social metadata must describe the image bytes platforms will fetch."""
    image = (REPO_ROOT / "assets" / "showcase" / "kami-landing.png").read_bytes()
    valid_png = image[:8] == b"\x89PNG\r\n\x1a\n" and image[12:16] == b"IHDR"
    width = int.from_bytes(image[16:20], "big") if valid_png else 0
    height = int.from_bytes(image[20:24], "big") if valid_png else 0
    offenders = []
    for name in ("index.html", "index-zh.html", "index-tw.html", "index-ja.html", "index-ko.html"):
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        declared_width = re.search(r'og:image:width" content="(\d+)"', text)
        declared_height = re.search(r'og:image:height" content="(\d+)"', text)
        if not (
            declared_width and int(declared_width.group(1)) == width
            and declared_height and int(declared_height.group(1)) == height
        ):
            offenders.append(name)
    check("public OG dimensions match the showcase PNG",
          valid_png and not offenders,
          f"image={width}x{height} offenders={', '.join(offenders)}")


def test_public_site_teaches_registered_tints_and_exact_radii() -> None:
    """Visible examples must describe tokens, not obsolete alpha recipes."""
    pages = [
        REPO_ROOT / "index.html",
        REPO_ROOT / "index-zh.html",
        REPO_ROOT / "index-tw.html",
        REPO_ROOT / "index-ja.html",
        REPO_ROOT / "index-ko.html",
    ]
    stale_tint_labels = (
        'class="opacity">0.18',
        'class="tag calm">Light 0.08',
        'class="tag standard">Standard 0.18',
        'class="tag calm">极淡 0.08',
        'class="tag standard">标准 0.18',
        'class="tag calm">極淡 0.08',
        'class="tag standard">標準 0.18',
        "equivalent solid hex",
        "等效实色",
        "等效實色",
        "등가 솔리드 hex",
    )
    offenders: list[str] = []
    for path in pages:
        text = path.read_text(encoding="utf-8")
        for token in stale_tint_labels:
            if token in text:
                offenders.append(f"{path.name}: {token}")
        for radius in ("2", "4"):
            if f'class="box" style="border-radius:{radius}px"' in text:
                offenders.append(f"{path.name}: {radius}px print radius")
            if f'class="box" style="border-radius:{radius}pt"' not in text:
                offenders.append(f"{path.name}: missing {radius}pt print radius")

    check("public site teaches registered tints and exact print radii",
          not offenders,
          f"offenders: {', '.join(offenders)}")


def test_reviewed_demo_details_keep_quiet_hierarchy() -> None:
    """Small editorial cues should not turn back into colored or framed UI."""
    def css_block(text: str, selector: str) -> str:
        match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", text, re.DOTALL)
        return match.group(1) if match else ""

    offenders: list[str] = []
    resume_surfaces = [
        TEMPLATES / "resume.html",
        TEMPLATES / "resume-en.html",
        TEMPLATES / "resume-ko.html",
        REPO_ROOT / "assets" / "demos" / "demo-musk-resume.html",
        REPO_ROOT / "assets" / "demos" / "demo-resume-ko.html",
    ]
    for path in resume_surfaces:
        text = path.read_text(encoding="utf-8")
        highlight = css_block(text, ".os-highlight")
        label = css_block(text, ".os-highlight .tag")
        if "background: var(--ivory)" not in highlight:
            offenders.append(f"{path.name}: chromatic highlight fill")
        if "background: transparent" not in label or "color: var(--brand)" not in label:
            offenders.append(f"{path.name}: filled highlight label")

    print_demo = (REPO_ROOT / "assets" / "demos" / "demo-kami-print.html").read_text(
        encoding="utf-8"
    )
    command = css_block(print_demo, ".cmd")
    if re.search(r"(?:^|[;\n])\s*border\s*:", command):
        offenders.append("demo-kami-print.html: framed command block")
    if "border-radius: 4pt" not in command:
        offenders.append("demo-kami-print.html: command block radius")

    slides_demo = (REPO_ROOT / "assets" / "demos" / "demo-agent-slides.html").read_text(
        encoding="utf-8"
    )
    suffix = css_block(slides_demo, ".metric .metric-suffix")
    if '<span class="metric-suffix">×</span>' not in slides_demo:
        offenders.append("demo-agent-slides.html: multiplier markup")
    if "font-size: 0.58em" not in suffix or "vertical-align: 0.08em" not in suffix:
        offenders.append("demo-agent-slides.html: multiplier optics")

    check("reviewed demo details keep quiet hierarchy",
          not offenders,
          f"offenders: {', '.join(offenders)}")


def test_table_components_keep_one_quiet_rule_system() -> None:
    """Tables should read as content first, with rules acting as quiet guides."""
    def css_block(text: str, selector: str) -> str:
        match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", text, re.DOTALL)
        return match.group(1) if match else ""

    def vertical_padding(block: str) -> float:
        match = re.search(r"padding:\s*([\d.]+)pt", block)
        return float(match.group(1)) if match else -1

    documents = []
    offenders: list[str] = []
    for path in sorted(TEMPLATES.glob("*.html")):
        text = path.read_text(encoding="utf-8")
        if ".kami-table" not in text:
            continue
        documents.append(path)
        header = css_block(text, "table th, .kami-table th")
        body = css_block(text, "table td, .kami-table td")
        compact_header = css_block(text, "table.compact th, .kami-table.compact th")
        compact_body = css_block(text, "table.compact td, .kami-table.compact td")
        total = css_block(text, "table .total td, .kami-table .total td")

        if "border-bottom: 0.6pt solid var(--border)" not in header:
            offenders.append(f"{path.name}: header rule")
        if "border-bottom: 0.25pt solid var(--border)" not in body:
            offenders.append(f"{path.name}: body rule")
        if "border-top: 0.6pt solid var(--border)" not in total:
            offenders.append(f"{path.name}: total rule")
        if "var(--brand)" in "\n".join((header, body, total)):
            offenders.append(f"{path.name}: accent-colored rule")

        if path.name.startswith("one-pager"):
            header_floor, body_floor = 5.0, 4.0
        elif path.name.startswith("resume"):
            header_floor, body_floor = 5.0, 4.0
        else:
            header_floor, body_floor = 6.0, 5.0
        if vertical_padding(header) < header_floor:
            offenders.append(f"{path.name}: header padding")
        if vertical_padding(body) < body_floor:
            offenders.append(f"{path.name}: body padding")
        if vertical_padding(compact_header) < 3.0:
            offenders.append(f"{path.name}: compact header padding")
        if vertical_padding(compact_body) < 2.5:
            offenders.append(f"{path.name}: compact body padding")

    check("all document families ship the shared table component",
          len(documents) == 18,
          f"found {len(documents)}: {', '.join(path.name for path in documents)}")
    check("document tables use neutral hairlines and readable row padding",
          not offenders,
          f"offenders: {', '.join(offenders)}")

    slide_paths = [
        TEMPLATES / "slides-weasy.html",
        TEMPLATES / "slides-weasy-en.html",
        TEMPLATES / "slides-weasy-ko.html",
        TEMPLATES / "marp" / "slides-marp.css",
        TEMPLATES / "marp" / "slides-marp-en.css",
    ]
    slide_offenders = []
    for path in slide_paths:
        text = path.read_text(encoding="utf-8")
        body = css_block(text, "table.data td")
        first = css_block(text, "table.data td:first-child")
        if "border-bottom: 0.25pt solid var(--border)" not in body:
            slide_offenders.append(f"{path.name}: body rule")
        if "color: var(--dark-warm)" not in first or "var(--brand)" in first:
            slide_offenders.append(f"{path.name}: first-column color")
        if vertical_padding(body) < 8.0:
            slide_offenders.append(f"{path.name}: row padding")
    check("slide data tables use the same quiet neutral system",
          not slide_offenders,
          f"offenders: {', '.join(slide_offenders)}")

    default_stripes = []
    for path in sorted(TEMPLATES.glob("equity-report*.html")):
        text = path.read_text(encoding="utf-8")
        if re.search(r'<table[^>]*class="[^"]*striped', text):
            default_stripes.append(path.name)
    check("equity report tables do not enable striping by default",
          not default_stripes,
          f"offenders: {', '.join(default_stripes)}")


def test_documented_snippets_answer_to_template_rules() -> None:
    """A doc snippet is copied more readily than a template is read.

    CHEATSHEET.md shipped a `.card` recipe pairing a 0.5pt border with an 8pt
    radius (the double-ring pitfall templates are failed for) against
    `--border-cream`, a token that no longer exists anywhere. Both survived
    because nothing scanned the docs.
    """
    bad = """```css
.card {
  background: var(--ivory);
  border: 0.5pt solid var(--border-cream);
  border-radius: 8pt;
}
```
"""
    p = write_temp_html(bad, suffix=".md")
    try:
        rules = set()
        for line_offset, snippet in _documented_snippets(p.read_text(encoding="utf-8")):
            rules |= {f.rule for f in scan_text(snippet, p, line_offset)}
            rules |= {f.rule for f in _undefined_token_findings(p, snippet, line_offset, {"--ivory"})}
        check("doc snippet scan catches the thin-border-radius recipe",
              "thin-border-radius" in rules, f"rules: {rules or '(none)'}")
        check("doc snippet scan catches a var() with no definition",
              "undefined-token" in rules, f"rules: {rules or '(none)'}")
    finally:
        p.unlink(missing_ok=True)


def test_documented_snippets_skip_tagged_counter_examples() -> None:
    """Docs teach by contrast; the line tagged `/* avoid */` is the lesson."""
    contrast = """```css
/* avoid */ .tag { background: rgba(27, 54, 93, 0.18); }
/* use   */ .tag { background: var(--tag-bg); }
```
"""
    p = write_temp_html(contrast, suffix=".md")
    try:
        rules = set()
        for line_offset, raw in _documented_snippets(p.read_text(encoding="utf-8")):
            rules |= {f.rule for f in scan_text(_blank_block(raw, NEGATIVE_EXAMPLE_LINE), p, line_offset)}
        check("a line tagged as the wrong way is not reported as a violation",
              "rgba-background" not in rules, f"rules: {rules or '(none)'}")
    finally:
        p.unlink(missing_ok=True)


def test_font_family_key_collapses_weight_variants() -> None:
    """One family at two weights must not read as two typefaces.

    Bold CJK body text is a separate BaseFont entry (TsangerJinKai02 plus
    TsangerJinKai02-Medium, or the W04/W05 pair). Without collapsing, the
    mixed-family rule would fail every correctly rendered bilingual document.
    """
    pairs = [
        ("TsangerJinKai02", "TsangerJinKai02-Medium"),
        ("TsangerJinKai02-W04", "TsangerJinKai02-W05"),
        ("Source-Han-Serif-K", "Source-Han-Serif-K-Mediu"),
        ("NotoSerifCJKsc-Regular", "NotoSerifCJKsc-Bold"),
    ]
    offenders = [f"{a} != {b}" for a, b in pairs if _font_family_key(a) != _font_family_key(b)]
    check("font family key collapses weight variants",
          not offenders,
          f"offenders: {', '.join(offenders)}")
    check("font family key still separates real families",
          _font_family_key("Songti-SC") != _font_family_key("Hiragino-Mincho-ProN-Lig"))


def test_inline_svg_text_uses_explicit_font_stacks() -> None:
    """WeasyPrint must not hand inline SVG labels to an arbitrary system font."""
    offenders = []
    for folder in (REPO_ROOT / "assets" / "diagrams", REPO_ROOT / "assets" / "demos"):
        for path in sorted(folder.glob("*.html")):
            if re.search(r'<text\b[^>]*\bfont-family=["\']inherit["\']',
                         path.read_text(encoding="utf-8"), re.IGNORECASE):
                offenders.append(path.relative_to(REPO_ROOT).as_posix())
    check("inline SVG text uses an explicit font stack",
          offenders == [], str(offenders))


def test_classify_cjk_font_separates_serif_from_the_rest() -> None:
    """The gate exists because a sans substitution shows no fallback boxes.

    A missing CJK serif is invisible to an eyeball pass: the page still reads,
    just with the wrong stroke density against metrics tuned for serif. The
    classifier is what turns that into a failure.
    """
    cases = {
        "ABCDEF+TsangerJinKai02-W04": "primary",
        "Songti-SC": "serif",
        "NotoSerifCJKsc-Regular": "serif",
        "Noto Serif CJK SC": "serif",
        "PingFang-SC": "other",
        "NotoSansCJKsc-Regular": "other",
        "SourceHanSansSC-Regular": "other",
    }
    offenders = [
        f"{name} -> {_classify_cjk_font(name)} (want {want})"
        for name, want in cases.items()
        if _classify_cjk_font(name) != want
    ]
    check("CJK font classifier separates primary and serif from everything else",
          not offenders,
          f"offenders: {', '.join(offenders)}")


def test_emphasis_container_mix_counts_distinct_fills() -> None:
    """Drift is several emphasis languages on a page, not one used repeatedly.

    Templates reuse a single fill across several raised components, which must
    stay clean. A generated document that invents a white rounded card for one
    passage and a tinted rounded block for the next must fail.
    """
    one_fill = """<!doctype html>
<html><head><style>
:root { --ivory: #faf9f5; --brand: #1B365D; }
.callout { background: var(--ivory); border-radius: 3pt; padding: 10pt; }
.takeaway { background: #faf9f5; border-radius: 4pt; padding: 10pt; }
.role { background: #E4ECF5; border-radius: 2pt; padding: 1pt 5pt; float: right; }
</style></head><body></body></html>
"""
    two_fills = """<!doctype html>
<html><head><style>
:root { --ivory: #faf9f5; --tag-bg: #E4ECF5; }
.qa-card { background: var(--ivory); border-radius: 8pt; padding: 10pt 14pt; }
.boundary { background: var(--tag-bg); border-radius: 6pt; padding: 8pt 12pt; }
</style></head><body></body></html>
"""
    clean = write_temp_html(one_fill)
    drifted = write_temp_html(two_fills)
    try:
        check("one emphasis fill (plus an inline chip) is not drift",
              not _emphasis_container_findings(clean),
              f"findings: {[f.excerpt for f in _emphasis_container_findings(clean)]}")
        found = _emphasis_container_findings(drifted)
        check("two different emphasis fills are flagged",
              len(found) == 1 and found[0].rule == "emphasis-container-mix",
              f"findings: {[f.rule for f in found] or '(none)'}")
    finally:
        clean.unlink(missing_ok=True)
        drifted.unlink(missing_ok=True)


def test_density_scans_the_only_page_of_a_single_page_pdf() -> None:
    """Page 1 is cover-exempt, which left one-page documents wholly unscanned.

    one-pager and letter render to a single page, so the cover exemption meant
    the only layout gate that reads a rendered page never looked at them.

    The fixture is built here rather than read from assets/examples, which is
    gitignored build output: pointing a test at it passes locally and fails on
    a fresh checkout. Synthesising the page also pins the expected verdict,
    since the emptiness ratio is chosen rather than inherited from whatever the
    template currently renders.
    """
    try:
        fitz = require_pymupdf()
    except MissingDepError as exc:
        skip("single-page density regression", str(exc), ci_required=True)
        return

    with tempfile.TemporaryDirectory() as tmp:
        single = Path(tmp) / "one-page.pdf"
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)  # A4 in points
        parchment = tuple(channel / 255 for channel in PARCHMENT_RGB)
        page.draw_rect(fitz.Rect(0, 0, 595, 842), color=parchment, fill=parchment)
        # Ink across the top third only, leaving ~64% trailing whitespace: past
        # the sparse threshold, so a scanned page must be reported.
        page.draw_rect(fitz.Rect(50, 50, 545, 300), color=(0.1, 0.1, 0.1), fill=(0.1, 0.1, 0.1))
        doc.save(str(single))
        doc.close()

        default_scan = silently(scan_density, [str(single)])
        explicit_scan = silently(scan_density, [str(single)], scan_single_page=True)

    if default_scan is None or explicit_scan is None:
        return
    check("single-page PDF is exempt in the repo-wide sweep",
          sum(default_scan[:2]) == 0,
          f"scan: {default_scan}")
    check("single-page PDF is scanned when passed explicitly",
          sum(explicit_scan[:2]) > 0,
          f"scan: {explicit_scan} (fixture leaves ~64% of the page empty)")


def test_ci_required_skip_is_a_failure_not_a_pass() -> None:
    """A missing heavy dependency in CI must turn the suite red."""
    global _FAIL, _SKIP
    original_fail, original_skip = _FAIL, _SKIP
    original_ci = os.environ.get("CI")
    try:
        os.environ["CI"] = "1"
        silently(skip, "negative-control fixture", ci_required=True)
        rejected = _FAIL == original_fail + 1 and _SKIP == original_skip + 1
    finally:
        _FAIL, _SKIP = original_fail, original_skip
        if original_ci is None:
            os.environ.pop("CI", None)
        else:
            os.environ["CI"] = original_ci
    check("CI-required skip increments failure and skip counters", rejected)


def test_chinese_slides_mono_has_cjk_fallback() -> None:
    """Slide labels may mix mono Latin and CJK; the mono stack needs CJK fallback."""
    text = (TEMPLATES / "slides-weasy.html").read_text(encoding="utf-8")
    check("slides-weasy mono stack includes TsangerJinKai02 fallback",
          '"TsangerJinKai02"' in text and '"Source Han Serif SC"' in text)


# --------------------------- scan_file ---------------------------

def test_scan_file_skip_bug() -> None:
    """Lines starting with '#' (CSS id selectors) must NOT be skipped."""
    fixture = """<!doctype html>
<html><head><style>
#card { background: rgba(0,0,0,0.5); }
</style></head><body></body></html>
"""
    p = write_temp_html(fixture)
    try:
        findings = scan_file(p)
        rules = {f.rule for f in findings}
        check("scan_file flags rgba on #id-prefixed CSS line",
              "rgba-background" in rules,
              f"rules found: {rules or '(none)'}")
    finally:
        p.unlink(missing_ok=True)


def test_scan_file_arrow_in_en() -> None:
    """`→` in -en.html body should trigger arrow-unicode-in-en."""
    fixture = """<!doctype html>
<html lang="en"><head><style>
.tag { color: #1B365D; }
</style></head><body>
<p>Step 1 → Step 2</p>
</body></html>
"""
    p = write_temp_html(fixture, suffix="-en.html")
    try:
        findings = scan_file(p)
        rules = {f.rule for f in findings}
        check("scan_file flags U+2192 arrow in -en.html",
              "arrow-unicode-in-en" in rules,
              f"rules found: {rules or '(none)'}")
    finally:
        p.unlink(missing_ok=True)


def test_scan_file_clean_template() -> None:
    """A clean template should produce zero findings."""
    fixture = """<!doctype html>
<html><head><style>
:root { --brand: #1B365D; }
.card { background: var(--ivory); }
.tag { background: #EEF2F7; color: var(--brand); }
</style></head><body></body></html>
"""
    p = write_temp_html(fixture)
    try:
        findings = scan_file(p)
        check("scan_file produces no findings on clean template",
              len(findings) == 0,
              f"got {len(findings)} finding(s): {[f.rule for f in findings]}")
    finally:
        p.unlink(missing_ok=True)


# --------------------------- slide sequence ---------------------------

def test_parse_slide_sequence_empty() -> None:
    fixture = """def main():
    pass
"""
    p = write_temp_html(fixture, suffix=".py")
    try:
        seq = _parse_slide_sequence(p)
        check("_parse_slide_sequence returns [] for empty main()",
              seq == [], f"got {seq}")
    finally:
        p.unlink(missing_ok=True)


def test_parse_slide_sequence_basic() -> None:
    fixture = """def main():
    cover_slide()
    content_slide()
    content_slide()
    chapter_slide()
    metrics_slide()

def helper():
    other_call()
"""
    p = write_temp_html(fixture, suffix=".py")
    try:
        seq = _parse_slide_sequence(p)
        expected = ["cover_slide", "content_slide", "content_slide", "chapter_slide", "metrics_slide"]
        check("_parse_slide_sequence parses ordered slide calls",
              seq == expected, f"got {seq}")
    finally:
        p.unlink(missing_ok=True)


# --------------------------- scan_file extra rules ---------------------------

def test_scan_file_line_height_too_loose() -> None:
    """line-height >= 1.6 should trigger line-height-too-loose."""
    fixture = """<!doctype html>
<html><head><style>
p { line-height: 1.8; }
</style></head><body></body></html>
"""
    p = write_temp_html(fixture)
    try:
        findings = scan_file(p)
        rules = {f.rule for f in findings}
        check("scan_file flags line-height 1.8 (too loose)",
              "line-height-too-loose" in rules,
              f"rules found: {rules or '(none)'}")
    finally:
        p.unlink(missing_ok=True)


def test_scan_text_closes_multiline_css_false_greens() -> None:
    direct = ".tag {\n  background:\n    rgba(255, 0, 0, 0.5);\n}"
    direct_findings = scan_text(direct, Path("multiline.html"))
    check("scan_text flags a multiline rgba background",
          [(f.rule, f.line) for f in direct_findings] == [("rgba-background", 2)],
          str([(f.rule, f.line) for f in direct_findings]))

    variables = (
        ":root { --safe: rgba(0, 0, 0, 0.1); "
        "--unsafe: rgba(255, 0, 0, 0.5); }\n"
        ".tag { background: var(--unsafe); }"
    )
    variable_findings = scan_text(variables, Path("variables.html"))
    check("scan_text finds every rgba variable declared on one line",
          [(f.rule, f.line) for f in variable_findings] == [("rgba-background", 2)],
          str([(f.rule, f.line) for f in variable_findings]))


def test_scan_file_flags_integer_line_height() -> None:
    findings = scan_text("p { line-height: 2; }", Path("integer-line-height.html"))
    check("scan_file flags integer line-height above the ceiling",
          [f.rule for f in findings] == ["line-height-too-loose"],
          str([(f.rule, f.excerpt) for f in findings]))


def test_scan_file_cool_gray() -> None:
    """Cool-gray hex literals should be flagged."""
    fixture = """<!doctype html>
<html><head><style>
.muted { color: #888; }
</style></head><body></body></html>
"""
    p = write_temp_html(fixture)
    try:
        findings = scan_file(p)
        rules = {f.rule for f in findings}
        check("scan_file flags cool gray #888",
              "cool-gray" in rules,
              f"rules found: {rules or '(none)'}")
    finally:
        p.unlink(missing_ok=True)


def test_off_palette_flags_non_token_hex() -> None:
    """A non-token, non-cool-gray hex in a component rule is off-palette."""
    fixture = """<!doctype html>
<html><head><style>
.x { color: #ff00aa; }
</style></head><body></body></html>
"""
    p = write_temp_html(fixture)
    try:
        findings = _off_palette_findings(p, {"#1b365d"})
        rules = {f.rule for f in findings}
        check("_off_palette_findings flags non-token hex #ff00aa",
              "off-palette" in rules,
              f"rules found: {rules or '(none)'}")
    finally:
        p.unlink(missing_ok=True)


def test_off_palette_flags_eight_digit_hex() -> None:
    findings = _off_palette_findings(
        Path("alpha-color.html"),
        {"#1b365d"},
        raw=".alert { color: #ff000080; }",
    )
    check("_off_palette_findings flags eight-digit hex colors",
          len(findings) == 1
          and findings[0].rule == "off-palette"
          and "#ff000080" in findings[0].excerpt,
          str([(f.rule, f.excerpt) for f in findings]))
    p = write_temp_html(":root { --alert: #ff000080; }")
    try:
        root_findings = _root_token_findings(p, {"#1b365d"})
        check("_root_token_findings flags eight-digit hex tokens",
              len(root_findings) == 1
              and "#ff000080" in root_findings[0].excerpt,
              str([(f.rule, f.excerpt) for f in root_findings]))
    finally:
        p.unlink(missing_ok=True)


def test_off_palette_ignores_root_and_svg() -> None:
    """Hex inside :root token defs and inside <svg> blocks must be skipped."""
    fixture = """<!doctype html>
<html><head><style>
:root { --brand: #1B365D; --accent: #ff00aa; }
</style></head><body>
<svg viewBox="0 0 10 10"><rect fill="#ff0000" /></svg>
</body></html>
"""
    p = write_temp_html(fixture)
    try:
        findings = _off_palette_findings(p, {"#1b365d"})
        check("_off_palette_findings skips :root defs and <svg> fills",
              findings == [],
              f"unexpected findings: {[(f.line, f.excerpt) for f in findings]}")
    finally:
        p.unlink(missing_ok=True)


def test_root_token_findings_flags_off_palette_definition() -> None:
    """An off-palette hex *defined* in :root (never used as a literal property
    hex) escapes _off_palette_findings, which blanks :root. _root_token_findings
    closes that gap: a stray `--brand-deep: #a64f33` second accent is flagged,
    while a registered token and cool-gray (reported elsewhere) are not."""
    fixture = """<!doctype html>
<html><head><style>
:root {
  --brand: #1B365D;
  --brand-deep: #a64f33;
}
</style></head><body></body></html>
"""
    p = write_temp_html(fixture)
    try:
        findings = _root_token_findings(p, {"#1b365d"})
        rules = {f.rule for f in findings}
        excerpts = " ".join(f.excerpt for f in findings)
        check("_root_token_findings flags off-palette :root token #a64f33",
              "off-palette-token" in rules and "#a64f33" in excerpts,
              f"rules={rules or '(none)'} excerpts={excerpts or '(none)'}")
        check("_root_token_findings does not flag the registered --brand token",
              "#1b365d" not in excerpts,
              f"unexpectedly flagged brand token: {excerpts}")
    finally:
        p.unlink(missing_ok=True)


def test_off_palette_repo_clean() -> None:
    """The real editorial templates must carry no off-palette colors."""
    rc = silently(check_off_palette)
    check("check_off_palette passes on the real templates",
          rc == 0,
          f"check_off_palette returned {rc}")


def test_check_update_script() -> None:
    """check-update.sh notifies on a newer remote, stays silent when current,
    throttles through a local cache marker, and fails silently offline. It GETs
    only a version file and uploads no document/task content; KAMI_UPDATE_URL
    points it at a fixture."""
    script = REPO_ROOT / "scripts" / "check-update.sh"
    check("check-update.sh exists", script.exists())
    if not script.exists():
        return
    if shutil.which("bash") is None or shutil.which("curl") is None:
        check("check-update.sh behavior (skipped: bash/curl unavailable)", True)
        return
    local_ver = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()

    def run(cache: str, url: str) -> tuple[int, str]:
        env = dict(os.environ, XDG_CACHE_HOME=cache, KAMI_UPDATE_URL=url)
        r = subprocess.run(["bash", str(script)], capture_output=True, text=True, env=env)
        return r.returncode, r.stdout.strip()

    with tempfile.TemporaryDirectory() as d:
        dp = Path(d)
        newer = dp / "newer"; newer.write_text("9.9.9\n")
        same = dp / "same"; same.write_text(local_ver + "\n")

        rc, out = run(str(dp / "c1"), newer.as_uri())
        check("check-update notifies on a newer remote", rc == 0 and "9.9.9" in out, out)
        check("check-update default command uses plugin bundle path",
              "npx skills add tw93/kami/plugins/kami -a universal -g -y" in out and "skills update" not in out,
              out)

        rc, out = run(str(dp / "c2"), same.as_uri())
        check("check-update is silent when current", rc == 0 and out == "", out)

        c3 = str(dp / "c3")
        run(c3, newer.as_uri())
        _, out2 = run(c3, newer.as_uri())
        check("check-update throttles to once per day", out2 == "", out2)

        rc, out = run(str(dp / "c4"), (dp / "nope").as_uri())
        check("check-update fails silently when offline", rc == 0 and out == "", out)

        no_home_env = dict(os.environ, KAMI_UPDATE_URL=newer.as_uri())
        no_home_env.pop("HOME", None)
        no_home_env.pop("XDG_CACHE_HOME", None)
        result = subprocess.run(
            ["bash", str(script)], capture_output=True, text=True, env=no_home_env)
        check("check-update is silent without a cache home",
              result.returncode == 0 and result.stdout == "" and result.stderr == "",
              result.stdout + result.stderr)

        unwritable_cache_env = dict(
            os.environ,
            XDG_CACHE_HOME="/dev/null",
            KAMI_UPDATE_URL=newer.as_uri(),
        )
        result = subprocess.run(
            ["bash", str(script)], capture_output=True, text=True, env=unwritable_cache_env)
        check("check-update is silent when the cache root is unusable",
              result.returncode == 0 and result.stdout == "" and result.stderr == "",
              result.stdout + result.stderr)


def test_check_update_defaults_to_latest_published_release() -> None:
    script = REPO_ROOT / "scripts" / "check-update.sh"
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        fake_curl = bin_dir / "curl"
        fake_curl.write_text(
            "#!/usr/bin/env bash\n"
            "case \" $* \" in\n"
            "  *\" https://github.com/tw93/Kami/releases/latest \"*)\n"
            "    printf '%s' 'https://github.com/tw93/Kami/releases/tag/V9.9.9'\n"
            "    ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        fake_curl.chmod(0o755)
        env = dict(
            os.environ,
            XDG_CACHE_HOME=str(root / "cache"),
            PATH=f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        )
        env.pop("KAMI_UPDATE_URL", None)
        result = subprocess.run(
            ["bash", str(script)], capture_output=True, text=True, env=env)
        check("check-update defaults to GitHub's latest published release tag",
              result.returncode == 0 and "Kami 9.9.9 is available" in result.stdout,
              result.stdout + result.stderr)


def test_check_update_uses_codex_plugin_update_command() -> None:
    """When installed through Codex plugin cache, the update hint should use
    plugin marketplace refresh commands instead of the legacy npx skill update.
    """
    script = REPO_ROOT / "scripts" / "check-update.sh"
    check("check-update.sh exists for Codex command test", script.exists())
    if not script.exists():
        return
    if shutil.which("bash") is None or shutil.which("curl") is None:
        check("check-update Codex command (skipped: bash/curl unavailable)", True)
        return

    with tempfile.TemporaryDirectory() as d:
        dp = Path(d)
        newer = dp / "newer"
        newer.write_text("9.9.9\n")

        roots = [
            dp / ".codex" / "plugins" / "cache" / "kami" / "kami" / "1.7.4" / "skills" / "kami",
            dp / "custom-codex-home" / "plugins" / "cache" / "kami" / "kami" / "1.7.4" / "skills" / "kami",
        ]
        for index, install_root in enumerate(roots, start=1):
            (install_root / "scripts").mkdir(parents=True)
            shutil.copy2(script, install_root / "scripts" / "check-update.sh")
            (install_root / "VERSION").write_text("1.7.4\n")

            env = dict(os.environ, XDG_CACHE_HOME=str(dp / f"cache-{index}"), KAMI_UPDATE_URL=newer.as_uri())
            result = subprocess.run(
                ["bash", str(install_root / "scripts" / "check-update.sh")],
                capture_output=True,
                text=True,
                env=env,
            )
            out = result.stdout.strip()
            check(f"check-update uses Codex plugin update command ({install_root.parent.parent.parent.name})",
                  result.returncode == 0 and "codex plugin marketplace upgrade kami" in out,
                  out)


def test_check_update_uses_claude_plugin_update_command() -> None:
    """When installed through Claude Code's plugin cache, the update hint should
    use Claude's plugin updater instead of generic npx skill install.
    """
    script = REPO_ROOT / "scripts" / "check-update.sh"
    check("check-update.sh exists for Claude command test", script.exists())
    if not script.exists():
        return
    if shutil.which("bash") is None or shutil.which("curl") is None:
        check("check-update Claude command (skipped: bash/curl unavailable)", True)
        return

    with tempfile.TemporaryDirectory() as d:
        dp = Path(d)
        newer = dp / "newer"
        newer.write_text("9.9.9\n")
        install_root = dp / ".claude" / "plugins" / "cache" / "kami" / "kami" / "1.9.1" / "skills" / "kami"
        (install_root / "scripts").mkdir(parents=True)
        shutil.copy2(script, install_root / "scripts" / "check-update.sh")
        (install_root / "VERSION").write_text("1.9.1\n")

        env = dict(os.environ, XDG_CACHE_HOME=str(dp / "cache"), KAMI_UPDATE_URL=newer.as_uri())
        result = subprocess.run(
            ["bash", str(install_root / "scripts" / "check-update.sh")],
            capture_output=True,
            text=True,
            env=env,
        )
        out = result.stdout.strip()
        check("check-update uses Claude plugin update command",
              result.returncode == 0 and "claude plugin update kami" in out and "npx skills" not in out,
              out)


def test_lint_repo_clean() -> None:
    """The full CSS lint (scan_file across every template) must pass. This is
    what `build.py --check` runs; covering it here means a rule violation such
    as thin-border-radius cannot reach main behind an otherwise green suite."""
    rc = silently(check_all, False)
    check("check_all (full CSS lint) passes on the real templates",
          rc == 0,
          f"check_all returned {rc}")


def test_scan_file_ignores_block_comment_rgba() -> None:
    """rgba() inside a /* ... */ CSS block comment must not trigger findings."""
    fixture = """<!doctype html>
<html><head><style>
/* historical note: we used to write
   background: rgba(0,0,0,0.5);
   here, but switched to solid hex. */
.card { background: #EEF2F7; }
</style></head><body></body></html>
"""
    p = write_temp_html(fixture)
    try:
        findings = scan_file(p)
        rules = {f.rule for f in findings}
        check("scan_file ignores rgba inside /* */ comment",
              "rgba-background" not in rules,
              f"rules found: {rules or '(none)'}")
    finally:
        p.unlink(missing_ok=True)


def test_scan_file_thin_border_with_radius() -> None:
    """Sub-1pt closed border in a block with border-radius should fire pitfall #2."""
    fixture = """<!doctype html>
<html><head><style>
.tag {
  border: 0.5pt solid #1B365D;
  border-radius: 3pt;
  background: #EEF2F7;
}
</style></head><body></body></html>
"""
    p = write_temp_html(fixture)
    try:
        findings = scan_file(p)
        rules = {f.rule for f in findings}
        check("scan_file flags thin border with border-radius",
              "thin-border-radius" in rules,
              f"rules found: {rules or '(none)'}")
    finally:
        p.unlink(missing_ok=True)


# --------------------------- check_placeholders ---------------------------

def test_check_placeholders_flags_unfilled() -> None:
    """A doc with `{{ name }}` left over should fail the check."""
    p = write_temp_html("<html><body><h1>{{ name }}</h1><p>{{ role }}</p></body></html>")
    try:
        rc = silently(check_placeholders, [str(p)])
        check("check_placeholders fails on {{ name }}", rc == 1, f"rc={rc}")
    finally:
        p.unlink(missing_ok=True)


def test_check_placeholders_passes_clean() -> None:
    """A doc with no placeholder syntax should pass."""
    p = write_temp_html("<html><body><h1>Real Name</h1><p>Real role</p></body></html>")
    try:
        rc = silently(check_placeholders, [str(p)])
        check("check_placeholders passes clean file", rc == 0, f"rc={rc}")
    finally:
        p.unlink(missing_ok=True)


def test_markdown_residue_flags_raw_markers() -> None:
    issues = _markdown_residue_issues("Intro\n---\nThis has **raw bold** and `raw code`.")
    check("markdown residue flags thematic breaks",
          any("thematic break" in issue for issue in issues),
          f"issues={issues}")
    check("markdown residue flags raw bold markers",
          any("bold marker" in issue for issue in issues),
          f"issues={issues}")
    check("markdown residue flags raw inline-code markers",
          any("inline-code marker" in issue for issue in issues),
          f"issues={issues}")

    check("markdown residue ignores clean text",
          _markdown_residue_issues("Clean paragraph with converted emphasis.") == [])

    issues = _markdown_residue_issues("A claim\u2014with an em dash.\n中文\u2014\u2014双破折号。")
    check("markdown residue flags em dashes",
          sum("em dash" in issue for issue in issues) == 2,
          f"issues={issues}")
    check("markdown residue allows en dash and hyphen",
          _markdown_residue_issues("Ranges use 2019-2024 and 3–5 items.") == [])


def test_check_markdown_residue_skips_html_code_blocks() -> None:
    dirty = write_temp_html("<html><body><p>Visible **raw bold**</p></body></html>", suffix=".html")
    clean_code = write_temp_html(
        "<html><body><p>Visible text</p><pre><code>**example** `cmd`</code></pre></body></html>",
        suffix=".html",
    )
    ambiguous_css = write_temp_html(
        '<html><head><link rel="stylesheet" href="theme.css"></head>'
        '<body><p>Visible **raw despite CSS uncertainty**</p></body></html>',
        suffix=".html",
    )
    descendant_css = write_temp_html(
        '<style>.wrap img { display: none }</style>'
        '<div class="wrap"><p>**VISIBLE-DESCENDANT**</p></div>',
        suffix=".html",
    )
    overridden_css = write_temp_html(
        '<style>.x { display: none } .x { display: block }</style>'
        '<p class="x">**VISIBLE-OVERRIDE**</p>',
        suffix=".html",
    )
    aria_hidden = write_temp_html(
        '<p aria-hidden="true">**VISUALLY-PRESENT**</p>',
        suffix=".html",
    )
    try:
        rc = silently(check_markdown_residue, [str(dirty)])
        check("check_markdown_residue fails visible raw markdown", rc == 1, f"rc={rc}")
        rc = silently(check_markdown_residue, [str(clean_code)])
        check("check_markdown_residue skips code/pre blocks", rc == 0, f"rc={rc}")
        rc = silently(check_markdown_residue, [str(ambiguous_css)])
        check("markdown residue includes text under ambiguous CSS",
              rc == 1, f"rc={rc}")
        residue_results = [
            silently(check_markdown_residue, [str(path)])
            for path in (descendant_css, overridden_css, aria_hidden)
        ]
        check("markdown residue never hides visually possible stylesheet or aria text",
              residue_results == [1, 1, 1], str(residue_results))
    finally:
        for path in (
            dirty, clean_code, ambiguous_css, descendant_css,
            overridden_css, aria_hidden,
        ):
            path.unlink(missing_ok=True)


def test_pdf_markdown_residue_skips_monospace_code() -> None:
    """Semantic code blocks remain exempt after HTML is flattened into PDF text."""
    try:
        from render import render_pdf
        import weasyprint  # noqa: F401
        import pypdf  # noqa: F401
    except ImportError:
        skip("PDF code residue exemption", "render dependencies unavailable", ci_required=True)
        return

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        html = root / "code.html"
        pdf = root / "code.pdf"
        html.write_text(
            '<style>code { font-family: monospace }</style>'
            '<p>Visible prose is clean.</p><pre><code>const msg = `hello`;</code></pre>',
            encoding="utf-8",
        )
        render_pdf(html, pdf)
        rc = silently(check_markdown_residue, [str(pdf)])
        check("PDF markdown residue skips monospace code", rc == 0, f"rc={rc}")


# --------------------------- cross-template consistency ---------------------------

def test_pair_names_includes_known_pairs() -> None:
    captured = list(_pair_names())
    check("pair_names includes one-pager",
          ("one-pager", "one-pager-en") in captured,
          f"got {[v for b, v in captured if b == 'one-pager']!r}")
    check("pair_names includes landing-page (CN/EN)",
          ("landing-page", "landing-page-en") in captured,
          f"got {[v for b, v in captured if b == 'landing-page']!r}")
    check("pair_names omits lone -en entries",
          not any(name.endswith("-en") for name, _ in _pair_names()))


def test_pair_names_includes_ko_variants_when_present() -> None:
    """`_pair_names` must yield (base, base-ko) pairs in addition to (base, base-en)."""
    captured = list(_pair_names())
    # Sanity: existing CN/EN and CN/KO pairs still detected, so the sweep
    # below cannot pass vacuously on an empty or EN-only pair list.
    check("CN/EN pair still detected", ("one-pager", "one-pager-en") in captured)
    check("CN/KO pair still detected", ("one-pager", "one-pager-ko") in captured)
    # Any base whose `-ko` sibling is registered must appear as a (base, base-ko) pair.
    bases = {base for base, _ in captured}
    seen = set(HTML_TEMPLATES) | set(SCREEN_TEMPLATES)
    missing = [
        base for base in bases
        if f"{base}-ko" in seen and (base, f"{base}-ko") not in captured
    ]
    check("pair_names includes ko variants when present", not missing,
          f"unpaired KO bases: {missing}")


def test_cross_template_consistency_clean() -> None:
    """The current repo should pass cross-template consistency."""
    rc = silently(check_cross_template_consistency, False)
    check("cross-template returns 0 on current repo", rc == 0, f"rc={rc}")


def test_extract_root_vars_picks_up_definitions() -> None:
    fixture = """<!doctype html>
<html><head><style>
:root {
  --brand: #1B365D;
  --parchment: #F5F4ED;
  --serif: Charter, Georgia, serif;
}
</style></head><body></body></html>
"""
    p = write_temp_html(fixture)
    try:
        vars_ = _extract_root_vars(p)
        check("extract_root_vars finds --brand", vars_.get("--brand") == "#1B365D",
              f"got {vars_.get('--brand')!r}")
        check("extract_root_vars finds --parchment", vars_.get("--parchment") == "#F5F4ED",
              f"got {vars_.get('--parchment')!r}")
    finally:
        p.unlink(missing_ok=True)


# --------------------------- _last_content_y ---------------------------

def _make_samples(rows_with_content: int, w: int, h: int, n: int = 3) -> bytes:
    """Build a flat RGB buffer: parchment everywhere, ink in the top N rows.

    Returns bytes matching the layout PyMuPDF's Pixmap uses, so we can drive
    _last_content_y without depending on a real PDF or numpy.
    """
    parchment_row = bytes((_BG_R, _BG_G, _BG_B)) * w
    ink_row = bytes((27, 54, 93)) * w
    out = bytearray()
    for y in range(h):
        out.extend(ink_row if y < rows_with_content else parchment_row)
    return bytes(out)


def test_last_content_y_dense_page() -> None:
    """Page with content all the way to the bottom: returns h-1."""
    w, h, n = 80, 100, 3
    samples = _make_samples(rows_with_content=h, w=w, h=h, n=n)
    y = _last_content_y(samples, w, h, w * n, n)
    check("_last_content_y dense page returns last row", y == h - 1, f"got {y}")


def test_last_content_y_sparse_page() -> None:
    """Page with content only in top 10 rows: returns 9."""
    w, h, n = 80, 100, 3
    samples = _make_samples(rows_with_content=10, w=w, h=h, n=n)
    y = _last_content_y(samples, w, h, w * n, n)
    check("_last_content_y sparse page returns last content row",
          y == 9, f"got {y}")


def test_last_content_y_blank_page() -> None:
    """Page with no content at all: returns 0."""
    w, h, n = 80, 100, 3
    samples = _make_samples(rows_with_content=0, w=w, h=h, n=n)
    y = _last_content_y(samples, w, h, w * n, n)
    check("_last_content_y blank page returns 0", y == 0, f"got {y}")


def test_density_threshold_buckets() -> None:
    """Drive the real `_density_bucket` seam so the SPARSE (>50%) / WARN (>25%)
    / OK categorization is asserted against production logic, not a reimplemented
    copy. A `>`->`>=` slip or a warn/sparse swap in checks.py fails here."""
    density_cfg = load_checks_thresholds()["density"]
    warn_pct = float(density_cfg["warn_pct"])
    sparse_pct = float(density_cfg["sparse_pct"])
    cases = [
        (0.0,        "OK"),      # full page
        (warn_pct,   "OK"),      # exactly at warn threshold -> not yet WARN (strict >)
        (0.30,       "WARN"),    # 30% trailing
        (sparse_pct, "WARN"),    # exactly at sparse threshold -> still WARN (strict >)
        (0.51,       "SPARSE"),  # 51% trailing
        (1.0,        "SPARSE"),  # blank page
    ]
    for empty, expected_bucket in cases:
        bucket = _density_bucket(empty, warn_pct, sparse_pct)
        check(
            f"_density_bucket empty={empty:.2f} -> {expected_bucket}",
            bucket == expected_bucket,
            f"got {bucket}",
        )


def test_rhythm_issues_rules() -> None:
    """Drive the three monotony rules in `_rhythm_issues` directly, without
    rendering a deck. Covers content-run limit, missing divider, and missing
    density-variation slide, plus the clean case."""
    max_run, min_deck = 4, 8

    healthy = [
        "title_slide", "content_slide", "content_slide", "quote_slide",
        "chapter_slide", "content_slide", "metrics_slide", "closing_slide",
    ]
    check("rhythm: balanced deck has no issues",
          _rhythm_issues(healthy, max_run, min_deck) == [],
          f"got {_rhythm_issues(healthy, max_run, min_deck)}")

    long_run = ["quote_slide"] + ["content_slide"] * (max_run + 1)
    issues = _rhythm_issues(long_run, max_run, min_deck)
    check("rhythm: over-long content run flagged",
          any("content_slide run" in i for i in issues), f"got {issues}")

    no_divider = ["title_slide"] + ["content_slide", "quote_slide"] * 5
    issues = _rhythm_issues(no_divider, max_run, min_deck)
    check("rhythm: large deck without divider flagged",
          any("no chapter_slide divider" in i for i in issues), f"got {issues}")

    no_variation = ["title_slide", "content_slide", "chapter_slide", "content_slide"]
    issues = _rhythm_issues(no_variation, max_run, min_deck)
    check("rhythm: deck without quote/metrics flagged",
          any("density variation" in i for i in issues), f"got {issues}")


def test_orphan_last_line_predicate() -> None:
    """Drive `_orphan_last_line`: a short trailing line on a multi-line block
    is an orphan; single-line blocks and long trailing lines are not."""
    max_words, max_chars = 3, 30

    orphan = "This is a full sentence that wraps\nword"
    check("orphan: short trailing line detected",
          _orphan_last_line(orphan, max_words, max_chars) == "word",
          f"got {_orphan_last_line(orphan, max_words, max_chars)!r}")

    single = "Only one line here"
    check("orphan: single-line block is not an orphan",
          _orphan_last_line(single, max_words, max_chars) is None,
          "single line flagged")

    long_tail = "First line of the block\n" + "x" * (max_chars + 5)
    check("orphan: long trailing line is not an orphan",
          _orphan_last_line(long_tail, max_words, max_chars) is None,
          "long tail flagged")

    many_words = "First line here\none two three four five"
    check("orphan: wordy trailing line is not an orphan",
          _orphan_last_line(many_words, max_words, max_chars) is None,
          "wordy tail flagged")


def test_resume_balance_issues() -> None:
    min_fill, max_fill, max_gap = 0.83, 0.95, 0.12
    check("resume balance accepts two filled pages",
          _resume_balance_issues([0.88, 0.92], 2, min_fill, max_fill, max_gap) == [])

    issues = _resume_balance_issues([0.92, 0.74], 2, min_fill, max_fill, max_gap)
    check("resume balance flags low second page",
          any("p2 fill" in issue for issue in issues),
          f"issues={issues}")
    check("resume balance flags page gap",
          any("gap" in issue for issue in issues),
          f"issues={issues}")

    issues = _resume_balance_issues([0.90, 0.89, 0.50], 3, min_fill, max_fill, max_gap)
    check("resume balance requires two pages",
          any("expected 2" in issue for issue in issues),
          f"issues={issues}")


def test_verify_target_requires_exactly_two_resume_pages() -> None:
    original_render = verify_mod.render_pdf
    original_fonts = verify_mod._pdf_font_names
    try:
        verify_mod._pdf_font_names = lambda _: {"ABCDEF+TsangerJinKai02-W04"}
        results = {}
        for page_count in (1, 2, 3):
            verify_mod.render_pdf = lambda _src, _out, n=page_count: n
            results[page_count] = verify_mod.verify_target(
                "resume", "resume.html", 2, TEMPLATES
            )
    finally:
        verify_mod.render_pdf = original_render
        verify_mod._pdf_font_names = original_fonts

    check("verify_target accepts a two-page resume",
          results[2] == [], repr(results[2]))
    check("verify_target rejects one- and three-page resumes as exact-count failures",
          all(
              any("expected 2" in issue for issue in results[count])
              for count in (1, 3)
          ),
          repr(results))


# --------------------------- runner ---------------------------

def test_highlight_with_language() -> None:
    html = '<pre><code class="language-python">def foo():\n    pass</code></pre>'
    out = highlight_code_blocks(html)
    if importlib.util.find_spec("pygments") is None:
        check("highlight skips styled output when Pygments is absent",
              out == html,
              f"out differs: {out[:200]}")
        return

    check("highlight adds style spans to language-tagged block",
          "<span" in out and "style=" in out,
          f"out: {out[:200]}")
    check("highlight avoids synthetic bold",
          "font-weight" not in out.lower(),
          f"out: {out[:200]}")
    check("highlight preserves pre/code wrapper",
          "<pre" in out and "</code>" in out)


def test_math_render_finds_standard_delimiters_only_in_text() -> None:
    from math_render import _latex_spans

    source = (
        r'<p data-formula="\(attribute\)">'
        r'Inline \(x^2\), display \[E = mc^2\], '
        r'escaped \\(literal\\).</p>'
        r'<code>\(code\)</code><pre>\[pre\]</pre>'
        r'<script>const formula = "\(script\)";</script>'
    )
    spans, issues = _latex_spans(source)
    check("math parser accepts standard inline and display delimiters",
          [(span.tex, span.display) for span in spans]
          == [("x^2", False), ("E = mc^2", True)],
          f"spans={spans} issues={issues}")
    check("math parser ignores attributes, escaped delimiters, code, pre, and script",
          not issues, str(issues))


def test_math_check_rejects_raw_unmatched_and_legacy_sources() -> None:
    from math_render import check_latex_html

    cases = [
        r"<p>\(x^2\)</p>",
        r"<p>\[x^2</p>",
        r"<p>x^2\)</p>",
        '<span class="latex-inline" data-latex="x^2"></span>',
        '<span class="math latex-display extra" data-latex="x^2"></span>',
    ]
    findings = [check_latex_html(case) for case in cases]
    rendered = (
        '<span class="latex-inline-svg"><mjx-container>'
        '<svg><text>done</text></svg></mjx-container></span>'
    )
    check("math check rejects raw, unmatched, and legacy formula sources",
          all(findings), repr(findings))
    check("math check accepts rendered MathJax SVG",
          check_latex_html(rendered) == [],
          str(check_latex_html(rendered)))


def test_math_render_replaces_delimiters_and_preserves_other_html() -> None:
    import math_render as math_mod

    source = r'<p>Before \(x &lt; y\) after.</p><code>\(code\)</code>'
    original_renderer = math_mod._render_svg
    seen = []
    try:
        def fake_renderer(formulas):
            seen.extend(formulas)
            return [
                '<mjx-container><svg role="img"><path d="M0 0"/></svg></mjx-container>'
                for _ in formulas
            ]
        math_mod._render_svg = fake_renderer
        rendered = math_mod.render_latex_in_html(source)
    finally:
        math_mod._render_svg = original_renderer
    check("math render decodes entities and sends the standard delimiter source",
          seen == [{"tex": "x < y", "display": False}], repr(seen))
    check("math render replaces only the formula text node",
          "latex-inline-svg" in rendered
          and r"\(x &lt; y\)" not in rendered
          and r"<code>\(code\)</code>" in rendered
          and rendered.startswith("<p>Before "),
          rendered[:500])


def test_math_parser_decodes_entity_delimiters_and_ignores_metadata() -> None:
    from math_render import _latex_spans, check_latex_html

    source = (
        r"<title>Analysis \(x^2\)</title>"
        r"<p>&#92;(x^2&#92;)</p>"
    )
    spans, issues = _latex_spans(source)
    check("math parser decodes HTML entities before delimiter scanning",
          [(span.tex, span.display) for span in spans] == [("x^2", False)]
          and source[spans[0].start:spans[0].end] == "&#92;(x^2&#92;)",
          f"spans={spans} issues={issues}")
    check("math parser treats title metadata as literal text",
          not issues and not check_latex_html(r"<title>Analysis \(x^2\)</title>"),
          str(issues))


def test_math_parser_fails_closed_on_malformed_ignored_regions() -> None:
    from math_render import check_latex_html

    malformed = [
        r"<pre>literal </code> \(x^2\)</pre>",
        r'<script/>const formula = "\(x^2\)";',
        r"<pre>literal <p>Formula: \(x^2\)</p>",
    ]
    legacy_example = (
        '<pre><code>class="latex-inline"</code></pre>'
        '<!-- class="latex-display" -->'
    )
    check("math parser rejects ambiguous ignored-tag structure",
          all(check_latex_html(source) for source in malformed),
          repr([check_latex_html(source) for source in malformed]))
    check("legacy placeholder examples inside literal regions stay literal",
          check_latex_html(legacy_example) == [],
          str(check_latex_html(legacy_example)))


def test_math_parser_accepts_optional_option_end_tags() -> None:
    from math_render import _latex_spans

    source = (
        r"<select><option>A<option>B</select>"
        r"<datalist><option>C<option>D</datalist>"
        r"<p>\(x^2\)</p>"
    )
    spans, issues = _latex_spans(source)
    check("math parser follows optional HTML option end-tag rules",
          [(span.tex, span.display) for span in spans] == [("x^2", False)]
          and not issues,
          f"spans={spans} issues={issues}")


def test_math_render_real_runtime_is_strict_and_safe() -> None:
    from math_render import MathRenderError, probe_mathjax, render_latex_in_html

    status = probe_mathjax()
    if status["status"] != "available":
        skip("MathJax strict and safe end-to-end render",
             status.get("detail", "locked runtime unavailable"),
             ci_required=True)
        return

    rendered = render_latex_in_html(
        r"<p>Inline \(x^2 + \frac{1}{2}\).</p><p>\[E = mc^2\]</p>"
    )
    safe_words = render_latex_in_html(
        r"<p>\(\text{src = x, href=1}, x &lt; y\)</p>"
    )
    rejected = 0
    for source in (
        r"<p>\(\frac{1\)</p>",
        r"<p>\(\href{javascript:alert(1)}{x}\)</p>",
        r"<p>\(\class{evil}{x}\)</p>",
        r"<p>\(\color{red}{x}\)</p>",
    ):
        try:
            render_latex_in_html(source)
        except MathRenderError:
            rejected += 1
    check("locked MathJax renders valid inline and display formulas end to end",
          rendered.count("<mjx-container") == 2
          and "latex-inline-svg" in rendered
          and "latex-display-svg" in rendered,
          rendered[:500])
    check("invalid TeX and author-controlled markup or color fail closed",
          rejected == 4, f"rejected={rejected}")
    check("rendered SVG contains no active link, source, script, or event attribute",
          not re.search(
              r"<\s*(?:script|foreignObject)\b|(?:href|src|on[a-z]+)\s*=",
              rendered,
              re.IGNORECASE,
          ),
          rendered[:500])
    check("SVG safety scan parses attributes rather than formula text substrings",
          "<mjx-container" in safe_words,
          safe_words[:500])


def test_math_svg_safety_parser_rejects_malformed_structure() -> None:
    from math_render import _SvgSafetyParser

    parser = _SvgSafetyParser()
    parser.feed("<mjx-container><svg></mjx-container>")
    parser.close()
    check("SVG safety scan rejects mismatched or unclosed renderer markup",
          parser.malformed or bool(parser._stack),
          f"malformed={parser.malformed} stack={parser._stack}")


def test_math_cli_failure_preserves_source_and_success_is_atomic() -> None:
    from math_render import probe_mathjax

    status = probe_mathjax()
    if status["status"] != "available":
        skip("MathJax in-place atomic CLI",
             status.get("detail", "locked runtime unavailable"),
             ci_required=True)
        return
    script = REPO_ROOT / "scripts" / "math_render.py"
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "filled.html"
        invalid = b"<p>\\(\\frac{1\\)</p>"
        path.write_bytes(invalid)
        path.chmod(0o640)
        failed = subprocess.run(
            [sys.executable, str(script), "--in-place", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        unchanged = path.read_bytes() == invalid
        path.write_text(r"<p>Energy: \(E = mc^2\).</p>", encoding="utf-8")
        path.chmod(0o640)
        succeeded = subprocess.run(
            [sys.executable, str(script), "--in-place", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        checked = subprocess.run(
            [sys.executable, str(script), "--check", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = path.read_text(encoding="utf-8")
        mode = stat.S_IMODE(path.stat().st_mode)
    check("failed strict in-place render preserves the original source bytes",
          failed.returncode == 1 and unchanged,
          (failed.stdout + failed.stderr)[:500])
    check("successful in-place render is check-clean and preserves file mode",
          succeeded.returncode == 0
          and checked.returncode == 0
          and "<mjx-container" in output
          and mode == 0o640,
          (succeeded.stdout + checked.stdout + checked.stderr)[:500])


def test_math_render_enforces_formula_count_limit_before_node() -> None:
    from math_render import MathRenderError, _latex_spans, render_latex_in_html

    source = "<p>" + r"\(x\)" * 50_000 + "</p>"
    tracemalloc.start()
    try:
        render_latex_in_html(source)
    except MathRenderError as exc:
        rejected = "formula safety limit" in str(exc)
    else:
        rejected = False
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    check("math renderer bounds formula count before allocating every span",
          rejected and peak < 5 * 1024 * 1024,
          f"rejected={rejected} peak={peak} bytes")

    fragmented = r"<p>x\)</p>" * 10_000
    tracemalloc.start()
    try:
        _latex_spans(fragmented)
    except MathRenderError as exc:
        fragmented_rejected = "TeX delimiters exceed" in str(exc)
    else:
        fragmented_rejected = False
    _current, fragmented_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    check("math renderer shares the delimiter budget across text nodes",
          fragmented_rejected and fragmented_peak < 8 * 1024 * 1024,
          f"rejected={fragmented_rejected} peak={fragmented_peak} bytes")


def test_math_delimiter_scan_is_linear_for_long_backslash_runs() -> None:
    from math_render import _latex_spans

    source = "<p>" + "\\" * 200_000 + "literal</p>"
    started = time.monotonic()
    spans, issues = _latex_spans(source)
    elapsed = time.monotonic() - started
    check("math delimiter scan stays linear on adversarial backslash runs",
          not spans and not issues and elapsed < 1.0,
          f"elapsed={elapsed:.3f}s spans={len(spans)} issues={issues[:2]}")


def test_math_no_formula_text_avoids_boundary_map_allocation() -> None:
    from math_render import _latex_spans

    source = "<p>" + "ordinary text " * 100_000 + "</p>"
    tracemalloc.start()
    spans, issues = _latex_spans(source)
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    check("math parser avoids per-character boundary maps without delimiters",
          not spans and not issues and peak < 8 * 1024 * 1024,
          f"peak={peak} bytes spans={len(spans)} issues={issues[:2]}")

    source = "<p>" + "a" * 1_000_000 + r"\(x^2\)</p>"
    tracemalloc.start()
    spans, issues = _latex_spans(source)
    _current, tail_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    check("math parser maps only formula boundaries in long text nodes",
          [(span.tex, span.display) for span in spans] == [("x^2", False)]
          and not issues
          and tail_peak < 8 * 1024 * 1024,
          f"peak={tail_peak} bytes spans={len(spans)} issues={issues[:2]}")


def test_mathjax_probe_and_install_ignore_polluted_node_options() -> None:
    from math_render import probe_mathjax

    status = probe_mathjax()
    if status["status"] != "available":
        skip("MathJax polluted NODE_OPTIONS handling",
             status.get("detail", "locked runtime unavailable"),
             ci_required=True)
        return
    original = os.environ.get("NODE_OPTIONS")
    try:
        os.environ["NODE_OPTIONS"] = "--definitely-invalid-kami-option"
        polluted_probe = probe_mathjax()
        environment = os.environ.copy()
        installed = subprocess.run(
            ["bash", str(REPO_ROOT / "scripts" / "ensure_mathjax.sh")],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        if original is None:
            os.environ.pop("NODE_OPTIONS", None)
        else:
            os.environ["NODE_OPTIONS"] = original
    check("doctor probe and installer ignore inherited NODE_OPTIONS",
          polluted_probe["status"] == "available" and installed.returncode == 0,
          f"probe={polluted_probe} install={(installed.stdout + installed.stderr)[:300]}")


def test_mathjax_runtime_rejects_unsupported_node_21() -> None:
    import math_render as math_mod

    manifest = json.loads(
        (REPO_ROOT / "scripts" / "mathjax-runtime" / "package.json")
        .read_text(encoding="utf-8")
    )
    with tempfile.TemporaryDirectory() as d:
        fake_bin = Path(d) / "bin"
        fake_bin.mkdir()
        node = fake_bin / "node"
        npm = fake_bin / "npm"
        node.write_text("#!/bin/sh\nprintf '21\\n'\n", encoding="utf-8")
        npm.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        node.chmod(0o755)
        npm.chmod(0o755)
        environment = os.environ.copy()
        environment["PATH"] = f"{fake_bin}:/usr/bin:/bin"
        result = subprocess.run(
            ["bash", str(REPO_ROOT / "scripts" / "ensure_mathjax.sh")],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
        )
        original_path = os.environ.get("PATH")
        try:
            os.environ["PATH"] = environment["PATH"]
            math_mod._validated_node.cache_clear()
            probe = math_mod.probe_mathjax()
        finally:
            if original_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = original_path
            math_mod._validated_node.cache_clear()
    check("MathJax runtime manifest and installer reject unsupported Node 21",
          manifest.get("engines", {}).get("node") == "20 || >=22"
          and result.returncode == 1
          and "Node.js 20 or Node.js 22+" in result.stderr
          and probe.get("status") == "missing"
          and "Node.js 20 or Node.js 22+" in probe.get("detail", ""),
          f"manifest={manifest.get('engines')} result={result.returncode} "
          f"stderr={result.stderr[:300]} probe={probe}")


def test_mathjax_installer_reclaims_dead_owner_lock() -> None:
    with tempfile.TemporaryDirectory() as d:
        temp_root = Path(d)
        fake_bin = temp_root / "bin"
        fake_bin.mkdir()
        node = fake_bin / "node"
        npm = fake_bin / "npm"
        node.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = \"-p\" ]; then\n"
            "  case \"$2\" in *process.versions*) printf '22\\n' ;; *) printf '4.1.3\\n' ;; esac\n"
            "  exit 0\n"
            "fi\n"
            "if [ \"$1\" = \"-\" ]; then exit 0; fi\n"
            "case \"$*\" in\n"
            "  *--probe*) test -d \"$HOME/.cache/kami/mathjax/4.1.3/node_modules\" ;;\n"
            "  *) exit 1 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        npm.write_text(
            "#!/bin/sh\nmkdir -p node_modules\n",
            encoding="utf-8",
        )
        node.chmod(0o755)
        npm.chmod(0o755)
        math_parent = temp_root / ".cache" / "kami" / "mathjax"
        lock = math_parent / ".install-4.1.3.lock"
        stale = math_parent / ".install-4.1.3-stale"
        lock.mkdir(parents=True)
        stale.mkdir()
        (stale / "partial").write_text("partial", encoding="utf-8")
        (lock / "pid").write_text("99999999\n", encoding="utf-8")
        (lock / "staging").write_text(f"{stale}\n", encoding="utf-8")
        environment = os.environ.copy()
        environment["HOME"] = str(temp_root)
        environment["PATH"] = f"{fake_bin}:/usr/bin:/bin"
        environment.pop("XDG_CACHE_HOME", None)
        result = subprocess.run(
            ["bash", str(REPO_ROOT / "scripts" / "ensure_mathjax.sh")],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
        )
        target = math_parent / "4.1.3" / "node_modules"
        recovered = (
            result.returncode == 0
            and target.is_dir()
            and not lock.exists()
            and not stale.exists()
        )
        truncated_results = []
        for owner_text in ("", "99999999"):
            shutil.rmtree(math_parent / "4.1.3")
            lock.mkdir()
            (lock / "pid").write_text(owner_text, encoding="utf-8")
            truncated = subprocess.run(
                ["bash", str(REPO_ROOT / "scripts" / "ensure_mathjax.sh")],
                cwd=REPO_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=10,
            )
            truncated_results.append(
                truncated.returncode == 0
                and target.is_dir()
                and not lock.exists()
            )
        recovered = recovered and all(truncated_results)
    check("MathJax installer reclaims a dead owner's lock and controlled staging",
          recovered,
          f"initial={(result.stdout + result.stderr)[:300]} "
          f"truncated={truncated_results}")


def test_mathjax_cache_survives_weasyprint_runtime_configuration() -> None:
    from math_render import probe_mathjax

    status = probe_mathjax()
    if status["status"] != "available":
        skip("MathJax cache after WeasyPrint configuration",
             status.get("detail", "locked runtime unavailable"),
             ci_required=True)
        return
    environment = os.environ.copy()
    environment.pop("XDG_CACHE_HOME", None)
    environment.pop("NODE_OPTIONS", None)
    code = (
        "import json, sys;"
        "sys.path.insert(0, 'scripts');"
        "from optional_deps import require_weasyprint_html;"
        "from math_render import probe_mathjax;"
        "require_weasyprint_html();"
        "print(json.dumps(probe_mathjax()))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        configured = json.loads(result.stdout)
    except json.JSONDecodeError:
        configured = {}
    check("WeasyPrint initialization does not redirect the MathJax cache",
          result.returncode == 0 and configured.get("status") == "available",
          (result.stdout + result.stderr)[:500])


def test_highlight_without_language() -> None:
    html = '<pre><code>def foo():\n    pass</code></pre>'
    out = highlight_code_blocks(html)
    check("highlight does not modify plain code block",
          out == html,
          f"out differs: {out[:200]}")


def test_highlight_accepts_valid_class_attribute_variants() -> None:
    if importlib.util.find_spec("pygments") is None:
        skip("highlight class attribute variants", "Pygments unavailable", ci_required=True)
        return

    cases = [
        "<pre><code class='language-python'>print(1)</code></pre>",
        '<pre><code id="sample" class="language-python">print(1)</code></pre>',
        '<pre><code class="language-python extra">print(1)</code></pre>',
        '<PRE><CODE CLASS="extra language-python">print(1)</CODE></PRE>',
    ]
    outputs = [highlight_code_blocks(html) for html in cases]
    check("highlight accepts quotes, attribute order, multiple classes, and tag case",
          all("<span" in output and "style=" in output for output in outputs),
          str(outputs))


def test_highlight_without_pygments_dependency() -> None:
    html = '<pre><code class="language-python">def foo():\n    pass</code></pre>'
    original_import = builtins.__import__
    original_warned = highlight_mod._WARNED_MISSING_PYGMENTS

    def fake_import(name, *args, **kwargs):
        if name == "pygments" or name.startswith("pygments."):
            raise ImportError("blocked for fallback test")
        return original_import(name, *args, **kwargs)

    try:
        highlight_mod._WARNED_MISSING_PYGMENTS = False
        builtins.__import__ = fake_import
        warning = io.StringIO()
        with contextlib.redirect_stderr(warning):
            out = highlight_code_blocks(html)
    finally:
        builtins.__import__ = original_import
        highlight_mod._WARNED_MISSING_PYGMENTS = original_warned

    check("highlight falls back unchanged without Pygments",
          out == html,
          f"out differs: {out[:200]}")
    check("highlight warns when Pygments is missing",
          "WARN: Pygments is not installed" in warning.getvalue(),
          f"warning: {warning.getvalue()}")


def test_render_pdf_preserves_last_good_output_on_post_render_failure() -> None:
    """A failed metadata/page validation must not replace the prior PDF."""
    import render as render_mod

    class FakeHTML:
        def __init__(self, **_kwargs):
            pass

        def write_pdf(self, path: str) -> None:
            Path(path).write_bytes(b"new-candidate")

    original_html = render_mod.require_weasyprint_html
    original_reader = render_mod.require_pypdf_reader
    original_metadata = render_mod.set_pdf_metadata
    try:
        render_mod.require_weasyprint_html = lambda: FakeHTML
        render_mod.require_pypdf_reader = lambda: object

        def fail_metadata(*_args, **_kwargs) -> None:
            raise RuntimeError("injected metadata failure")

        render_mod.set_pdf_metadata = fail_metadata
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "source.html"
            out = root / "output.pdf"
            src.write_text("<html><body>candidate</body></html>", encoding="utf-8")
            out.write_bytes(b"last-good")
            try:
                render_mod.render_pdf(src, out)
            except RuntimeError as exc:
                failed = "metadata failure" in str(exc)
            else:
                failed = False
            staged = list(root.glob(".output.pdf-*"))
            check("render failure preserves the last good PDF",
                  failed and out.read_bytes() == b"last-good",
                  f"failed={failed} bytes={out.read_bytes()!r}")
            check("render failure cleans staged candidates", staged == [], str(staged))
    finally:
        render_mod.require_weasyprint_html = original_html
        render_mod.require_pypdf_reader = original_reader
        render_mod.set_pdf_metadata = original_metadata


def test_pdf_metadata_preserves_document_navigation_and_language() -> None:
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import NameObject, RectangleObject, TextStringObject
        from render import set_pdf_metadata
    except ImportError as exc:
        skip("PDF metadata structure preservation", str(exc), ci_required=True)
        return

    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d) / "structured.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.add_outline_item("Chapter", 0)
        writer.add_named_destination("chapter", 0)
        writer.add_uri(
            0,
            "https://example.com",
            RectangleObject([0, 0, 20, 20]),
        )
        writer.root_object.update({
            NameObject("/Lang"): TextStringObject("en-US"),
        })
        writer.add_metadata({"/Author": "{{AUTHOR}}", "/Title": "Structured"})
        writer.write(str(pdf))

        set_pdf_metadata(pdf, author="Ada Lovelace")
        reader = PdfReader(str(pdf))
        root = reader.trailer["/Root"]
        annotation_count = len(reader.pages[0].get("/Annots", []))
        metadata = dict(reader.metadata or {})
        structure = {
            "pages": len(reader.pages),
            "outline": len(reader.outline),
            "names": sorted(reader.named_destinations),
            "lang": str(root.get("/Lang")),
            "annotations": annotation_count,
        }

    check("PDF metadata update preserves catalog navigation and annotations",
          structure == {
              "pages": 1,
              "outline": 1,
              "names": ["chapter"],
              "lang": "en-US",
              "annotations": 1,
          },
          str(structure))
    check("PDF metadata update changes only placeholder author and Kami stamps",
          metadata.get("/Author") == "Ada Lovelace"
          and metadata.get("/Title") == "Structured"
          and metadata.get("/Producer") == "Kami"
          and metadata.get("/Creator") == "Kami",
          str(metadata))


def test_build_slides_requires_a_fresh_valid_pptx() -> None:
    import render as render_mod

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        templates = root / "templates"
        examples = root / "examples"
        templates.mkdir()
        examples.mkdir()
        (templates / "slides.py").write_text("# fixture", encoding="utf-8")
        out = examples / "slides.pptx"
        out.write_bytes(b"last-good")

        original_templates = render_mod.TEMPLATES
        original_examples = render_mod.EXAMPLES
        original_targets = render_mod.pptx_targets
        original_run = render_mod.subprocess.run
        mode = "missing"

        def fake_run(command, **_kwargs):
            candidate = Path(command[-1])
            if mode == "invalid":
                candidate.write_bytes(b"not-a-pptx")
            elif mode == "valid":
                with zipfile.ZipFile(candidate, "w") as archive:
                    for entry in render_mod._PPTX_REQUIRED_ENTRIES:
                        archive.writestr(entry, b"fixture")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        try:
            render_mod.TEMPLATES = templates
            render_mod.EXAMPLES = examples
            render_mod.pptx_targets = lambda: {"slides": "slides.py"}
            render_mod.subprocess.run = fake_run

            missing_ok = silently(render_mod.build_slides, "slides")
            missing_preserved = out.read_bytes() == b"last-good"
            mode = "invalid"
            invalid_ok = silently(render_mod.build_slides, "slides")
            invalid_preserved = out.read_bytes() == b"last-good"
            mode = "valid"
            valid_ok = silently(render_mod.build_slides, "slides")
            valid_issue = render_mod._pptx_issue(out)
        finally:
            render_mod.TEMPLATES = original_templates
            render_mod.EXAMPLES = original_examples
            render_mod.pptx_targets = original_targets
            render_mod.subprocess.run = original_run

        leftovers = list(examples.glob(".slides.pptx-*"))

    check("PPTX build rejects missing and invalid candidates without replacement",
          not missing_ok and missing_preserved and not invalid_ok and invalid_preserved,
          f"missing={missing_ok}/{missing_preserved} invalid={invalid_ok}/{invalid_preserved}")
    check("PPTX build atomically accepts a fresh valid package",
          valid_ok and valid_issue is None and leftovers == [],
          f"valid={valid_ok} issue={valid_issue} leftovers={leftovers}")


def test_release_gate_rejects_identity_mismatches() -> None:
    from release_gate import release_identity_issues

    good = release_identity_issues("V1.2.3", "1.2.3", "same", "same")
    wrong_tag = release_identity_issues("V1.2.4", "1.2.3", "same", "same")
    wrong_sha = release_identity_issues("V1.2.3", "1.2.3", "head", "tag")
    check("release identity accepts an exact tag, version, and SHA", good == [], str(good))
    check("release identity rejects a tag/version mismatch",
          any("does not match VERSION" in issue for issue in wrong_tag), str(wrong_tag))
    check("release identity rejects a tag/checkout SHA mismatch",
          any("does not match checkout HEAD" in issue for issue in wrong_sha), str(wrong_sha))


def test_release_gate_resolves_only_the_tag_namespace() -> None:
    import release_gate as release_gate_mod

    calls = []
    original_git = release_gate_mod._git
    try:
        release_gate_mod._git = lambda *args: calls.append(args) or "tag-sha"
        resolved = release_gate_mod.resolve_tag_commit("V1.2.3")
    finally:
        release_gate_mod._git = original_git
    check("release gate cannot resolve a same-named branch as a tag",
          resolved == "tag-sha"
          and calls == [("rev-parse", "--verify", "refs/tags/V1.2.3^{commit}")],
          str(calls))


def test_release_gate_requires_main_push_provenance() -> None:
    from release_gate import check_run_issues

    pr_run = [{
        "headSha": "candidate",
        "headBranch": "feature/release",
        "event": "pull_request",
        "status": "completed",
        "conclusion": "success",
    }]
    main_run = [{
        "headSha": "candidate",
        "headBranch": "main",
        "event": "push",
        "status": "completed",
        "conclusion": "success",
    }]
    check("release gate rejects successful PR-only checks",
          bool(check_run_issues(pr_run, "candidate")), str(pr_run))
    check("release gate accepts exact-SHA checks from a main push",
          check_run_issues(main_run, "candidate") == [], str(main_run))


def test_release_gate_requires_mainline_reachability() -> None:
    import release_gate as release_gate_mod

    original_git = release_gate_mod._git
    original_run = release_gate_mod.subprocess.run
    try:
        release_gate_mod._git = lambda *args: "main-sha"
        release_gate_mod.subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args, returncode=1, stdout="", stderr="")
        issues = release_gate_mod.mainline_issues("tag-sha", "origin/main")
    finally:
        release_gate_mod._git = original_git
        release_gate_mod.subprocess.run = original_run
    check("release gate rejects commits outside origin/main",
          len(issues) == 1 and "not reachable from origin/main" in issues[0],
          str(issues))


def test_release_gate_compares_zip_payloads_not_container_bytes() -> None:
    from release_gate import archive_payload_issues

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        tracked = root / "tracked.zip"
        equivalent = root / "equivalent.zip"
        changed = root / "changed.zip"
        duplicated = root / "duplicated.zip"
        with zipfile.ZipFile(tracked, "w") as archive:
            archive.writestr("kami/VERSION", "1.2.3")
        with zipfile.ZipFile(equivalent, "w") as archive:
            info = zipfile.ZipInfo("kami/VERSION", date_time=(2026, 1, 2, 3, 4, 6))
            archive.writestr(info, "1.2.3")
        with zipfile.ZipFile(changed, "w") as archive:
            archive.writestr("kami/VERSION", "1.2.4")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(duplicated, "w") as archive:
                archive.writestr("kami/VERSION", "first")
                archive.writestr("kami/VERSION", "second")

        same_issues = archive_payload_issues(tracked, equivalent)
        changed_issues = archive_payload_issues(tracked, changed)
        duplicate_issues = archive_payload_issues(duplicated, tracked)
        check("release gate ignores ZIP container timestamp differences",
              tracked.read_bytes() != equivalent.read_bytes() and same_issues == [],
              str(same_issues))
        check("release gate rejects changed entry payloads",
              changed_issues == ["candidate payload differs: kami/VERSION"],
              str(changed_issues))
        check("release gate rejects duplicate ZIP entry names",
              len(duplicate_issues) == 1
              and "duplicate ZIP entry: kami/VERSION" in duplicate_issues[0],
              str(duplicate_issues))


def test_release_workflow_reads_back_required_reactions() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8")
    expected = ("+1", "eyes", "heart", "hooray", "laugh", "rocket")
    check("release workflow reads reactions back after posting",
          "gh api --paginate" in workflow
          and "release reactions missing" in workflow
          and all(workflow.count(reaction) >= 2 for reaction in expected),
          "release workflow lacks a final reaction-set assertion")


def test_release_workflow_preserves_published_version_payloads() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8")
    check("release workflow requires main push provenance",
          "--json headSha,headBranch,event,status,conclusion" in workflow
          and "--main-ref origin/main" in workflow
          and "--checks-json /tmp/kami-check-runs.json" in workflow,
          "release workflow can accept non-main CI")
    check("release workflow refuses same-version payload replacement",
          "--clobber" not in workflow
          and "gh release download" in workflow
          and "existing kami.zip already matches this release" in workflow,
          "release workflow can overwrite a published archive")


def test_release_note_help_matches_placeholder_flow() -> None:
    draft = (REPO_ROOT / "scripts" / "draft-release-notes.py").read_text(
        encoding="utf-8")
    release_doc = (REPO_ROOT / "docs" / "release.md").read_text(encoding="utf-8")
    check("release-note help edits the workflow-created placeholder",
          "gh release edit --notes-file" in draft
          and "gh release create --notes-file" not in draft
          and '"--match", "V[0-9]*.[0-9]*.[0-9]*"' in draft
          and "V<prev>..HEAD" in release_doc
          and "let CI create the placeholder" in release_doc,
          "draft-release-notes.py and docs/release.md disagree")


def test_marp_themes_token_synced() -> None:
    """Marp theme CSS keeps its :root tokens in sync with tokens.json.

    Locks the invariant AGENTS.md documents (tokens.py globs marp/*.css), so the
    Marp decks cannot silently drift even if that glob is later refactored away.
    """
    from shared import TOKENS_FILE
    from tokens import CSS_VAR, ROOT_BLOCK

    canonical = {k.lstrip("-"): v.strip().lower()
                 for k, v in json.loads(TOKENS_FILE.read_text(encoding="utf-8")).items()}
    marp_files = sorted((TEMPLATES / "marp").glob("*.css"))
    check("marp theme CSS present", len(marp_files) >= 1, f"found {len(marp_files)} file(s)")

    drift: list[str] = []
    checked = 0
    for path in marp_files:
        block = ROOT_BLOCK.search(path.read_text(encoding="utf-8", errors="replace"))
        if not block:
            continue
        checked += 1
        found = {m.group(1): m.group(2).strip().lower()
                 for m in CSS_VAR.finditer(block.group(1))}
        for name, expected in canonical.items():
            actual = found.get(name)
            if actual is not None and actual != expected:
                drift.append(f"{path.name}: --{name} expected {expected}, got {actual}")
    check("marp theme :root tokens match tokens.json",
          checked >= 1 and not drift,
          "; ".join(drift) if drift else f"checked {checked}, no :root block found")


def test_mermaid_theme_matches_tokens() -> None:
    from shared import TOKENS_FILE
    canonical = json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
    issues = _mermaid_theme_drift(canonical)
    check("mermaid theme colors and role docs match tokens.json",
          issues == [],
          f"issues: {issues}")


def test_mermaid_theme_drift_flags_token_mismatch() -> None:
    from shared import TOKENS_FILE
    canonical = json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
    canonical["--brand"] = "#000000"
    issues = _mermaid_theme_drift(canonical)
    check("mermaid theme drift flags accent token mismatch",
          any("accent" in issue and "--brand" in issue for issue in issues),
          f"issues: {issues}")


def test_mermaid_normalize_defaults_match_theme() -> None:
    import mermaid_normalize as mermaid_mod
    theme = json.loads((REPO_ROOT / "references" / "mermaid-theme.json").read_text(encoding="utf-8"))
    expected_colors = {f"--{key}": value for key, value in theme["colors"].items()}
    check("mermaid normalizer fallback colors mirror mermaid-theme.json",
          mermaid_mod._DEFAULT_COLORS == expected_colors,
          f"default={mermaid_mod._DEFAULT_COLORS}, theme={expected_colors}")
    check("mermaid normalizer fallback font mirrors mermaid-theme.json",
          mermaid_mod._DEFAULT_FONT_STACK == theme["cssFontStack"],
          f"default={mermaid_mod._DEFAULT_FONT_STACK}, theme={theme['cssFontStack']}")


# --------------------------- mermaid normalize ---------------------------

def test_mermaid_color_mix_srgb_single_pct() -> None:
    from mermaid_normalize import _Resolver
    r = _Resolver({"--fg": "#141413", "--bg": "#f5f4ed"})
    # color-mix(in srgb, fg 12%, bg) == 0.12*fg + 0.88*bg
    got = r.hex_of("color-mix(in srgb, var(--fg) 12%, var(--bg))")
    check("color-mix(in srgb, fg 12%, bg) resolves to warm gray",
          got == "#dad9d3", f"got {got}")


def test_mermaid_color_mix_both_pct() -> None:
    from mermaid_normalize import _Resolver
    r = _Resolver({"--bg": "#ffffff", "--c": "#000000"})
    got = r.hex_of("color-mix(in srgb, var(--bg) 75%, var(--c) 25%)")
    check("color-mix honors both explicit percentages", got == "#bfbfbf", f"got {got}")


def test_mermaid_normalize_strips_unsafe_features() -> None:
    from mermaid_normalize import normalize
    # Root carries a deliberately NON-Kami theme (red accent, white bg) to prove
    # the normalizer re-themes to the Kami palette regardless of source theme.
    raw = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'style="--bg:#ffffff;--fg:#000000;--accent:#ff0000;background:var(--bg)">'
        "<style>@import url('https://fonts.googleapis.com/css2?family=Charter');\n"
        "  text { font-family: 'Charter', system-ui, sans-serif; }\n"
        "  svg { --_t: color-mix(in srgb, var(--fg) 25%, var(--bg)); }</style>"
        '<rect fill="var(--accent)" stroke="var(--fg)"/></svg>'
    )
    out = normalize(raw)
    check("normalize removes color-mix()", "color-mix(" not in out, out)
    check("normalize removes var()", "var(" not in out, out)
    check("normalize removes google-fonts import", "googleapis" not in out, out)
    check("normalize drops the quoted single-family bug", "'Charter'" not in out, out)
    check("normalize keeps the Kami CJK serif stack", "TsangerJinKai02" in out, out)
    check("normalize resolves fill to a static hex", 'fill="#' in out, out)
    check("normalize re-themes accent to Kami ink-blue",
          "#1b365d" in out.lower(), out)
    check("normalize drops the source theme's red accent",
          "#ff0000" not in out.lower(), out)


def test_mermaid_lint_flags_unnormalized_svg() -> None:
    body = '<svg><rect fill="color-mix(in srgb, #000000 50%, #ffffff)"/></svg>'
    path = write_temp_html(body, suffix=".html")  # not a screen-template name
    try:
        rules = {f.rule for f in scan_file(path)}
        check("scan_file flags un-normalized mermaid color-mix",
              "mermaid-color-mix" in rules, f"rules={rules}")
    finally:
        path.unlink(missing_ok=True)


def test_mermaid_diagram_templates_normalized() -> None:
    for name in ("sequence.html", "class.html", "er.html"):
        path = REPO_ROOT / "assets" / "diagrams" / name
        check(f"diagram {name} exists", path.exists(), f"missing {path}")
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        check(f"{name} carries no color-mix()", "color-mix(" not in text)
        check(f"{name} carries no <foreignObject>", "<foreignObject" not in text)
        check(f"{name} carries no runtime web-font import", "googleapis" not in text)


def test_mermaid_diagrams_match_their_mmd_sources() -> None:
    """The committed diagram HTML must still carry every node/participant/entity
    label from its .mmd source. No Node regenerates these, so this guards against
    a .mmd edit that silently leaves the committed SVG stale."""
    src_dir = REPO_ROOT / "assets" / "diagrams" / "src"
    sources = sorted(src_dir.glob("*.mmd"))
    check("diagram .mmd sources present", len(sources) >= 1, f"found {len(sources)}")
    for mmd in sources:
        html_path = REPO_ROOT / "assets" / "diagrams" / f"{mmd.stem}.html"
        check(f"{mmd.stem}.html exists for {mmd.name}", html_path.exists())
        if not html_path.exists():
            continue
        labels: set[str] = set()
        for line in mmd.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            m = re.match(r"participant\s+\S+\s+as\s+(.+)", line)
            if m:
                labels.add(m.group(1).strip())
            m = re.match(r"class\s+(\w+)", line)
            if m:
                labels.add(m.group(1))
            labels.update(re.findall(r"\b([A-Z][A-Z_]{2,})\b", line))  # ER entities
        body = html_path.read_text(encoding="utf-8")
        missing = sorted(label for label in labels if label not in body)
        check(f"{mmd.stem}.html carries all {mmd.name} labels",
              not missing, f"missing labels (regenerate the diagram): {missing}")


def test_mermaid_normalize_rejects_non_beautiful_mermaid() -> None:
    """A non-beautiful-mermaid SVG (no --bg/--fg roles) must raise, not silently
    emit unresolved colors."""
    from mermaid_normalize import normalize
    raised = False
    try:
        normalize('<svg xmlns="http://www.w3.org/2000/svg"><rect fill="#000"/></svg>')
    except ValueError:
        raised = True
    check("normalize rejects input lacking --bg/--fg color roles", raised)


def test_mermaid_normalize_cli_accepts_output_before_input() -> None:
    """CLI parsing should accept both `input -o out` and `-o out input`."""
    script = REPO_ROOT / "scripts" / "mermaid_normalize.py"
    raw = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'style="--bg:#ffffff;--fg:#000000;--accent:#ff0000">'
        '<rect fill="var(--accent)" /></svg>'
    )
    with tempfile.TemporaryDirectory() as d:
        dp = Path(d)
        src = dp / "raw.svg"
        out = dp / "clean.svg"
        src.write_text(raw, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(script), "-o", str(out), str(src)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        body = out.read_text(encoding="utf-8") if out.exists() else ""
        check("mermaid_normalize CLI supports -o before input",
              result.returncode == 0 and out.exists() and "color-mix(" not in body and "var(" not in body,
              (result.stdout + result.stderr).strip())


def test_mermaid_normalize_cli_reports_missing_input() -> None:
    """Missing input should be a concise ERROR, not a Python traceback."""
    script = REPO_ROOT / "scripts" / "mermaid_normalize.py"
    with tempfile.TemporaryDirectory() as d:
        result = subprocess.run(
            [sys.executable, str(script), str(Path(d) / "missing.svg")],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        combined = result.stdout + result.stderr
        check("mermaid_normalize CLI reports missing input without traceback",
              result.returncode == 1 and "ERROR:" in combined and "Traceback" not in combined,
              combined.strip())


# --------------------------- content IR ---------------------------

def test_content_schemas_cover_all_public_doc_types() -> None:
    from shared import content_schema_types, public_document_template_kinds
    expected = public_document_template_kinds() | {"landing-page"}
    actual = set(content_schema_types())
    check("content schemas cover every public doc type plus landing-page",
          actual == expected,
          f"missing: {sorted(expected - actual)}, extra: {sorted(actual - expected)}")


def test_content_schemas_parse_and_are_objects() -> None:
    from shared import SCHEMAS_DIR, content_schema_types
    bad = []
    for name in content_schema_types():
        try:
            schema = json.loads((SCHEMAS_DIR / f"{name}.json").read_text(encoding="utf-8"))
            if schema.get("type") != "object" or "required" in schema and not schema["required"]:
                bad.append(name)
        except json.JSONDecodeError:
            bad.append(name)
    check("content schemas parse as object contracts", not bad, f"bad: {bad}")


def test_changelog_contract_requires_four_to_eight_changes() -> None:
    from content import validate_content_file

    def validate(version: dict) -> list[str]:
        _, issues = validate_content_file({
            "type": "changelog",
            "lang": "en",
            "content": {"product": "Kami", "versions": [version]},
        })
        return issues

    base = {"version": "V1.2.3", "date": "2026-08-23"}
    valid = validate({
        **base,
        "breaking": [{"change": "Changed command", "migration": "Use new command"}],
        "features": ["Added export", "Added preview"],
        "fixes": ["Fixed wrapping"],
    })
    missing = validate(base)
    too_few = validate({**base, "fixes": ["Fixed first", "Fixed second", "Fixed third"]})
    too_many = validate({
        **base,
        "features": [f"Added feature {index}" for index in range(8)],
        "fixes": ["Fixed overflow"],
    })
    empty_class = validate({**base, "features": []})

    check("changelog accepts four changes split across supported classes",
          valid == [], repr(valid))
    check("changelog requires at least one change class",
          any("requires at least one" in issue for issue in missing),
          repr(missing))
    check("changelog enforces the combined four-to-eight entry envelope",
          any("got 3" in issue for issue in too_few)
          and any("got 9" in issue for issue in too_many),
          f"few={too_few} many={too_many}")
    check("changelog rejects an explicitly empty change class",
          any("too few items" in issue for issue in empty_class),
          repr(empty_class))


def test_validate_node_flags_structural_defects() -> None:
    from content import validate_node
    schema = {
        "type": "object",
        "required": ["title", "metrics"],
        "properties": {
            "title": {"type": "string", "minLength": 2, "maxLength": 10},
            "metrics": {
                "type": "array", "minItems": 3, "maxItems": 4,
                "items": {"type": "object", "required": ["value"],
                          "properties": {"value": {"type": "string"}}},
            },
            "layout": {"type": "string", "enum": ["cover", "content"]},
        },
    }
    ok = validate_node({"title": "Hello", "metrics": [{"value": "1"}] * 3}, schema)
    check("validate_node passes a conforming object", ok == [])
    issues = validate_node(
        {"title": "way too long for the cap", "metrics": [{}], "layout": "hero"},
        schema,
    )
    text = "\n".join(issues)
    check("validate_node flags length, count, required, and enum defects",
          "too long" in text and "too few items" in text
          and "missing required field 'value'" in text and "'hero' not in" in text,
          text)
    numeric = validate_node(0, {"type": "integer", "minimum": 1, "maximum": 3}, "page")
    check("validate_node enforces numeric bounds",
          numeric == ["page: too small (0 < 1)"], str(numeric))


def test_coverage_issues_catch_dropped_values() -> None:
    from content import coverage_issues
    content = {
        "name": "Kami",
        "metric": "62%",
        "note": "p" * 120,
        "image": "shot.png",
        "cjk": "用户 2M 规模",
    }
    html_text = "Kami cut latency 62% at 用户2M规模 scale"
    issues, checked, skipped = coverage_issues(content, html_text)
    check("coverage passes present values, skips prose and images, normalizes CJK spacing",
          issues == [] and checked == 3 and skipped == 1,
          f"issues={issues} checked={checked} skipped={skipped}")
    issues, _, _ = coverage_issues({"metric": "$340K"}, html_text)
    check("coverage flags a dropped atomic value",
          len(issues) == 1 and "$340K" in issues[0], str(issues))


def test_check_content_cli_validates_and_covers() -> None:
    from content import check_content
    payload = {
        "type": "letter",
        "lang": "en",
        "content": {
            "sender": "Ada Lovelace, London",
            "date": "2026-07-13",
            "recipient": "Charles Babbage",
            "salutation": "Dear Charles,",
            "paragraphs": [
                "I write to state my purpose in one sentence: the engine deserves a program of its own.",
                "The evidence sits in the notes: fifty operations, one loop, and a table the machine can follow.",
                "My ask is specific: review the table this month so we can test it on the mill.",
            ],
            "signoff": "Sincerely,",
            "signature": "Ada",
        },
    }
    with tempfile.TemporaryDirectory() as d:
        content_path = Path(d) / "content.json"
        content_path.write_text(json.dumps(payload), encoding="utf-8")
        rc = silently(check_content, [str(content_path)])
        check("check_content accepts a valid letter IR", rc == 0)
        html = write_temp_html(
            "<html><body><p>Ada Lovelace, London 2026-07-13 Charles Babbage "
            "Dear Charles, My ask is specific: review the table this month so "
            "we can test it on the mill. Sincerely, Ada</p></body></html>"
        )
        try:
            rc = silently(check_content, [str(content_path), str(html)])
            check("check_content coverage passes when atomic values present", rc == 0)

            ambiguous_html = write_temp_html(
                html.read_text(encoding="utf-8").replace(
                    "<p>", '<p style="font-size:calc(1px - 1px)">',
                )
            )
            try:
                ambiguous_rc = silently(
                    check_content,
                    [str(content_path), str(ambiguous_html)],
                )
                check("check_content degrades indeterminate visibility evidence",
                      ambiguous_rc == 2)
            finally:
                ambiguous_html.unlink()

            missing_text_html = write_temp_html(
                html.read_text(encoding="utf-8")
                .replace("2026-07-13", "2026-07-14")
                .replace("</body>", '<img srcset="a.png 1x,b.png 2x"></body>')
            )
            try:
                missing_text_rc = silently(
                    check_content,
                    [str(content_path), str(missing_text_html)],
                )
                check("resource ambiguity cannot downgrade definite missing text",
                      missing_text_rc == 1)
            finally:
                missing_text_html.unlink()

            for style in (
                "clip-path:circle(50%)",
                "mask-image:url(#rounded)",
                "filter:url(#soften)",
            ):
                decorated_html = write_temp_html(
                    html.read_text(encoding="utf-8")
                    .replace("2026-07-13", "2026-07-14")
                    .replace(
                        "</body>",
                        f'<img style="{style}" src="decorative.svg"></body>',
                    )
                )
                try:
                    decorated_rc = silently(
                        check_content,
                        [str(content_path), str(decorated_html)],
                    )
                    check("decorative resource ambiguity cannot downgrade missing text",
                          decorated_rc == 1, style)
                finally:
                    decorated_html.unlink()

            for decoration in (
                '<svg><path filter="url(#shadow)"></path></svg>',
                '<svg><circle mask="url(#fade)"></circle></svg>',
                '<svg><g clip-path="url(#round)"></g></svg>',
                '<style>.decor { clip-path:circle(50%) }</style>'
                '<svg><path class="decor"></path></svg>',
            ):
                decorated_svg_html = write_temp_html(
                    html.read_text(encoding="utf-8")
                    .replace("2026-07-13", "2026-07-14")
                    .replace("</body>", f"{decoration}</body>")
                )
                try:
                    decorated_svg_rc = silently(
                        check_content,
                        [str(content_path), str(decorated_svg_html)],
                    )
                    check("decorative SVG ambiguity cannot downgrade missing text",
                          decorated_svg_rc == 1, decoration)
                finally:
                    decorated_svg_html.unlink()

            payload["brief"] = {
                "audience": "Technical collaborator",
                "job": "Secure review",
                "template": "letter-en",
                "formats": ["html", "pdf"],
                "page_target": 1,
                "required_assets": ["must-appear-logo.svg"],
                "acceptance_checks": ["required logo is embedded"],
            }
            content_path.write_text(json.dumps(payload), encoding="utf-8")
            missing_asset_rc = silently(check_content, [str(content_path), str(html)])
            check("check_content coverage rejects a missing required brief asset",
                  missing_asset_rc == 1)
            mixed_html = write_temp_html(
                html.read_text(encoding="utf-8")
                .replace("2026-07-13", "2026-07-14")
                .replace("</body>", '<img srcset="a.png 1x,b.png 2x"></body>')
            )
            try:
                mixed_report = io.StringIO()
                with contextlib.redirect_stdout(mixed_report):
                    mixed_rc = check_content(
                        [str(content_path), str(mixed_html)]
                    )
                report = mixed_report.getvalue()
                check("mixed coverage reports definite and indeterminate findings separately",
                      mixed_rc == 1
                      and "definitely missing" in report
                      and "NOTE:" in report
                      and report.index("content.date") < report.index("NOTE:")
                      and report.index("brief.required_assets") > report.index("NOTE:"),
                      report)
            finally:
                mixed_html.unlink()
            html.write_text(
                html.read_text(encoding="utf-8").replace(
                    "</body>", '<img src="must-appear-logo.svg" alt=""></body>'
                ),
                encoding="utf-8",
            )
            embedded_asset_rc = silently(check_content, [str(content_path), str(html)])
            check("check_content coverage accepts an embedded required brief asset",
                  embedded_asset_rc == 0)
        finally:
            html.unlink()
        del payload["content"]["signature"]
        content_path.write_text(json.dumps(payload), encoding="utf-8")
        rc = silently(check_content, [str(content_path)])
        check("check_content rejects a missing required field", rc == 1)
        rc = silently(check_content, [])
        check("check_content usage error returns 2", rc == 2)


def test_content_ir_rejects_invalid_envelope() -> None:
    from content import validate_content_file

    body = {
        "sender": "Ada Lovelace, London",
        "date": "2026-07-13",
        "recipient": "Charles Babbage",
        "salutation": "Dear Charles,",
        "paragraphs": [
            "I write to state my purpose in one sentence: the engine deserves a program of its own.",
            "The evidence sits in the notes: fifty operations, one loop, and a table the machine can follow.",
            "My ask is specific: review the table this month so we can test it on the mill.",
        ],
        "signoff": "Sincerely,",
        "signature": "Ada",
    }
    valid_type, valid_issues = validate_content_file({
        "type": "letter", "lang": "zh-TW", "content": body,
    })
    _, invalid_issues = validate_content_file({
        "type": "letter", "lang": "not_a_locale", "content": body,
        "unexpected": True,
    })
    check("content IR accepts a strict language-tagged envelope",
          valid_type == "letter" and valid_issues == [], str(valid_issues))
    check("content IR rejects invalid lang and unknown top-level fields",
          any("'lang'" in issue for issue in invalid_issues)
          and any("unknown field 'unexpected'" in issue for issue in invalid_issues),
          str(invalid_issues))


def test_content_ir_validates_optional_artifact_brief() -> None:
    from content import (
        BRIEF_SCHEMA,
        _brief_contract_issues,
        validate_content_file,
        validate_node,
    )

    body = {
        "sender": "Ada Lovelace, London",
        "date": "2026-07-13",
        "recipient": "Charles Babbage",
        "salutation": "Dear Charles,",
        "paragraphs": [
            "I write to state my purpose in one sentence: the engine deserves a program of its own.",
            "The evidence sits in the notes: fifty operations, one loop, and a table the machine can follow.",
            "My ask is specific: review the table this month so we can test it on the mill.",
        ],
        "signoff": "Sincerely,",
        "signature": "Ada",
    }
    brief = {
        "audience": "Technical collaborator",
        "job": "Secure a review of the program table",
        "template": "letter-en",
        "formats": ["html", "pdf"],
        "page_target": 1,
        "acceptance_checks": ["one page", "specific ask remains visible"],
        "target": {"surface": "letter body", "page": 1},
        "preserve": ["letterhead", "signature"],
        "evidence": ["rendered page 1"],
    }
    _, valid_issues = validate_content_file({
        "type": "letter", "lang": "en", "brief": brief, "content": body,
    })
    invalid = dict(brief)
    invalid["formats"] = ["docx"]
    invalid["page_target"] = 0
    invalid["mystery"] = True
    _, invalid_issues = validate_content_file({
        "type": "letter", "lang": "en", "brief": invalid, "content": body,
    })
    text = "\n".join(invalid_issues)
    check("content IR accepts a structured artifact brief", valid_issues == [], str(valid_issues))
    check("content IR rejects unknown brief fields, formats, and page bounds",
          "brief: unknown field 'mystery'" in text
          and "'docx' not in" in text
          and "brief.page_target: too small" in text,
          text)

    conflicting = dict(brief, template="one-pager", page_target=2)
    _, conflict_issues = validate_content_file({
        "type": "one-pager", "lang": "cn", "brief": conflicting,
        "content": {
            "title": "A concise product claim",
            "subtitle": "A subtitle long enough to explain the intended audience and outcome",
            "metrics": [
                {"value": "10x", "label": "faster"},
                {"value": "99%", "label": "coverage"},
                {"value": "2m", "label": "setup"},
            ],
            "argument": [
                "A focused paragraph that explains the user problem, the proposed change, and why it matters now in concrete terms."
            ],
            "evidence": ["Measured result", "Observed behavior", "Verified source"],
            "next_step": "Review the evidence and approve the next test.",
        },
    })
    check("content IR rejects a page target beyond the template ceiling",
          any("exceeds template 'one-pager' maximum 1" in issue for issue in conflict_issues),
          str(conflict_issues))
    one_page_resume_issues = _brief_contract_issues(
        {"template": "resume-en", "formats": ["html", "pdf"], "page_target": 1},
        "resume",
        "en",
    )
    check("brief contract enforces the two-page resume hard stop",
          any("require exactly 2 pages" in issue for issue in one_page_resume_issues),
          str(one_page_resume_issues))

    landing_issues = _brief_contract_issues(
        {"template": "landing-page", "page_target": 2}, "landing-page"
    )
    slides_issues = _brief_contract_issues(
        {"template": "slides", "page_target": 12}, "slides"
    )
    editable_slides_issues = _brief_contract_issues(
        {"template": "slides-en", "formats": ["pptx"], "page_target": 12}, "slides"
    )
    impossible_resume_issues = _brief_contract_issues(
        {"template": "resume", "formats": ["pptx"], "page_target": 2}, "resume"
    )
    wrong_language_issues = _brief_contract_issues(
        {"template": "resume-en", "formats": ["html", "pdf"], "page_target": 2},
        "resume",
        "ko",
    )
    korean_pptx_fallback_issues = _brief_contract_issues(
        {
            "template": "slides-en", "formats": ["pptx"],
            "page_target": 12,
        },
        "slides",
        "ko",
    )
    korean_mixed_fallback_issues = _brief_contract_issues(
        {
            "template": "slides-en", "formats": ["html", "pdf", "pptx"],
            "page_target": 12,
        },
        "slides",
        "ko",
    )
    korean_pdf_wrong_variant_issues = _brief_contract_issues(
        {"template": "slides-en", "formats": ["html", "pdf"], "page_target": 12},
        "slides",
        "ko",
    )
    check("brief contract accepts screen, generic slide, and editable PPTX keys",
          landing_issues == [] and slides_issues == [] and editable_slides_issues == [],
          f"landing={landing_issues} slides={slides_issues} "
          f"editable={editable_slides_issues}")
    check("brief contract rejects a format the selected template cannot produce",
          any("does not support pptx" in issue for issue in impossible_resume_issues),
          str(impossible_resume_issues))
    check("brief contract rejects a known language/template variant mismatch",
          any("does not match language 'ko'" in issue for issue in wrong_language_issues),
          str(wrong_language_issues))
    check("brief contract keeps the documented Korean editable-PPTX fallback",
          korean_pptx_fallback_issues == [], str(korean_pptx_fallback_issues))
    check("brief contract limits the Korean slides-en fallback to editable PPTX",
          any("does not match language 'ko'" in issue
              for issue in korean_pdf_wrong_variant_issues)
          and any("does not match language 'ko'" in issue
                  for issue in korean_mixed_fallback_issues),
          f"pdf={korean_pdf_wrong_variant_issues} mixed={korean_mixed_fallback_issues}")

    marp_brief = dict(
        brief,
        template="slides-marp-en",
        formats=["md", "pdf"],
        page_target=12,
    )
    marp_schema_issues = validate_node(marp_brief, BRIEF_SCHEMA, "brief")
    marp_contract_issues = _brief_contract_issues(marp_brief, "slides", "en")
    korean_marp_issues = _brief_contract_issues(
        dict(marp_brief, template="slides-marp"),
        "slides",
        "ko",
    )
    check("brief contract accepts the shipped Marp authoring path",
          marp_schema_issues == []
          and marp_contract_issues == []
          and korean_marp_issues == [],
          f"schema={marp_schema_issues} contract={marp_contract_issues} "
          f"korean={korean_marp_issues}")

    no_length_contract = dict(brief)
    no_length_contract.pop("page_target")
    target_issues = _brief_contract_issues(no_length_contract, "letter", "en")
    length_only_issues = _brief_contract_issues(
        dict(no_length_contract, length_target="600 to 800 words"),
        "letter",
        "en",
    )
    check("artifact brief requires a page or length target",
          any("page_target or length_target" in issue for issue in target_issues)
          and length_only_issues == [],
          f"missing={target_issues} length_only={length_only_issues}")

    _, legacy_issues = validate_content_file({
        "type": "letter", "lang": "en", "content": body,
    })
    check("content IR keeps pre-brief files valid", legacy_issues == [], str(legacy_issues))


def test_build_cli_dispatches_new_checks() -> None:
    rc, out = run_build_args(["--check-content"])
    check("build.py --check-content without args is a usage error",
          rc == 2 and "usage" in out, out.strip()[:120])
    rc, out = run_build_args(["--check-visual"])
    check("build.py --check-visual without args is a usage error",
          rc == 2 and "usage" in out, out.strip()[:120])
    rc, out = run_build_args(["--doctor"])
    check("build.py --doctor reports capability status",
          rc in {0, 1} and "Kami doctor" in out
          and "visual verification" in out,
          out.strip()[:300])


def test_skill_routes_visual_repairs_and_generated_assets_without_losing_contracts() -> None:
    skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
    diagrams = (REPO_ROOT / "references" / "diagrams.md").read_text(encoding="utf-8")
    for mode in ("New document", "Content-only", "Visual repair", "Generated asset"):
        check(f"SKILL work mode keeps {mode}", mode in skill)
    check("visual repair locks target, preserve, evidence, and artifact matrices",
          all(term in skill for term in (
              "`target`", "`preserve`", "PDF: target page", "Screen: 1280px",
              "PPTX: editable source", "Generated asset: target slot",
          )),
          "visual feedback contract incomplete")
    check("image generation routes from observed capability",
          "Route from observed capability" in skill
          and "Claude, Codex, most coding agents" not in skill,
          "host-name capability list still present")
    check("illustration brief keeps old visual system and adds semantic anchors",
          all(term in diagrams for term in (
              "1. Claim:", "2. Placement:", "3. Reference:", "4. Exclusions:",
              "5. Canvas:", "6. Accent:", "7. Strokes and icons:",
              "8. Labels:", "9. Content spec:",
          ))
          and "After two look-based rejections" in diagrams,
          "illustration brief lost a field")


def test_visual_checklist_and_output_dir() -> None:
    from visual import REVIEW_CHECKLIST, visual_output_dir
    check("visual checklist has stable size and no em dash",
          len(REVIEW_CHECKLIST) == 10 and all("\u2014" not in line for line in REVIEW_CHECKLIST))
    out = visual_output_dir(Path("/tmp/docs/report.pdf"))
    check("visual output dir sits next to the pdf",
          out == Path("/tmp/docs/report-visual"), str(out))


def test_visual_clears_stale_page_images() -> None:
    """A re-render with fewer pages must not leave prior page PNGs behind."""
    from visual import _clear_page_images
    with tempfile.TemporaryDirectory() as d:
        target = Path(d)
        for name in ("page-01.png", "page-07.png", "notes.txt"):
            (target / name).write_bytes(b"x")
        _clear_page_images(target)
        left = sorted(p.name for p in target.iterdir())
        check("stale page PNGs removed, unrelated files kept",
              left == ["notes.txt"], str(left))


def test_coverage_survives_split_markup_values() -> None:
    """Values split across sibling nodes ("62" + "%") must still count as present."""
    from content import coverage_issues
    issues, checked, _ = coverage_issues({"metric": "62%"}, "value:\n62\n%")
    check("coverage rejoins values split by markup",
          issues == [] and checked == 1, str(issues))


def test_coverage_rejects_substrings_and_hidden_text() -> None:
    """Changed facts and hidden-only copies must not satisfy coverage."""
    from content import coverage_issues
    from checks import visible_html_evidence, visible_html_text

    cases = [
        ({"metric": "62%"}, "Revenue reached 162%"),
        ({"metric": "62"}, "Revenue reached 1962"),
        ({"metric": "12 34"}, "Revenue reached 1234"),
        ({"metric": 1.0}, "Revenue reached 1.5"),
    ]
    issues = [coverage_issues(content, text)[0] for content, text in cases]
    check("coverage rejects values embedded in larger or collapsed tokens",
          all(len(found) == 1 for found in issues), str(issues))

    hidden_html = (
        "<html><head><title>62%</title><style>.concealed { display: none }</style></head><body>"
        "<template>62%</template><p hidden>62%</p>"
        '<p aria-hidden="true">62%</p><p style="display: none">62%</p>'
        '<p class="concealed">62%</p>'
        "<p>Visible value is 61%.</p></body></html>"
    )
    text = visible_html_text(hidden_html)
    missing, _, _ = coverage_issues({"metric": "62%"}, text)
    check("coverage ignores head, template, hidden, and display-none text",
          len(missing) == 1, f"text={text!r} issues={missing}")

    malformed_hidden = (
        '<div hidden><img></img><p>SECRET-FACT</p></div>'
        '<p>VISIBLE-FACT</p>'
    )
    malformed_text = visible_html_text(malformed_hidden)
    malformed_missing, _, _ = coverage_issues(
        {"hidden": "SECRET-FACT", "visible": "VISIBLE-FACT"},
        malformed_text,
    )
    check("visible-text parser keeps hidden scope across a void closing tag",
          len(malformed_missing) == 1
          and "SECRET-FACT" in malformed_missing[0]
          and "VISIBLE-FACT" in malformed_text,
          f"text={malformed_text!r} issues={malformed_missing}")

    self_closing_hidden = (
        '<div hidden/><p>SELF-CLOSING-SECRET</p></div>'
        '<p>SELF-CLOSING-VISIBLE</p>'
    )
    self_closing_text = visible_html_text(self_closing_hidden)
    self_closing_missing, _, _ = coverage_issues(
        {
            "hidden": "SELF-CLOSING-SECRET",
            "visible": "SELF-CLOSING-VISIBLE",
        },
        self_closing_text,
    )
    check("visible-text parser follows HTML semantics for non-void self-closing tags",
          len(self_closing_missing) == 1
          and "SELF-CLOSING-SECRET" in self_closing_missing[0]
          and "SELF-CLOSING-VISIBLE" in self_closing_text,
          f"text={self_closing_text!r} issues={self_closing_missing}")

    benign_selector_text = visible_html_text(
        '<style>[hidden] { display: none } '
        '[aria-hidden="true"] { visibility: hidden } '
        ':root { --fallback-display: none }</style>'
        '<p hidden>HIDDEN-BY-ATTRIBUTE</p>'
        '<p aria-hidden="false">VISIBLE-ARIA-FALSE</p>'
        '<p>VISIBLE-AFTER-SELECTOR</p>'
    )
    check("visibility parser scopes attribute selectors and custom properties",
          "HIDDEN-BY-ATTRIBUTE" not in benign_selector_text
          and "VISIBLE-ARIA-FALSE" in benign_selector_text
          and "VISIBLE-AFTER-SELECTOR" in benign_selector_text,
          repr(benign_selector_text))

    important_hidden_text = visible_html_text(
        '<style>.important-secret {'
        'display: none !important; display: block'
        '}</style>'
        '<p class="important-secret">IMPORTANT-SECRET</p>',
        fail_closed=True,
    )
    inline_important_text = visible_html_text(
        '<p style="display:none!important;display:block">INLINE-IMPORTANT-SECRET</p>',
        fail_closed=True,
    )
    visible_var_fallback = visible_html_text(
        '<p style="display:var(--missing, block)">VISIBLE-VAR-FALLBACK</p>',
        fail_closed=True,
    )
    check("visibility parser honors important cascade and visible var fallback",
          "IMPORTANT-SECRET" not in important_hidden_text
          and "INLINE-IMPORTANT-SECRET" not in inline_important_text
          and "VISIBLE-VAR-FALLBACK" in visible_var_fallback,
          f"style={important_hidden_text!r} inline={inline_important_text!r} "
          f"fallback={visible_var_fallback!r}")

    hidden_equivalents = [
        'font-size:0%',
        'font-size:calc(0px)',
        'font-size:min(0px, 1px)',
        'transform:scale(0, 0)',
        'transform:matrix(0,0,0,0,0,0)',
        'width:0%;height:0%;overflow:hidden',
        'max-width:0;max-height:0;overflow:hidden',
        'position:absolute;left:-99999px',
        'text-indent:-99999px;overflow:hidden;white-space:nowrap',
        'clip:rect(0, 0, 0, 0)',
    ]
    equivalent_results = [
        visible_html_text(
            f'<p style="{style}">EQUIVALENT-HIDDEN</p>',
            fail_closed=True,
        )
        for style in hidden_equivalents
    ]
    check("visibility parser recognizes equivalent hidden CSS values",
          all("EQUIVALENT-HIDDEN" not in text for text in equivalent_results),
          str(equivalent_results))

    ordinary_layout_text = visible_html_text(
        '<p style="position:absolute;top:20px;left:20px">ABSOLUTE-VISIBLE</p>'
        '<p style="transform:translateX(10px)">TRANSLATED-VISIBLE</p>'
        '<p style="scale:.95">SCALED-VISIBLE</p>'
        '<p style="backdrop-filter:blur(8px)">FILTERED-VISIBLE</p>'
        '<p style="margin-top:-1px">MARGIN-VISIBLE</p>'
        '<p style="text-indent:1em">INDENTED-VISIBLE</p>',
        fail_closed=True,
    )
    check("ordinary positioned and transformed layouts remain visible",
          all(marker in ordinary_layout_text for marker in (
              "ABSOLUTE-VISIBLE", "TRANSLATED-VISIBLE", "SCALED-VISIBLE",
              "FILTERED-VISIBLE", "MARGIN-VISIBLE", "INDENTED-VISIBLE",
          )),
          repr(ordinary_layout_text))

    ambiguous_text, ambiguous_state = visible_html_evidence(
        '<p style="font-size:calc(1px - 1px)">AMBIGUOUS-VISIBILITY</p>',
        fail_closed=True,
    )
    check("unresolved functional visibility is excluded and marked ambiguous",
          ambiguous_state and "AMBIGUOUS-VISIBILITY" not in ambiguous_text,
          f"ambiguous={ambiguous_state} text={ambiguous_text!r}")

    non_rendered_html = visible_html_text(
        '<svg><title>SVG-TITLE</title><desc>SVG-DESC</desc></svg>'
        '<svg><defs><text>SVG-DEFS</text></defs>'
        '<symbol><text>SVG-SYMBOL</text></symbol>'
        '<metadata>SVG-METADATA</metadata>'
        '<clipPath><text>SVG-CLIP</text></clipPath>'
        '<mask><text>SVG-MASK</text></mask>'
        '<pattern><text>SVG-PATTERN</text></pattern>'
        '<text>SVG-RENDERED</text></svg>'
        '<noembed>NOEMBED-TEXT</noembed>'
        '<noframes>NOFRAMES-TEXT</noframes>'
        '<datalist><option>DATALIST-OPTION</option></datalist>'
        '<ruby>base<rp>RUBY-FALLBACK</rp><rt>annotation</rt></ruby>'
        '<p>RENDERED-TEXT</p>',
        fail_closed=True,
    )
    check("visible text skips non-rendered metadata and fallback containers",
          all(marker not in non_rendered_html for marker in (
              "SVG-TITLE", "SVG-DESC", "SVG-DEFS", "SVG-SYMBOL",
              "SVG-METADATA", "SVG-CLIP", "SVG-MASK", "SVG-PATTERN",
              "NOEMBED-TEXT", "NOFRAMES-TEXT", "DATALIST-OPTION",
              "RUBY-FALLBACK",
          ))
          and "SVG-RENDERED" not in non_rendered_html
          and "RENDERED-TEXT" in non_rendered_html,
          repr(non_rendered_html))

    hidden_svg_text = visible_html_text(
        '<svg><text display="none">DISPLAY-SECRET</text>'
        '<text visibility="hidden">VISIBILITY-SECRET</text>'
        '<text opacity="0">OPACITY-SECRET</text>'
        '<text>SVG-VISIBLE</text></svg>',
        fail_closed=True,
    )
    check("visible text respects SVG presentation attributes",
          all(marker not in hidden_svg_text for marker in (
              "DISPLAY-SECRET", "VISIBILITY-SECRET", "OPACITY-SECRET",
          ))
          and "SVG-VISIBLE" not in hidden_svg_text,
          repr(hidden_svg_text))

    off_viewport_svg_text = visible_html_text(
        '<svg viewBox="0 0 100 100">'
        '<text x="-99999" y="20">OFF-LEFT</text>'
        '<text x="10000" y="20">OFF-RIGHT</text>'
        '<text x="101" y="20">JUST-OFF-RIGHT</text>'
        '<text x="-99" y="20">JUST-OFF-LEFT</text>'
        '<text x="101%" y="20">PERCENT-OFF-RIGHT</text>'
        '<text x="99" y="20" dx="10">DELTA-OFF-RIGHT</text>'
        '<svg x="101" viewBox="0 0 10 10"><text x="0" y="5">NESTED-OFF</text></svg>'
        '<text x="20" y="20">SVG-IN-VIEW</text></svg>',
        fail_closed=True,
    )
    check("visible text rejects SVG coordinates outside the viewport",
          "OFF-LEFT" not in off_viewport_svg_text
          and "OFF-RIGHT" not in off_viewport_svg_text
          and "JUST-OFF-RIGHT" not in off_viewport_svg_text
          and "JUST-OFF-LEFT" not in off_viewport_svg_text
          and "PERCENT-OFF-RIGHT" not in off_viewport_svg_text
          and "DELTA-OFF-RIGHT" not in off_viewport_svg_text
          and "NESTED-OFF" not in off_viewport_svg_text
          and "SVG-IN-VIEW" not in off_viewport_svg_text,
          repr(off_viewport_svg_text))

    malformed_table = (
        '<div hidden><table></div>MALFORMED-SECRET</table></div>'
        '<p>MALFORMED-VISIBLE</p>'
    )
    malformed_coverage_text = visible_html_text(malformed_table, fail_closed=True)
    malformed_residue_text = visible_html_text(malformed_table)
    check("crossed HTML closes split coverage and residue conservatively",
          "MALFORMED-SECRET" not in malformed_coverage_text
          and "MALFORMED-SECRET" in malformed_residue_text,
          f"coverage={malformed_coverage_text!r} residue={malformed_residue_text!r}")

    optional_end_html = visible_html_text(
        '<p>PARAGRAPH-FIRST<div>PARAGRAPH-SECOND</div><p>PARAGRAPH-THIRD'
        '<ul><li>LIST-FIRST<li>LIST-SECOND</ul>'
        '<table><tr><td>CELL-FIRST<td>CELL-SECOND</tr></table>',
        fail_closed=True,
    )
    check("standard optional HTML end tags preserve visible content",
          all(marker in optional_end_html for marker in (
              "PARAGRAPH-FIRST", "PARAGRAPH-SECOND", "PARAGRAPH-THIRD",
              "LIST-FIRST", "LIST-SECOND", "CELL-FIRST", "CELL-SECOND",
          )),
          repr(optional_end_html))

    self_closing_svg_text, self_closing_svg_ambiguous = visible_html_evidence(
        '<svg viewBox="0 0 100 100"><path d="M0 0L10 10" /></svg>'
        '<p>VISIBLE-AFTER-SVG</p>',
        fail_closed=True,
    )
    check("SVG foreign-content self-closing tags close without tainting HTML",
          self_closing_svg_text.strip() == "VISIBLE-AFTER-SVG"
          and not self_closing_svg_ambiguous,
          f"text={self_closing_svg_text!r} "
          f"ambiguous={self_closing_svg_ambiguous}")


def test_visibility_resolves_document_custom_properties() -> None:
    """Resolve only unconditional custom properties inherited from the root."""
    from checks import visible_html_evidence
    from content import html_resource_evidence

    visible_text, visible_ambiguous = visible_html_evidence(
        "<style>:root { --ink: #504e49 } body { color: var(--ink) }</style>"
        "<body>VISIBLE</body>",
        fail_closed=True,
    )
    check("document custom property makes body text deterministic",
          "VISIBLE" in visible_text and not visible_ambiguous,
          f"text={visible_text!r} ambiguous={visible_ambiguous}")

    template_results = []
    for path in sorted(TEMPLATES.glob("*.html")):
        raw = path.read_text(encoding="utf-8")
        text, ambiguous = visible_html_evidence(raw, fail_closed=True)
        template_results.append((path.name, bool(text.strip()), ambiguous, "<svg" in raw.lower()))
    check("all shipped HTML templates expose visible text under fail-closed checks",
          bool(template_results) and all(result[1] for result in template_results),
          str([result for result in template_results if not result[1]]))
    check("templates without SVG have deterministic visible text",
          all(ambiguous is False for _, _, ambiguous, has_svg in template_results
              if not has_svg),
          str([result for result in template_results if not result[3] and result[2]]))

    ambiguous_cases = [
        '<style>:root{--ink:#000}.dark{--ink:transparent}p{color:var(--ink)}</style>'
        '<div class="dark"><p>SECRET</p></div>',
        '<style>:root{--ink:#000}@media print{:root{--ink:transparent}}'
        'p{color:var(--ink)}</style><p>SECRET</p>',
        '<style>@property --ink{syntax:"<color>";inherits:false;initial-value:transparent}'
        ':root{--ink:#000}p{color:var(--ink)}</style><p>SECRET</p>',
        '<style>:root{--ink:#000}p{color:var(--ink)}</style>'
        '<p style="--ink:transparent">SECRET</p>',
        '<style>:root{--ink:#000}p{color:var(--ink)}</style>'
        '<p style=--ink:transparent>SECRET</p>',
        '<style>:root{--ink:#000}p{color:var(--ink)}</style>'
        "<p style='--ink:transparent'>SECRET</p>",
        '<style>:root{--ink:#000}p{color:var(--ink)}</style>'
        '<p style="--ink:trans&#112;arent">SECRET</p>',
    ]
    ambiguous_results = [
        visible_html_evidence(raw, fail_closed=True) for raw in ambiguous_cases
    ]
    check("conflicting or registered custom properties remain fail-closed",
          all("SECRET" not in text and ambiguous
              for text, ambiguous in ambiguous_results),
          repr(ambiguous_results))

    scoped_cases = [
        '<style>.theme{--d:block}p{display:var(--d,none)}</style>'
        '<div class="theme"></div><p>SECRET</p>',
        '<style>@media screen{:root{--d:block}}p{display:var(--d,none)}</style>'
        '<p>SECRET</p>',
        '<style>p{display:var(--d,none)}</style>'
        '<div style="--d:block"></div><p>SECRET</p>',
        '<style>.noop{--payload:"x; --ink:#000"}'
        'p{color:var(--ink,transparent)}</style><p>SECRET</p>',
        '<style>:root{--d:block}.hide{--junk:{x};--d:none}'
        'p{display:var(--d)}</style><p class="hide">SECRET</p>',
        '<style>:root{--INK:#000}p{color:var(--ink,transparent)}</style>'
        '<p>SECRET</p>',
    ]
    scoped_results = [
        visible_html_evidence(raw, fail_closed=True) for raw in scoped_cases
    ]
    check("scoped and malformed custom properties cannot expose hidden text",
          all("SECRET" not in text for text, _ in scoped_results),
          repr(scoped_results))

    scoped_assets, _ = html_resource_evidence(
        '<style>.theme{--d:block}img{display:var(--d,none)}</style>'
        '<div class="theme"></div><img src="required.svg">'
    )
    check("scoped custom properties cannot expose hidden resources",
          "required.svg" not in scoped_assets, repr(scoped_assets))

    hidden_cases = [
        '<style>:root{--ink:transparent}p{color:var(--ink)}</style><p>SECRET</p>',
        '<style>:root{--d:none}p{display:var(--d, block)}</style><p>SECRET</p>',
        '<p style=\'display:none;--x:";display:block"\'>SECRET</p>',
        '<p style="--HIDE:none;--hide:block;display:var(--HIDE)">SECRET</p>',
    ]
    hidden_results = [
        visible_html_evidence(raw, fail_closed=True) for raw in hidden_cases
    ]
    check("resolved hiding custom properties exclude their text deterministically",
          all("SECRET" not in text and not ambiguous
              for text, ambiguous in hidden_results),
          repr(hidden_results))

    benign_cases = [
        '<style>:root{--ink:#000}html{--ink:#000}p{color:var(--ink)}</style>'
        '<p>SHOWN</p>',
        '<style>:root{--base:#111;--ink:var(--base)}p{color:var(--ink)}</style>'
        '<p>SHOWN</p>',
        '<style>:root{--ink:#111}</style><p style="color:var(--ink)">SHOWN</p>',
    ]
    benign_results = [
        visible_html_evidence(raw, fail_closed=True) for raw in benign_cases
    ]
    check("identical and nested custom properties remain visible",
          all("SHOWN" in text and not ambiguous
              for text, ambiguous in benign_results),
          repr(benign_results))


def test_coverage_checks_asset_attributes() -> None:
    from checks import visible_html_text
    from content import (
        coverage_issues,
        html_resource_attributes,
        html_resource_evidence,
    )

    raw = (
        '<img src="./images/product-shot.png" alt="Product">'
        '<img src="images/product-shot@2x.webp" alt="Product at high density">'
        '<template><img src="hidden-shot.png"></template>'
        '<a href="linked-only.png">not embedded</a>'
    )
    attrs = html_resource_attributes(raw)
    present, checked, _ = coverage_issues(
        {"image": "product-shot.png", "images": ["product-shot@2x.webp"]}, "", attrs
    )
    missing, _, _ = coverage_issues({"image": "missing-shot.png"}, "", attrs)
    check("coverage accepts image paths present in src and srcset",
          present == [] and checked == 2, f"issues={present} attrs={attrs}")

    hidden_svg_attrs = html_resource_attributes(
        '<svg><defs><image href="hidden-def.png"></image></defs>'
        '<symbol><image href="hidden-symbol.png"></image></symbol>'
        '<image x="0" y="0" width="10" height="10" '
        'href="visible-svg.png"></image></svg>'
    )
    check("asset coverage skips SVG definition resources",
          hidden_svg_attrs == {"visible-svg.png"}, repr(hidden_svg_attrs))

    hidden_asset_cases = [
        '<svg><image display="none" href="required.svg"></image></svg>',
        '<svg><image visibility="hidden" href="required.svg"></image></svg>',
        '<svg><image opacity="0" href="required.svg"></image></svg>',
        '<img style="width:0;height:0" src="required.svg">',
        '<img width="0" height="0" src="required.svg">',
        '<svg width="0" height="0"><image href="required.svg"></image></svg>',
        '<img style="position:absolute;left:-99999px" src="required.svg">',
        '<img style="transform:matrix(0,0,0,0,0,0)" src="required.svg">',
        '<img style="width:calc(0px);height:calc(0px)" src="required.svg">',
        '<svg viewBox="0 0 100 100"><image x="-99999" href="required.svg"></image></svg>',
        '<svg viewBox="0 0 100 100"><image x="10000" href="required.svg"></image></svg>',
        '<svg viewBox="0 0 100 100"><image x="101" y="0" width="10" height="10" href="required.svg"></image></svg>',
        '<svg viewBox="0 0 100 100"><image x="101%" y="0" width="10" height="10" href="required.svg"></image></svg>',
        '<svg viewBox="0 0 100 100"><svg x="101"><image x="0" y="0" width="10" height="10" href="required.svg"></image></svg></svg>',
        '<svg viewBox="0 0 100 100"><defs><clipPath id="empty"></clipPath></defs>'
        '<image x="0" y="0" width="20" height="20" '
        'clip-path="url(#empty)" href="required.svg"></image></svg>',
        '<svg viewBox="0 0 100 100"><defs><mask id="empty"></mask></defs>'
        '<image x="0" y="0" width="20" height="20" '
        'mask="url(#empty)" href="required.svg"></image></svg>',
        '<svg viewBox="0 0 100 100"><defs><filter id="empty"></filter></defs>'
        '<image x="0" y="0" width="20" height="20" '
        'filter="url(#empty)" href="required.svg"></image></svg>',
    ]
    check("asset coverage rejects non-rendered CSS and presentation forms",
          all(not html_resource_attributes(case) for case in hidden_asset_cases),
          str([html_resource_attributes(case) for case in hidden_asset_cases]))

    deterministic_attrs, responsive_ambiguous = html_resource_evidence(
        '<img src="required.svg">'
        '<img srcset="a.png 1x,b.png 2x">'
    )
    check("responsive ambiguity preserves unrelated deterministic resources",
          deterministic_attrs == {"required.svg"} and responsive_ambiguous,
          f"attrs={deterministic_attrs} ambiguous={responsive_ambiguous}")
    hidden_responsive_attrs, hidden_responsive_ambiguous = html_resource_evidence(
        '<div hidden><img srcset="a.png 1x,b.png 2x"></div>'
    )
    check("hidden responsive resources do not degrade asset evidence",
          hidden_responsive_attrs == set() and not hidden_responsive_ambiguous,
          f"attrs={hidden_responsive_attrs} "
          f"ambiguous={hidden_responsive_ambiguous}")
    svg_then_asset, svg_then_asset_ambiguous = html_resource_evidence(
        '<svg viewBox="0 0 100 100"><path d="M0 0L10 10" /></svg>'
        '<img src="required.svg">'
    )
    check("self-closing SVG graphics preserve following resource evidence",
          svg_then_asset == {"required.svg"} and not svg_then_asset_ambiguous,
          f"attrs={svg_then_asset} ambiguous={svg_then_asset_ambiguous}")
    check("coverage rejects omitted image assets",
          len(missing) == 1 and "missing-shot.png" in missing[0], str(missing))
    hidden, _, _ = coverage_issues(
        {"images": ["hidden-shot.png", "linked-only.png"]}, "", attrs
    )
    check("coverage ignores assets in templates and plain links",
          len(hidden) == 2, f"issues={hidden} attrs={attrs}")
    wrong_origin, _, _ = coverage_issues(
        ["https://brand.example/logo.svg"],
        "",
        html_resource_attributes('<img src="https://other.example/logo.svg">'),
        root_path="brief.required_assets",
        force_assets=True,
    )
    same_origin, _, _ = coverage_issues(
        ["https://brand.example/logo.svg?v=approved"],
        "",
        html_resource_attributes('<img src="https://brand.example/logo.svg?v=cache">'),
        root_path="brief.required_assets",
        force_assets=True,
    )
    check("required absolute assets cannot be impersonated by the same path on another host",
          len(wrong_origin) == 1, str(wrong_origin))
    check("required absolute assets tolerate cache-query changes on the same origin and path",
          same_origin == [], str(same_origin))

    local_absolute_remote_copy, _, _ = coverage_issues(
        ["/approved/brand/logo.svg"],
        "",
        html_resource_attributes(
            '<img src="https://attacker.example/approved/brand/logo.svg">'
        ),
        root_path="brief.required_assets",
        force_assets=True,
    )
    local_absolute_exact, _, _ = coverage_issues(
        ["/approved/brand/logo.svg"],
        "",
        html_resource_attributes('<img src="/approved/brand/logo.svg">'),
        root_path="brief.required_assets",
        force_assets=True,
    )
    check("required local absolute assets reject remote path impersonation",
          len(local_absolute_remote_copy) == 1 and local_absolute_exact == [],
          f"remote={local_absolute_remote_copy} exact={local_absolute_exact}")

    malformed_hidden_attrs = html_resource_attributes(
        '<div hidden><img></img><img src="hidden-after-void.svg"></div>'
        '<img hidden src="hidden-void.svg">'
        '<img src="visible.svg">'
    )
    check("resource parser keeps hidden scope across a void closing tag",
          malformed_hidden_attrs == {"visible.svg"},
          str(sorted(malformed_hidden_attrs)))

    self_closing_hidden_attrs = html_resource_attributes(
        '<div hidden/><img src="hidden-self-closing.svg"></div>'
        '<img src="visible-after-self-closing.svg">'
    )
    check("resource parser follows HTML semantics for non-void self-closing tags",
          self_closing_hidden_attrs == {"visible-after-self-closing.svg"},
          str(sorted(self_closing_hidden_attrs)))

    css_hidden_attrs = html_resource_attributes(
        '<style>.concealed img { display: none } '
        '.escaped { d\\69splay: n\\6f ne } '
        '[hidden] { display: none } '
        ':root { --fallback-display: none }</style>'
        '<div class="concealed"><img src="hidden-by-selector.svg"></div>'
        '<img style="display/**/: none" src="hidden-by-inline-comment.svg">'
        '<img class="escaped" src="hidden-by-css-escape.svg">'
        '<img hidden src="hidden-by-attribute.svg">'
        '<img src="visible-after-css.svg">'
    )
    check("resource parser fails closed on compound and comment-split hidden CSS",
          css_hidden_attrs == {"visible-after-css.svg"},
          str(sorted(css_hidden_attrs)))

    ambiguous_css_cases = [
        (
            '<style>div:not(.show) img { display: none }</style>'
            '<div><img src="hidden-by-not.svg"></div>',
            "hidden-by-not.svg",
        ),
        (
            '<style>[data-state^="hid"] { display: none }</style>'
            '<p data-state="hidden">HIDDEN-BY-ATTR-OPERATOR</p>',
            "HIDDEN-BY-ATTR-OPERATOR",
        ),
        (
            '<style>.marker + p { display: none }</style>'
            '<span class="marker"></span><p>HIDDEN-BY-SIBLING</p>',
            "HIDDEN-BY-SIBLING",
        ),
        (
            '<style>.hidden-by-var { --hide: none; display: var(--hide) }</style>'
            '<img class="hidden-by-var" src="hidden-by-var.svg">',
            "hidden-by-var.svg",
        ),
        (
            '<style>.h\\69 dden { visibility: collapse }</style>'
            '<img class="hidden" src="hidden-by-selector-escape.svg">',
            "hidden-by-selector-escape.svg",
        ),
        (
            '<link rel="style&#115;heet" '
            'href="data:text/css,.x%7Bdisplay%3Anone%7D">'
            '<img class="x" src="hidden-by-encoded-stylesheet.svg">',
            "hidden-by-encoded-stylesheet.svg",
        ),
        (
            '<style>@\\69mport url("data:text/css,.x%7Bdisplay%3Anone%7D")</style>'
            '<img class="x" src="hidden-by-escaped-import.svg">',
            "hidden-by-escaped-import.svg",
        ),
    ]
    ambiguous_results = [
        (
            marker,
            visible_html_text(raw, fail_closed=True),
            html_resource_attributes(raw),
        )
        for raw, marker in ambiguous_css_cases
    ]
    check("unsupported hiding CSS fails closed instead of partially matching",
          all(
              marker not in text and marker not in attrs
              for marker, text, attrs in ambiguous_results
          ),
          str(ambiguous_results))

    responsive_attrs = html_resource_attributes(
        '<picture>'
        '<source media="(min-width:99999px)" srcset="never-selected.svg">'
        '<img src="actual.svg" srcset="candidate-1.svg 1x, candidate-2.svg 2x">'
        '</picture>'
    )
    check("resource parser excludes unresolved responsive candidates",
          responsive_attrs == set(),
          str(sorted(responsive_attrs)))
    picture_fallback_attrs = html_resource_attributes(
        '<picture>'
        '<source media="(min-width:1px)" srcset="actual.svg">'
        '<img src="required-fallback.svg">'
        '</picture>'
    )
    bare_source_attrs = html_resource_attributes(
        '<source srcset="bare-unrendered.svg">'
    )
    check("picture fallbacks and bare sources cannot prove required assets",
          picture_fallback_attrs == set() and bare_source_attrs == set(),
          f"picture={sorted(picture_fallback_attrs)} bare={sorted(bare_source_attrs)}")

    remote_base, _, _ = coverage_issues(
        ["approved/logo.svg"],
        "",
        html_resource_attributes(
            '<base href="https://attacker.example/">'
            '<img src="approved/logo.svg">'
        ),
        root_path="brief.required_assets",
        force_assets=True,
    )
    check("required local assets reject a remote base URL",
          len(remote_base) == 1,
          str(remote_base))


def test_coverage_caps_adversarial_reports() -> None:
    from content import MAX_COVERAGE_ISSUES, MAX_COVERAGE_VALUES, coverage_issues

    missing, _, _ = coverage_issues({"values": list(range(1000))}, "")
    oversized, _, _ = coverage_issues({"values": ["present"] * (MAX_COVERAGE_VALUES + 1)}, "present")
    check("coverage caps missing-value reports",
          len(missing) == MAX_COVERAGE_ISSUES + 1
          and "issue limit" in missing[-1], f"issues={len(missing)}")
    check("coverage caps the number of atomic values",
          len(oversized) == 1 and "too many atomic values" in oversized[0], str(oversized[-2:]))


# --------------------------- MCP server ---------------------------

def test_mcp_server_stdio_protocol() -> None:
    """The server must speak newline-delimited JSON-RPC with nothing else on stdout."""
    script = REPO_ROOT / "scripts" / "mcp_server.py"
    msgs = [
        {"jsonrpc": "2.0", "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-03-26"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": None, "method": "ping"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "kami_templates", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "kami_doctor", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "nope", "arguments": {}}},
    ]
    stdin = "".join(json.dumps(m) + "\n" for m in msgs)
    result = subprocess.run(
        [sys.executable, str(script)],
        input=stdin, capture_output=True, text=True, cwd=REPO_ROOT, timeout=60,
    )
    try:
        replies = {m.get("id"): m for m in map(json.loads, result.stdout.strip().splitlines())}
    except json.JSONDecodeError:
        check("mcp server stdout is newline-delimited JSON", False, result.stdout[:200])
        return
    init = replies.get(1, {}).get("result", {})
    check("mcp initialize echoes protocol version and names the server",
          init.get("protocolVersion") == "2025-03-26"
          and init.get("serverInfo", {}).get("name") == "kami",
          json.dumps(init)[:200])
    tools = [t["name"] for t in replies.get(2, {}).get("result", {}).get("tools", [])]
    check("mcp tools/list exposes the five kami tools",
          tools == ["kami_templates", "kami_doctor", "kami_render", "kami_check", "kami_screenshot"],
          str(tools))
    body = replies.get(3, {}).get("result", {}).get("content", [{}])[0].get("text", "{}")
    payload = json.loads(body)
    check("mcp kami_templates returns registries and schema types",
          set(payload.get("document_templates", {})) == set(HTML_TEMPLATES)
          and set(payload.get("pptx_templates", {})) == {"slides", "slides-en"}
          and set(payload.get("marp_templates", {})) == set(MARP_TEMPLATES)
          and payload.get("content_schema_types"),
          body[:200])
    doctor_body = replies.get(4, {}).get("result", {}).get("content", [{}])[0].get("text", "{}")
    doctor = json.loads(doctor_body)
    check("mcp kami_doctor reports dependencies, fonts, and capabilities",
          isinstance(doctor.get("ok"), bool)
          and len(doctor.get("dependencies", [])) >= 3
          and len(doctor.get("fonts", [])) >= 3
          and "pdf_visual_review" in doctor.get("capabilities", {})
          and "strict_math" in doctor.get("capabilities", {}),
          doctor_body[:300])
    check("mcp unknown tool returns a JSON-RPC error",
          "error" in replies.get(5, {}), json.dumps(replies.get(5, {}))[:200])
    check("mcp explicit null id remains a request",
          replies.get(None, {}).get("result") == {}, str(replies.get(None)))
    check("mcp notifications produced no reply", len(replies) == 6, str(sorted(
        ("null" if key is None else str(key)) for key in replies
    )))


def test_mcp_check_returns_stable_findings_and_coverage() -> None:
    from mcp_server import CHECK_REGISTRY, tool_check

    with tempfile.TemporaryDirectory() as d:
        clean = Path(d) / "clean.html"
        broken = Path(d) / "broken.html"
        math_broken = Path(d) / "math-broken.html"
        clean.write_text("<html><body><p>Ready</p></body></html>", encoding="utf-8")
        broken.write_text("<html><body><p>{{ missing }}</p></body></html>", encoding="utf-8")
        math_broken.write_text(
            r"<html><body><p>\(x^2\)</p></body></html>",
            encoding="utf-8",
        )
        invalid_content = Path(d) / "invalid-content.json"
        invalid_content.write_text(
            json.dumps({"type": "letter", "lang": "en", "content": {}}),
            encoding="utf-8",
        )
        valid_content = Path(d) / "valid-content.json"
        valid_content.write_text(json.dumps({
            "type": "letter",
            "lang": "en",
            "content": {
                "sender": "Ada Lovelace, London",
                "date": "2026-07-13",
                "recipient": "Charles Babbage",
                "salutation": "Dear Charles,",
                "paragraphs": [
                    "I write to state my purpose in one sentence: the engine deserves a program of its own.",
                    "The evidence sits in the notes: fifty operations, one loop, and a table the machine can follow.",
                    "My ask is specific: review the table this month so we can test it on the mill.",
                ],
                "signoff": "Sincerely,",
                "signature": "Ada",
            },
        }), encoding="utf-8")
        clean_result = tool_check({"path": str(clean)})
        broken_result = tool_check({"path": str(broken)})
        math_broken_result = tool_check({"path": str(math_broken)})
        invalid_content_result = tool_check({
            "path": str(clean), "content": str(invalid_content),
        })
        missing_coverage_result = tool_check({
            "path": str(clean), "content": str(valid_content),
        })

    check("MCP check registry carries unique stable rule IDs",
          CHECK_REGISTRY and clean_result["ruleset_version"] == 3
          and len(CHECK_REGISTRY) == len(set(CHECK_REGISTRY))
          and all({"scope", "severity", "required_engine", "explanation"} <= set(rule)
                  for rule in CHECK_REGISTRY.values()),
          str(CHECK_REGISTRY))
    check("MCP clean check returns coverage without findings",
          clean_result["ok"] is True
          and clean_result["degraded"] is False
          and clean_result["findings"] == []
          and [item["id"] for item in clean_result["coverage"]]
          == ["html.placeholders", "html.math", "html.markdown-residue"]
          and clean_result["report"],
          json.dumps(clean_result)[:500])
    check("MCP failed check returns a stable finding and legacy report",
          broken_result["ok"] is False
          and broken_result["findings"][0]["id"] == "html.placeholders"
          and broken_result["findings"][0]["status"] == "failed"
          and "placeholder" in broken_result["report"].lower(),
          json.dumps(broken_result)[:500])
    check("MCP HTML check rejects unrendered standard LaTeX",
          math_broken_result["ok"] is False
          and [finding["id"] for finding in math_broken_result["findings"]]
          == ["html.math"],
          json.dumps(math_broken_result)[:500])
    invalid_ids = [item["id"] for item in invalid_content_result["findings"]]
    invalid_coverage = {
        item["id"]: item for item in invalid_content_result["coverage"]
    }
    check("MCP labels invalid content IR as contract failure before coverage",
          "content.contract" in invalid_ids
          and "content.coverage" not in invalid_ids
          and invalid_coverage["content.coverage"]["status"] == "not_run"
          and invalid_coverage["content.coverage"]["blocked_by"]
          == "content.contract",
          json.dumps(invalid_content_result)[:800])
    missing_ids = [item["id"] for item in missing_coverage_result["findings"]]
    missing_statuses = {
        item["id"]: item["status"]
        for item in missing_coverage_result["coverage"]
    }
    check("MCP runs coverage once after a valid content contract",
          missing_ids == ["content.coverage"]
          and missing_statuses["content.contract"] == "passed"
          and missing_statuses["content.coverage"] == "failed",
          json.dumps(missing_coverage_result)[:800])


def test_mcp_server_rejects_bad_frames_without_exiting() -> None:
    """Wrong-shaped JSON-RPC frames return errors and do not kill the server."""
    script = REPO_ROOT / "scripts" / "mcp_server.py"
    msgs = [
        [],
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": "bad"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "kami_templates", "arguments": ["bad"]}},
        {"jsonrpc": "2.0", "id": 3, "method": "ping"},
    ]
    result = subprocess.run(
        [sys.executable, str(script)],
        input="".join(json.dumps(m) + "\n" for m in msgs),
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=60,
    )
    replies = [json.loads(line) for line in result.stdout.strip().splitlines()]
    by_id = {reply.get("id"): reply for reply in replies}
    check("mcp malformed frames keep the process alive",
          result.returncode == 0 and len(replies) == 4 and "result" in by_id.get(3, {}),
          (result.stdout + result.stderr)[:400])
    check("mcp wrong params and arguments return invalid-params errors",
          by_id.get(1, {}).get("error", {}).get("code") == -32602
          and by_id.get(2, {}).get("error", {}).get("code") == -32602,
          result.stdout[:400])


def test_mcp_all_tools_succeed_over_stdio() -> None:
    """Exercise render, check, and screenshot through the installed protocol path."""
    try:
        from optional_deps import require_pypdf_reader, require_weasyprint_html
        require_weasyprint_html()
        require_pypdf_reader()
        require_pymupdf()
    except MissingDepError as exc:
        skip("MCP all-tools stdio success path", str(exc), ci_required=True)
        return

    script = REPO_ROOT / "scripts" / "mcp_server.py"
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        html = root / "source.html"
        pdf = root / "output.pdf"
        html.write_text(
            "<!doctype html><html><head><style>"
            "@page{size:A4;margin:20mm}body{font-family:serif}"
            "</style></head><body><h1>Kami MCP smoke</h1><p>Rendered.</p></body></html>",
            encoding="utf-8",
        )
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "kami_render", "arguments": {
                 "html": str(html), "out": str(pdf)}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "kami_check", "arguments": {"path": str(html)}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "kami_screenshot", "arguments": {"pdf": str(pdf)}}},
        ]
        result = subprocess.run(
            [sys.executable, str(script)],
            input="".join(json.dumps(m) + "\n" for m in msgs),
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=120,
        )
        try:
            replies = {m.get("id"): m for m in map(json.loads, result.stdout.strip().splitlines())}
            payloads = {
                reply_id: json.loads(
                    replies[reply_id]["result"]["content"][0]["text"]
                )
                for reply_id in (2, 3, 4)
            }
        except (KeyError, json.JSONDecodeError) as exc:
            check("MCP all-tools success path returns JSON results", False,
                  f"{exc}: {(result.stdout + result.stderr)[:500]}")
            return

        render_result = payloads[2]
        check_result = payloads[3]
        screenshot_result = payloads[4]
        check("MCP render succeeds over stdio",
              result.returncode == 0 and render_result.get("pages") == 1 and pdf.is_file(),
              json.dumps(render_result)[:300])
        check("MCP check succeeds over stdio",
              check_result.get("ok") is True and check_result.get("exit_code") == 0,
              json.dumps(check_result)[:300])
        page_paths = [Path(path) for path in screenshot_result.get("pages", [])]
        check("MCP screenshot returns evidence without a false perceptual verdict",
              "ok" not in screenshot_result
              and screenshot_result.get("rasterized") is True
              and screenshot_result.get("review_pending") is True
              and screenshot_result.get("font_check", {}).get("ok") is True
              and len(page_paths) == 1 and all(path.is_file() for path in page_paths),
              json.dumps(screenshot_result)[:500])


def test_mcp_render_guards_source_and_output_types() -> None:
    from mcp_server import tool_render

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        html = root / "source.html"
        html.write_text("<html><body>safe source</body></html>", encoding="utf-8")
        original = html.read_bytes()
        hardlink = root / "hardlink.pdf"
        hardlink.hardlink_to(html)
        victim = root / "victim.txt"
        victim.write_bytes(b"do-not-overwrite")
        symlink = root / "symlink.pdf"
        symlink.symlink_to(victim)
        rejected = 0
        for out in (html, hardlink, symlink, root / "not-pdf.txt"):
            try:
                tool_render({"html": str(html), "out": str(out)})
            except ValueError:
                rejected += 1
        check("mcp render rejects source aliases and non-PDF outputs",
              rejected == 4 and html.read_bytes() == original
              and victim.read_bytes() == b"do-not-overwrite",
              f"rejected={rejected} source_changed={html.read_bytes() != original}")


def test_visual_rejects_empty_pdf_and_bad_dpi() -> None:
    try:
        from pypdf import PdfWriter
        from visual import render_pages
    except ImportError:
        skip("visual empty-PDF guard", "pypdf unavailable", ci_required=True)
        return

    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d) / "empty.pdf"
        evidence = Path(d) / "empty-visual"
        evidence.mkdir()
        old_page = evidence / "page-01.png"
        old_page.write_bytes(b"last-good-run")
        writer = PdfWriter()
        writer.write(str(pdf))
        errors = 0
        for dpi in (1, -1, 301):
            try:
                render_pages(pdf, dpi=dpi)
            except ValueError:
                errors += 1
        try:
            render_pages(pdf, dpi=110)
        except ValueError as exc:
            empty_error = "no pages" in str(exc)
        else:
            empty_error = False
        check("visual rejects empty PDFs and out-of-range DPI",
              empty_error and errors == 3,
              f"empty_error={empty_error} dpi_errors={errors}")
        check("failed visual render preserves last good evidence",
              old_page.read_bytes() == b"last-good-run")

        symlink_target = Path(d) / "elsewhere"
        symlink_target.mkdir()
        symlink_output = Path(d) / "linked-visual"
        symlink_output.symlink_to(symlink_target, target_is_directory=True)
        try:
            render_pages(pdf, out_dir=symlink_output, dpi=110)
        except ValueError as exc:
            symlink_rejected = "symbolic link" in str(exc)
        else:
            symlink_rejected = False
        check("visual rejects a symbolic-link evidence directory", symlink_rejected)

        huge_pdf = Path(d) / "huge.pdf"
        huge_writer = PdfWriter()
        huge_writer.add_blank_page(width=5000, height=5000)
        huge_writer.write(str(huge_pdf))
        try:
            render_pages(huge_pdf, dpi=300)
        except ValueError as exc:
            huge_rejected = "pixels" in str(exc)
        else:
            huge_rejected = False
        check("visual rejects an oversized raster page before rendering", huge_rejected)


def test_document_checks_reject_empty_pdf() -> None:
    """A readable PDF with zero pages is not a successfully checked artifact."""
    try:
        from pypdf import PdfWriter
        from checks import check_density, check_orphans
        from mcp_server import tool_check
    except ImportError:
        skip("empty-PDF document checks", "render dependencies unavailable", ci_required=True)
        return

    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d) / "empty.pdf"
        PdfWriter().write(str(pdf))
        results = [
            silently(check_markdown_residue, [str(pdf)]),
            silently(check_orphans, [str(pdf)]),
            silently(check_density, [str(pdf)]),
        ]
        mcp_result = tool_check({"path": str(pdf)})
        check("PDF checks reject zero-page artifacts",
              results == [2, 2, 2], str(results))
        check("MCP check rejects zero-page artifacts",
              not mcp_result["ok"]
              and all(rule["status"] == "degraded" for rule in mcp_result["coverage"]),
              str(mcp_result))


def _test_functions():
    tests = []
    for name, func in globals().items():
        if not name.startswith("test_") or not callable(func):
            continue
        if getattr(func, "__module__", None) != __name__:
            continue
        code = getattr(func, "__code__", None)
        if code is None:
            continue
        tests.append((code.co_firstlineno, name, func))
    return [(name, func) for _, name, func in sorted(tests)]


def main() -> int:
    for name, func in _test_functions():
        signature = inspect.signature(func)
        if signature.parameters:
            params = ", ".join(signature.parameters)
            check(f"{name} has no parameters", False, f"parameters: {params}")
            continue
        func()
    print()
    print(f"Passed: {_PASS} | Skipped: {_SKIP} | Failed: {_FAIL}")
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
