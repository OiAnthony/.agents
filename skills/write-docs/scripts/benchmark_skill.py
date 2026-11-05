#!/usr/bin/env python3
"""Deterministic quality benchmark for the write-docs skill.

This benchmark checks observable skill contracts rather than pinning prose to a
specific implementation. It also runs the scanner's fixed regression corpus so
an iteration cannot improve the rubric by breaking the only executable tool.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = ROOT / "skills" / "write-docs"
SKILL = SKILL_DIR / "SKILL.md"
REFERENCES = SKILL_DIR / "references"
ASSETS = SKILL_DIR / "assets"
SCANNER = SKILL_DIR / "scripts" / "scan_ai_taste.py"
PATTERNS = SKILL_DIR / "scripts" / "patterns.yaml"
SAMPLES = SKILL_DIR / "scripts" / "samples"

ROUTES = {
    "tech-blog": ("博客", "技术分享", "工程博客", "tech-blog.md"),
    "design-doc": ("技术方案", "设计文档", "RFC", "design-doc.md"),
    "api-doc": ("接口文档", "API 文档", "OpenAPI", "api-doc.md"),
    "schema-doc": ("表结构", "数据字典", "迁移", "schema-doc.md"),
    "howto": ("使用指南", "教程", "README", "howto.md"),
    "everyday": ("PR 描述", "周报", "事故通报", "everyday.md"),
    "de-ai": ("去AI味", "模仿", "AI 腔", "de-ai.md"),
}
EXPECTED_REFERENCES = (
    "shared.md",
    "tech-blog.md",
    "design-doc.md",
    "api-doc.md",
    "schema-doc.md",
    "howto.md",
    "everyday.md",
    "de-ai.md",
    "benchmarks.md",
)
EXPECTED_ASSETS = (
    "tech-blog-skeleton.md",
    "api-endpoint.md",
    "schema-table.md",
    "runbook.md",
    "pr-description.md",
    "style-contract.md",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def has_any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms)


def route_rows(text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in text.splitlines():
        if "|" not in line:
            continue
        for route in ROUTES:
            if f"references/{route}.md" not in line:
                continue
            if re.search(rf"(?<![\w-]){re.escape(route)}(?![\w-])", line):
                rows[route] = line
    return rows


def run_scanner(sample: str, expected: int) -> bool:
    proc = subprocess.run(
        [sys.executable, str(SCANNER), str(SAMPLES / sample), "--profile", "all"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return proc.returncode == expected


def main() -> int:
    errors: list[str] = []
    if not SKILL.is_file():
        errors.append("missing SKILL.md")
    if not SCANNER.is_file() or not PATTERNS.is_file():
        errors.append("missing executable scanner inputs")
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 2

    skill = read(SKILL)
    refs = {name: read(REFERENCES / name) for name in EXPECTED_REFERENCES if (REFERENCES / name).is_file()}
    assets = {name: read(ASSETS / name) for name in EXPECTED_ASSETS if (ASSETS / name).is_file()}
    rows = route_rows(skill)

    # Hard checks protect the benchmark from becoming green while its workload
    # no longer runs. The quality score itself remains continuous.
    expected_samples = {
        "ai_zh.md": 1,
        "ai_en.md": 1,
        "gpt_deepseek_zh.md": 1,
        "clean_zh.md": 0,
    }
    scanner_passes = sum(run_scanner(name, code) for name, code in expected_samples.items())
    if scanner_passes != len(expected_samples):
        errors.append(f"scanner regression: {scanner_passes}/{len(expected_samples)}")

    route_passes = 0
    for route, signals in ROUTES.items():
        row = rows.get(route, "")
        target = REFERENCES / signals[-1]
        if row and target.is_file() and sum(signal in row for signal in signals[:-1]) >= 2:
            route_passes += 1
    if route_passes != len(ROUTES):
        errors.append(f"route contract: {route_passes}/{len(ROUTES)}")

    reference_passes = sum(
        (REFERENCES / name).is_file()
        and bool(re.search(r"^#{1,3} ", refs.get(name, ""), re.MULTILINE))
        and ("检查清单" in refs.get(name, "") or "checklist" in refs.get(name, "").lower())
        for name in EXPECTED_REFERENCES
    )
    asset_passes = sum((ASSETS / name).is_file() and bool(assets.get(name, "").strip()) for name in EXPECTED_ASSETS)

    progressive_terms = (
        ("contract", ("合同", "读者", "场景")),
        ("evidence", ("证据", "数字", "来源")),
        ("outline", ("提纲", "标题", "结论")),
        ("self_check", ("自检", "检查清单")),
        ("fact_check", ("事实核对", "事实一致")),
        ("delivery", ("交付", "待补", "假设")),
    )
    progressive_passes = sum(has_any(skill, terms) for _, terms in progressive_terms)

    benchmark_terms = (
        ("problem", ("缺口", "问题")),
        ("failure", ("失败", "不够")),
        ("decision", ("决定", "设计")),
        ("evidence", ("证据", "数字")),
        ("ablation", ("消融", "变体")),
        ("cost", ("成本", "token")),
        ("negative", ("负面", "中性结果")),
        ("limits", ("局限", "未知")),
        ("open_questions", ("开放问题", "未解决")),
        ("methodology", ("方法论", "负载")),
    )
    benchmark_text = refs.get("benchmarks.md", "") + refs.get("tech-blog.md", "")
    benchmark_passes = sum(has_any(benchmark_text, terms) for _, terms in benchmark_terms)

    deai_terms = (
        ("scanner", ("scan_ai_taste.py", "扫描")),
        ("high", ("HIGH", "high")),
        ("medium", ("MEDIUM", "medium")),
        ("bounded_loop", ("最多三轮", "最多 3 轮", "三轮")),
        ("fact_preservation", ("事实", "数字", "链接")),
    )
    deai_text = skill + refs.get("de-ai.md", "")
    deai_passes = sum(has_any(deai_text, terms) for _, terms in deai_terms)

    local_links = re.findall(r"`((?:references|assets)/[^`\s]+\.md)`", skill)
    resolved_links = sum((SKILL_DIR / link).is_file() for link in local_links)
    link_integrity = 1.0 if local_links and resolved_links == len(local_links) else 0.0
    pattern_integrity = 1.0 if "rules:" in read(PATTERNS) and "version:" in read(PATTERNS) else 0.0
    script_docs = read(SKILL_DIR / "scripts" / "README.md") if (SKILL_DIR / "scripts" / "README.md").is_file() else ""
    maintainability = sum(
        has_any(script_docs, terms)
        for terms in (("期望 1", "expected"), ("期望 0", "expected"), ("退出码", "exit code"), ("零依赖", "standard library"))
    )

    # Weighted score: routeability and executable behavior dominate prose cues.
    score = (
        20.0 * route_passes / len(ROUTES)
        + 15.0 * reference_passes / len(EXPECTED_REFERENCES)
        + 5.0 * asset_passes / len(EXPECTED_ASSETS)
        + 15.0 * progressive_passes / len(progressive_terms)
        + 20.0 * benchmark_passes / len(benchmark_terms)
        + 15.0 * deai_passes / len(deai_terms)
        + 5.0 * link_integrity
        + 3.0 * pattern_integrity
        + 2.0 * maintainability / 4.0
    )

    print(f"METRIC skill_quality={score:.2f}")
    print(f"METRIC route_coverage={route_passes}/{len(ROUTES)}")
    print(f"METRIC reference_integrity={reference_passes}/{len(EXPECTED_REFERENCES)}")
    print(f"METRIC asset_integrity={asset_passes}/{len(EXPECTED_ASSETS)}")
    print(f"METRIC benchmark_signals={benchmark_passes}/{len(benchmark_terms)}")
    print(f"METRIC scanner_regression={scanner_passes}/{len(expected_samples)}")
    print(f"METRIC local_link_integrity={resolved_links}/{len(local_links)}")

    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
