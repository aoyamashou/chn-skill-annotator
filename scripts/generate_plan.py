#!/usr/bin/env python3
"""Generate a plan template for pending Chinese description annotations."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
PLACEHOLDER_PATTERNS = (
    re.compile(r"replace with description", re.IGNORECASE),
    re.compile(r"\[todo:.*description", re.IGNORECASE),
    re.compile(r"todo", re.IGNORECASE),
)
PHRASE_MAP = [
    ("search and manage", "搜索和管理"),
    ("create, manage, and delete", "创建、管理和删除"),
    ("create and edit", "创建和编辑"),
    ("create, edit, and analyze", "创建、编辑和分析"),
    ("creation, editing, and analysis", "创建、编辑和分析"),
    ("creation and editing", "创建和编辑"),
    ("read and update", "读取和更新"),
    ("fetch and read", "抓取和读取"),
    ("read, watch, and listen to", "读取、观看和收听"),
    ("find, organize, and manage", "查找、整理和管理"),
    ("search and install", "搜索并安装"),
    ("search, install, and manage", "搜索、安装和管理"),
    ("generate and edit", "生成和编辑"),
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
    ("applications and infrastructure", "应用和基础设施"),
    ("browser automation", "浏览器自动化"),
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
        default=".",
        help="Root directory to scan recursively. Defaults to the current directory.",
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
    return parser.parse_args()


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


def infer_summary(text: str) -> str:
    if is_placeholder(text):
        return "等待写入描述"
    if contains_chinese(text):
        return ""

    action = choose_action(text)
    obj = choose_object(text)
    summary = f"{action}{obj}"

    if "batch" in text.lower() and "批量" not in summary:
        summary = f"批量{summary}"
    if "current directory" in text.lower() and "当前目录" not in summary and len(summary) <= 16:
        summary = f"{summary}（当前目录）"

    return shorten_summary(summary)


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
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
        if contains_chinese(description):
            continue

        entry = {
            "path": str(path.resolve()),
            "summary": infer_summary(description) if args.auto_summary else ("等待写入描述" if is_placeholder(description) else ""),
        }
        if args.include_original:
            entry["original_description"] = description
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
