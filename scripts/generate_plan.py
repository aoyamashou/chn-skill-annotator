#!/usr/bin/env python3
"""Generate a plan template for pending Chinese description annotations."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
DEFAULT_SKILLS_DIR = "skills"
SEPARATOR = "｜"
PLACEHOLDER_PATTERNS = (
    re.compile(r"replace with description", re.IGNORECASE),
    re.compile(r"\[todo:.*description", re.IGNORECASE),
    re.compile(r"todo", re.IGNORECASE),
)
QUALITY_HINTS = [
    ("official documentation", "官方文档"),
    ("official docs", "官方文档"),
    ("official", "官方"),
    ("up-to-date", "最新"),
    ("latest", "最新"),
    ("real browser", "真实浏览器"),
    ("interactive", "交互式"),
    ("iterative", "迭代式"),
    ("persistent", "持久化"),
    ("private repos", "私有仓库"),
    ("private repo", "私有仓库"),
    ("github repo path", "仓库路径"),
    ("github repo", "GitHub 仓库"),
    ("curated list", "精选列表"),
    ("render/validation", "渲染校验"),
    ("validation", "校验"),
    ("formula-aware", "公式感知"),
    ("visual review", "可视化检查"),
    ("cached recalculation", "缓存重算"),
]
SUMMARY_PATTERNS = [
    (
        re.compile(r"openai.+official documentation|official documentation.+openai", re.IGNORECASE),
        "查阅 OpenAI 官方最新文档",
    ),
    (
        re.compile(r"creating effective skills|create a new skill|update an existing skill", re.IGNORECASE),
        "创建和优化 Codex 技能",
    ),
    (
        re.compile(r"install codex skills.+curated list|install codex skills.+github repo", re.IGNORECASE),
        "从列表或仓库安装 Codex 技能",
    ),
    (
        re.compile(r"deploy.+cloudflare|cloudflare.+deploy|cloudflare using workers, pages", re.IGNORECASE),
        "部署应用到 Cloudflare",
    ),
    (
        re.compile(r"automating a real browser|real browser.+playwright|navigation, form filling, snapshots", re.IGNORECASE),
        "通过 Playwright 执行真实浏览器自动化",
    ),
    (
        re.compile(r"persistent browser.+iterative ui debugging|electron interaction.+js_repl", re.IGNORECASE),
        "通过 js_repl 持续交互调试浏览器",
    ),
    (
        re.compile(r"presentation slide decks|pptx.+pptxgenjs|powerpoint deck", re.IGNORECASE),
        "创建和编辑 PPTX 演示文稿",
    ),
    (
        re.compile(r"spreadsheets?.+formula-aware|cached recalculation|visual review", re.IGNORECASE),
        "创建编辑并分析电子表格",
    ),
]
PHRASE_MAP = [
    ("search and manage", "搜索和管理"),
    ("create, manage, and delete", "创建、管理和删除"),
    ("create and edit", "创建和编辑"),
    ("create, edit, and analyze", "创建、编辑和分析"),
    ("creation, editing, and analysis", "创建、编辑和分析"),
    ("creation and editing", "创建和编辑"),
    ("creating effective", "创建和优化"),
    ("create effective", "创建和优化"),
    ("creating", "创建"),
    ("read and update", "读取和更新"),
    ("fetch and read", "抓取和读取"),
    ("read, watch, and listen to", "读取、观看和收听"),
    ("find, organize, and manage", "查找、整理和管理"),
    ("search and install", "搜索并安装"),
    ("search, install, and manage", "搜索、安装和管理"),
    ("generate and edit", "生成和编辑"),
    ("install", "安装"),
    ("generate", "生成"),
    ("annotate", "补充注释"),
    ("deploy", "部署"),
    ("download", "下载"),
    ("manage", "管理"),
    ("react to", "回应"),
    ("switch into", "切换到"),
    ("delegate", "委托"),
    ("take", "生成"),
]
NOUN_MAP = [
    ("skill descriptions", "技能描述"),
    ("description fields", "描述字段"),
    ("skill metadata", "技能元数据"),
    ("codex skills", "Codex 技能"),
    ("applications and infrastructure", "应用和基础设施"),
    ("browser automation", "浏览器自动化"),
    ("real browser", "真实浏览器"),
    ("browser tools", "浏览器工具"),
    ("web pages, apis, and online content", "网页、API 和在线内容"),
    ("videos or audio", "视频或音频"),
    ("video/audio files", "视频音频文件"),
    ("voice messages", "语音消息"),
    ("jupyter notebook", "Jupyter Notebook"),
    ("notebook", "Notebook"),
    ("spreadsheet", "电子表格"),
    ("spreadsheets", "电子表格"),
    ("presentations", "演示文稿"),
    ("presentation", "演示文稿"),
    ("documents", "文档"),
    ("document", "文档"),
    ("pdf", "PDF"),
    ("files", "文件"),
    ("images", "图片"),
    ("image", "图片"),
    ("songs", "歌曲"),
    ("music", "音乐"),
    ("telegram", "Telegram"),
    ("discord", "Discord"),
    ("twitter/x links", "Twitter/X 链接"),
    ("threads", "聊天线程"),
    ("tasks", "任务"),
    ("scheduled tasks", "定时任务"),
    ("system information", "系统信息"),
    ("memory and conversation history", "记忆和历史对话"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a plan.json template for SKILL.md files that still need Chinese summaries."
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Root directory to scan recursively. Defaults to the Codex skills directory.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to the generated plan JSON file.",
    )
    parser.add_argument(
        "--include-original",
        action="store_true",
        help="Include the original description text in each entry.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    parser.add_argument(
        "--auto-summary",
        action="store_true",
        help="Prefill a heuristic Chinese candidate summary for each pending entry.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include files that already contain Chinese so summaries can be rewritten.",
    )
    return parser.parse_args()


def resolve_scan_root(root_arg: str | None) -> Path:
    if root_arg:
        return Path(root_arg).expanduser().resolve()
    codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    return (codex_home / DEFAULT_SKILLS_DIR).resolve()


def iter_skill_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("SKILL.md") if path.is_file())


def extract_description(path: Path) -> tuple[str | None, bool]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, False

    frontmatter_end = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            frontmatter_end = idx
            break
    if frontmatter_end is None:
        return None, False

    for idx in range(1, frontmatter_end):
        line = lines[idx]
        if not re.match(r"^description:\s*", line):
            continue
        raw = line.split(":", 1)[1].strip()
        if raw in {"|", "|-", ">", ">-"}:
            content_lines = []
            for j in range(idx + 1, frontmatter_end):
                content_lines.append(lines[j])
            return "\n".join(content_lines).strip(), True
        return raw.strip().strip("\"'"), True
    return None, True


def contains_chinese(text: str) -> bool:
    return bool(CHINESE_RE.search(text))


def strip_existing_summary(text: str) -> str:
    if SEPARATOR in text:
        return text.split(SEPARATOR, 1)[1].strip()
    return text


def is_placeholder(text: str) -> bool:
    stripped = text.strip()
    return any(pattern.search(stripped) for pattern in PLACEHOLDER_PATTERNS)


def shorten_summary(summary: str) -> str:
    summary = re.sub(r"\s+", "", summary)
    summary = summary[:24]
    if summary.endswith(("并", "与", "和", "及", "、")):
        summary = summary[:-1]
    return summary or "补充技能中文描述"


def choose_action(text: str) -> str:
    lowered = text.lower()
    for source, target in PHRASE_MAP:
        if source in lowered:
            return target
    return "处理"


def choose_object(text: str) -> str:
    lowered = text.lower()
    for source, target in NOUN_MAP:
        if source in lowered:
            return target
    if "skill" in lowered:
        return "技能"
    return "内容"


def collect_quality_hints(text: str) -> list[str]:
    lowered = text.lower()
    hints: list[str] = []
    for source, target in QUALITY_HINTS:
        if source in lowered and target not in hints:
            hints.append(target)
    return hints


def build_summary_parts(text: str) -> list[str]:
    action = choose_action(text)
    obj = choose_object(text)
    hints = collect_quality_hints(text)
    lowered = text.lower()
    parts = [action]

    quality_prefix = "".join(
        hint for hint in hints if hint in {"官方", "最新", "交互式", "持久化"}
    )
    core = f"{quality_prefix}{obj}" if quality_prefix else obj

    parts.append(core)

    tail_hints = [
        hint
        for hint in hints
        if hint not in {"官方", "最新", "真实浏览器", "交互式", "持久化"}
    ]
    if "from a curated list" in lowered or "curated list" in lowered:
        tail_hints.append("精选列表")
    if "from another repo" in lowered or "github repo path" in lowered or "github repo" in lowered:
        tail_hints.append("仓库来源")
    if "use when" in lowered and "openai" in lowered and "documentation" in lowered:
        tail_hints.append("OpenAI")

    deduped_tail: list[str] = []
    for hint in tail_hints:
        if hint not in deduped_tail:
            deduped_tail.append(hint)

    if deduped_tail:
        parts.append("".join(deduped_tail[:2]))
    return parts


def infer_summary(text: str) -> str:
    if is_placeholder(text):
        return "等待写入描述"
    if contains_chinese(text):
        return ""

    for pattern, summary in SUMMARY_PATTERNS:
        if pattern.search(text):
            return shorten_summary(summary)

    summary = "".join(build_summary_parts(text))

    if "batch" in text.lower() and "批量" not in summary:
        summary = f"批量{summary}"
    if "skills directory" in text.lower() and "Skills目录" not in summary and len(summary) <= 14:
        summary = f"{summary}（Skills目录）"
    elif "current directory" in text.lower() and "当前目录" not in summary and len(summary) <= 16:
        summary = f"{summary}（当前目录）"

    return shorten_summary(summary)


def main() -> int:
    args = parse_args()
    root = resolve_scan_root(args.root)
    output = Path(args.output).expanduser().resolve()

    if output.exists() and not args.overwrite:
        print(f"Output file already exists: {output}", file=sys.stderr)
        print("Use --overwrite to replace it.", file=sys.stderr)
        return 1

    entries = []
    scanned = 0
    for path in iter_skill_files(root):
        scanned += 1
        description, frontmatter_ok = extract_description(path)
        if not frontmatter_ok or description is None:
            continue
        original_description = description
        description = strip_existing_summary(description)
        if contains_chinese(original_description) and not args.all:
            continue

        entry = {
            "path": str(path.resolve()),
            "summary": infer_summary(description) if args.auto_summary else ("等待写入描述" if is_placeholder(description) else ""),
        }
        if args.include_original:
            entry["original_description"] = original_description
        entries.append(entry)

    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"entries": entries}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"Generated {output} with {len(entries)} pending entries "
        f"from {scanned} scanned SKILL.md files."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
