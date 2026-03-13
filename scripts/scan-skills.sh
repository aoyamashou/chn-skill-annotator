#!/usr/bin/env bash
set -euo pipefail

# 扫描本地 Skill 文本风险、frontmatter 与来源信息。

if [ "$#" -gt 0 ]; then
  DIRS=("$@")
else
  DIRS=()
  [ -d "./.claude/skills" ] && DIRS+=("./.claude/skills")
  [ -d "$HOME/.claude/skills" ] && DIRS+=("$HOME/.claude/skills")
  [ -d "$HOME/.codex/skills" ] && DIRS+=("$HOME/.codex/skills")
fi

if [ "${#DIRS[@]}" -eq 0 ]; then
  echo "未找到可扫描的 skills 目录。"
  exit 0
fi

echo "=== SCAN ROOTS ==="
for dir in "${DIRS[@]}"; do
  echo "$dir"
done

echo
echo "=== SKILL INVENTORY ==="
for dir in "${DIRS[@]}"; do
  [ -d "$dir" ] || continue
  find -L "$dir" -name "SKILL.md" 2>/dev/null | while IFS= read -r f; do
    words=$(wc -w < "$f" | tr -d ' ')
    skill_dir=$(dirname "$f")
    is_link="no"
    link_target=""
    if [ -L "$skill_dir" ]; then
      is_link="yes"
      link_target=$(readlink -f "$skill_dir")
    fi
    echo "path=$f words=$words symlink=$is_link target=$link_target"
  done
done

echo
echo "=== SKILL SECURITY SCAN ==="
for dir in "${DIRS[@]}"; do
  [ -d "$dir" ] || continue
  find -L "$dir" -name "SKILL.md" 2>/dev/null | while IFS= read -r f; do
    echo "--- SCANNING: $f ---"
    grep -inE 'ignore (previous|above|all) (instructions|prompts|rules)' "$f" && echo "[!] PROMPT_INJECTION: $f" || true
    grep -inE '(you are now|pretend you are|act as if|new persona)' "$f" && echo "[!] ROLE_HIJACK: $f" || true
    grep -inE '(curl|wget).*(-X *POST|--data).*\$' "$f" && echo "[!] DATA_EXFIL: $f" || true
    grep -inE 'base64.*encode.*secret|base64.*encode.*key|base64.*encode.*token' "$f" && echo "[!] DATA_EXFIL_B64: $f" || true
    grep -nE 'rm\s+-rf\s+[/~]' "$f" && echo "[!] DESTRUCTIVE: $f" || true
    grep -nE 'git push --force\s+origin\s+main' "$f" && echo "[!] DESTRUCTIVE_GIT: $f" || true
    grep -nE 'chmod\s+777' "$f" && echo "[!] DESTRUCTIVE_PERM: $f" || true
    grep -nE "(api_key|secret_key|api_secret|access_token)\s*[:=]\s*[\"'][A-Za-z0-9+/]{16,}" "$f" && echo "[!] HARDCODED_CRED: $f" || true
    grep -nE 'eval\s*\$\(' "$f" && echo "[!] OBFUSCATION_EVAL: $f" || true
    grep -nE 'base64\s+-d' "$f" && echo "[!] OBFUSCATION_B64: $f" || true
    grep -nE '\\x[0-9a-fA-F]{2}' "$f" && echo "[!] OBFUSCATION_HEX: $f" || true
    grep -inE '(override|bypass|disable)\s*(the\s+)?(safety|rules?|hooks?|guard|verification)' "$f" && echo "[!] SAFETY_OVERRIDE: $f" || true
  done
done

echo
echo "=== SKILL FRONTMATTER ==="
for dir in "${DIRS[@]}"; do
  [ -d "$dir" ] || continue
  find -L "$dir" -name "SKILL.md" 2>/dev/null | while IFS= read -r f; do
    if head -1 "$f" | grep -q '^---'; then
      echo "frontmatter=yes path=$f"
      sed -n '2,/^---$/p' "$f" | head -10
    else
      echo "frontmatter=MISSING path=$f"
    fi
  done
done

echo
echo "=== SKILL SYMLINK PROVENANCE ==="
for dir in "${DIRS[@]}"; do
  [ -d "$dir" ] || continue
  find "$dir" -maxdepth 1 -type l 2>/dev/null | while IFS= read -r link; do
    target=$(readlink -f "$link")
    echo "link=$(basename "$link") target=$target"
    if [ -d "$target/.git" ]; then
      remote=$(git -C "$target" remote get-url origin 2>/dev/null || echo "unknown")
      commit=$(git -C "$target" rev-parse --short HEAD 2>/dev/null || echo "unknown")
      echo "  git_remote=$remote commit=$commit"
    fi
  done
done
