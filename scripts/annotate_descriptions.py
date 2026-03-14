#!/usr/bin/env python3
"""Scan and annotate SKILL.md description fields with Chinese summaries."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SEPARATOR = "｜"
DEFAULT_SKILLS_DIR = "skills"
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
PLACEHOLDER_PATTERNS = (
    re.compile(r"replace with description", re.IGNORECASE),
    re.compile(r"\[todo:.*description", re.IGNORECASE),
    re.compile(r"todo", re.IGNORECASE),
)


@dataclass
class DescriptionBlock:
    path: Path
    lines: list[str]
    frontmatter_end: int
    description_index: int
    block_end: int
    is_block: bool
    content_lines: list[str]
    raw_text: str

    @property
    def has_chinese(self) -> bool:
        return bool(CHINESE_RE.search(self.raw_text))

    @property
    def is_placeholder(self) -> bool:
        text = self.raw_text.strip()
        return any(pattern.search(text) for pattern in PLACEHOLDER_PATTERNS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check or annotate SKILL.md description fields."
    )
    parser.add_argument(
        "mode", choices=("check", "dry-run", "annotate"), help="Operation mode."
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Root directory to scan recursively. Defaults to the Codex skills directory.",
    )
    parser.add_argument(
        "--plan",
        help="Path to a JSON plan file. Required for dry-run and annotate.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output in check mode.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow dry-run and annotate to rewrite descriptions that already contain Chinese.",
    )
    return parser.parse_args()


def resolve_scan_root(root_arg: str | None) -> Path:
    if root_arg:
        return Path(root_arg).expanduser().resolve()
    codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    return (codex_home / DEFAULT_SKILLS_DIR).resolve()


def iter_skill_files(root: Path) -> Iterable[Path]:
    return sorted(path for path in root.rglob("SKILL.md") if path.is_file())


def load_description_block(path: Path) -> DescriptionBlock | None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None

    frontmatter_end = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            frontmatter_end = idx
            break
    if frontmatter_end is None:
        return None

    description_index = None
    for idx in range(1, frontmatter_end):
        if re.match(r"^description:\s*", lines[idx]):
            description_index = idx
            break
    if description_index is None:
        return DescriptionBlock(
            path=path,
            lines=lines,
            frontmatter_end=frontmatter_end,
            description_index=-1,
            block_end=-1,
            is_block=False,
            content_lines=[],
            raw_text="",
        )

    line = lines[description_index]
    match = re.match(r"^description:\s*(.*?)(\r?\n)$", line)
    raw_value = match.group(1) if match else line.split(":", 1)[1].strip()
    newline = match.group(2) if match else "\n"
    if raw_value.strip() in {"|", "|-", ">", ">-"}:
        content_lines: list[str] = []
        block_end = description_index + 1
        while block_end < frontmatter_end:
            candidate = lines[block_end]
            if re.match(r"^[A-Za-z0-9_-]+:\s*", candidate) and not candidate.startswith(
                " "
            ):
                break
            content_lines.append(candidate)
            block_end += 1
        raw_text = "".join(content_lines)
        return DescriptionBlock(
            path=path,
            lines=lines,
            frontmatter_end=frontmatter_end,
            description_index=description_index,
            block_end=block_end,
            is_block=True,
            content_lines=content_lines,
            raw_text=raw_text,
        )

    return DescriptionBlock(
        path=path,
        lines=lines,
        frontmatter_end=frontmatter_end,
        description_index=description_index,
        block_end=description_index + 1,
        is_block=False,
        content_lines=[],
        raw_text=raw_value.strip().strip("\"'"),
    )


def normalize_summary(summary: str) -> str:
    summary = summary.strip()
    if not summary:
        raise ValueError("summary is empty")
    if SEPARATOR in summary:
        raise ValueError(f"summary must not contain {SEPARATOR!r}")
    if not CHINESE_RE.search(summary):
        raise ValueError("summary must contain Chinese characters")
    return summary


def load_plan(plan_path: Path) -> dict[Path, str]:
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "entries" in data:
        entries = data["entries"]
    elif isinstance(data, list):
        entries = data
    else:
        raise ValueError("plan JSON must be a list or an object with an 'entries' key")

    plan: dict[Path, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("each plan entry must be an object")
        path_raw = entry.get("path")
        summary_raw = entry.get("summary")
        if not path_raw or not summary_raw:
            raise ValueError("each plan entry must include 'path' and 'summary'")
        path = Path(path_raw).expanduser().resolve()
        plan[path] = normalize_summary(summary_raw)
    return plan


def classify_block(block: DescriptionBlock | None) -> str:
    if block is None:
        return "invalid"
    if block.description_index == -1:
        return "missing"
    if block.has_chinese:
        return "annotated"
    return "pending"


def render_updated_lines(block: DescriptionBlock, summary: str) -> list[str]:
    lines = block.lines[:]
    if block.is_block:
        content_lines = block.content_lines[:]
        inserted = False
        for idx, line in enumerate(content_lines):
            if not line.strip():
                continue
            indent = re.match(r"^(\s*)", line).group(1)
            body = line[len(indent) :]
            if SEPARATOR in body:
                body = body.split(SEPARATOR, 1)[1]
            content_lines[idx] = f"{indent}{summary}{SEPARATOR}{body}"
            inserted = True
            break
        if not inserted:
            content_lines = [f"  {summary}{SEPARATOR}\n"]
        return lines[: block.description_index + 1] + content_lines + lines[block.block_end :]

    original_line = lines[block.description_index]
    match = re.match(r"^(description:\s*)(.*?)(\r?\n)$", original_line)
    if not match:
        raise ValueError("unable to parse description line")
    prefix, raw_value, newline = match.groups()
    value = raw_value.strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        quote = value[0]
        inner = value[1:-1]
        if SEPARATOR in inner:
            inner = inner.split(SEPARATOR, 1)[1]
        new_value = f"{quote}{summary}{SEPARATOR}{inner}{quote}"
    else:
        if SEPARATOR in value:
            value = value.split(SEPARATOR, 1)[1]
        new_value = f"{summary}{SEPARATOR}{value}"
    lines[block.description_index] = f"{prefix}{new_value}{newline}"
    return lines


def run_check(root: Path, as_json: bool) -> int:
    results = []
    counts = {"pending": 0, "annotated": 0, "missing": 0, "invalid": 0}
    for path in iter_skill_files(root):
        block = load_description_block(path)
        status = classify_block(block)
        counts[status] += 1
        results.append(
            {
                "path": str(path.resolve()),
                "status": status,
                "placeholder": bool(block and block.is_placeholder),
                "description": "" if block is None else block.raw_text.strip(),
            }
        )

    if as_json:
        print(json.dumps({"counts": counts, "results": results}, ensure_ascii=False, indent=2))
        return 0

    for item in results:
        suffix = " placeholder" if item["placeholder"] else ""
        print(f"{item['status']:10} {item['path']}{suffix}")
    print(
        "SUMMARY "
        f"pending={counts['pending']} "
        f"annotated={counts['annotated']} "
        f"missing={counts['missing']} "
        f"invalid={counts['invalid']}"
    )
    return 0


def run_apply(root: Path, plan_path: Path, dry_run: bool, force: bool) -> int:
    plan = load_plan(plan_path)
    counts = {"updated": 0, "skipped": 0, "missing": 0, "errored": 0}

    for target_path, summary in sorted(plan.items()):
        try:
            if not target_path.exists():
                print(f"missing     {target_path}")
                counts["missing"] += 1
                continue

            resolved_root = root.resolve()
            resolved_target = target_path.resolve()
            if resolved_root not in resolved_target.parents and resolved_target != resolved_root:
                print(f"errored     {target_path} outside root")
                counts["errored"] += 1
                continue

            block = load_description_block(resolved_target)
            status = classify_block(block)
            allowed_statuses = {"pending", "annotated"} if force else {"pending"}
            if status not in allowed_statuses:
                print(f"skipped     {target_path} ({status})")
                counts["skipped"] += 1
                continue

            new_lines = render_updated_lines(block, summary)
            if dry_run:
                print(f"preview     {target_path} -> {summary}")
            else:
                resolved_target.write_text("".join(new_lines), encoding="utf-8")
                print(f"updated     {target_path} -> {summary}")
            counts["updated"] += 1
        except Exception as exc:  # noqa: BLE001
            print(f"errored     {target_path} {exc}")
            counts["errored"] += 1

    label = "DRY-RUN" if dry_run else "SUMMARY"
    print(
        f"{label} updated={counts['updated']} "
        f"skipped={counts['skipped']} "
        f"missing={counts['missing']} "
        f"errored={counts['errored']}"
    )
    return 0 if counts["errored"] == 0 else 1


def main() -> int:
    args = parse_args()
    root = resolve_scan_root(args.root)

    if args.mode == "check":
        return run_check(root, args.json)

    if not args.plan:
        print("--plan is required for dry-run and annotate", file=sys.stderr)
        return 1

    plan_path = Path(args.plan).expanduser().resolve()
    return run_apply(root, plan_path, dry_run=args.mode == "dry-run", force=args.force)


if __name__ == "__main__":
    sys.exit(main())
