---
name: chn-skill-annotator
description: 为 Codex 的 Skills 目录下各个 SKILL.md 的 description 批量补充中文注释并跳过已有中文项｜Annotate frontmatter description fields in SKILL.md files under the Codex skills directory with a concise Chinese one-line summary, preserving the original English description. Use when the user asks to add Chinese notes to skill metadata, scan SKILL.md descriptions, check which skills still lack Chinese, preview changes with dry-run, or batch-update skills in the Codex skills directory.
---

# CHN Skill Annotator

## Overview

Scan `SKILL.md` files under the Codex skills directory, detect whether `description` already contains Chinese, and prepend a concise Chinese summary when needed.

Use the bundled script for scanning, plan validation, dry-run previews, and deterministic writeback. Generate the Chinese summaries yourself before applying them.

## Workflow

1. Run the checker first to identify which `SKILL.md` files still need Chinese annotations.
2. Read each pending `description` and write one concise Chinese sentence.
3. If the original description is a placeholder or TODO-style text, use `等待写入描述`.
4. Save the summaries into a JSON plan file.
5. Run `dry-run` to preview the changes.
6. Run `annotate` to write the changes after the preview looks correct.

## Summary Rules

- Keep the Chinese summary concise. Target roughly `12-32` Chinese characters.
- Use direct functional language instead of marketing language.
- Preserve key qualifiers from the English description when they matter, such as `官方`, `最新`, `交互式`, `私有仓库`, `Cloudflare`, or similar scope-defining details.
- Preserve the original English description after the Chinese summary.
- Always use the full-width separator `｜`.
- If a `description` already contains Chinese, skip it.
- If the YAML description uses block style (`|`), prepend the Chinese summary only to the first non-empty content line.
- Only modify the frontmatter `description` field.
- By default, only operate on `SKILL.md` files under the Codex skills directory.
- Allow `--root` to override the scan root when the user explicitly requests a different directory.

## Script

Use `scripts/annotate_descriptions.py` and `scripts/generate_plan.py`.

### Generate a plan template

```bash
python scripts/generate_plan.py --output ./plan.json --include-original
```

This scans the Codex skills directory recursively and writes a template JSON file containing only the `SKILL.md` files that still need Chinese summaries.

By default the scripts resolve the scan root as `$CODEX_HOME/skills`, and fall back to `~/.codex/skills` when `CODEX_HOME` is not set.

Use `--overwrite` if the output file already exists.

Add `--auto-summary` to prefill a heuristic Chinese candidate summary for each pending entry.

### Check files

```bash
python scripts/annotate_descriptions.py check
```

This scans the Codex skills directory recursively and reports:

- `pending`: no Chinese yet, needs annotation
- `annotated`: already contains Chinese, skip
- `missing`: no `description` field

### Create a plan

Prepare or generate a JSON file like:

```json
{
  "entries": [
    {
      "path": "/absolute/path/to/some/SKILL.md",
      "summary": "创建和编辑演示文稿"
    }
  ]
}
```

Rules:

- Use absolute paths when possible.
- Each `summary` must be Chinese only and must not include `｜`.
- Use `等待写入描述` for placeholder descriptions.
- If `--auto-summary` is enabled, review each generated summary before applying it, especially to confirm it preserves the English description's core scope and qualifiers.

### Preview changes

```bash
python scripts/annotate_descriptions.py dry-run --plan /path/to/plan.json
```

### Apply changes

```bash
python scripts/annotate_descriptions.py annotate --plan /path/to/plan.json
```

## Output Expectations

The script prints per-file results and a final summary including how many files were:

- updated
- skipped
- missing
- errored

If `dry-run` is used, no files are modified.

## Guardrails

- Do not overwrite Chinese that already exists.
- Do not rewrite unrelated frontmatter fields.
- Do not change the `name` field.
- Do not invent long Chinese paragraphs. One sentence only.
- Do not touch files outside the selected scan root.
