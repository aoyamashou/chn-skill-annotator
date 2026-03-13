---
name: chn-note-security-scan
description: 在安装新的 Skill 或 MCP 后，先询问是否执行中文备注与安全审计，并按用户选择运行对应流程。支持三选一入口：中文备注+安全审计、仅中文备注、仅安全审计。
version: "0.1.0"
---

# CHN Note Security Scan

当用户安装新的 Skill 或 MCP，或要求你为 Skill / MCP 执行中文备注与安全检查时，使用这个 Skill。

这个 Skill 是一个入口协调器，负责先询问用户，再根据选择执行对应子流程。

## 固定交互流程

触发后，第一句必须先问用户：

`即将安装新的Skill或MCP，在安装后是否进行前置操作？`

然后紧接着给出三个选项：

`1. 中文备注+安全审计`

`2. 仅中文备注`

`3. 仅安全审计`

如果用户没有明确选择，默认按：

`1. 中文备注+安全审计`

处理。

## 选择分流规则

### 选项 1

先执行“中文备注”流程，再执行“安全审计”流程。

### 选项 2

只执行“中文备注”流程，不做安全审计。

### 选项 3

只执行“安全审计”流程，不做中文备注。

## 中文备注流程

仅对目标目录下的 `SKILL.md` 生效。

优先使用以下脚本：

- `scripts/generate_plan.py`
- `scripts/annotate_descriptions.py`

执行顺序：

1. 先检查哪些 `SKILL.md` 还没有中文备注
2. 为每个待处理项生成简洁中文摘要
3. 生成 plan 文件
4. 先执行 dry-run 预览
5. 预览正常后再执行 annotate

推荐命令：

```bash
python3 scripts/annotate_descriptions.py check --root <target>
python3 scripts/generate_plan.py --root <target> --output /tmp/chn-note-plan.json --include-original --auto-summary --overwrite
python3 scripts/annotate_descriptions.py dry-run --root <target> --plan /tmp/chn-note-plan.json
python3 scripts/annotate_descriptions.py annotate --root <target> --plan /tmp/chn-note-plan.json
```

中文摘要规则：

- 保持简洁，通常 `10-25` 个汉字
- 使用功能性语言，不写营销文案
- 保留原英文描述
- 使用全角分隔符 `｜`
- 如果已经包含中文，跳过
- 如果是占位文本，使用 `等待写入描述`
- 只修改 frontmatter 中的 `description`

如果目标是 MCP 包且目录下没有 `SKILL.md`，明确说明：

`中文备注不适用，已跳过。`

## 安全审计流程

默认优先做快速文本安全扫描。

优先使用：

- `scripts/scan-skills.sh`

默认检查：

- `SKILL.md` 中的提示注入
- 角色劫持
- 数据外传
- 危险破坏命令
- 硬编码凭据
- 混淆与隐藏载荷
- 安全机制绕过
- frontmatter 完整性
- 软链接来源信息

推荐命令：

```bash
bash scripts/scan-skills.sh <target>
```

如果用户明确要求“安装前深度审计”或目标是 MCP 包，需要在快速扫描之后补做扩展审计，检查：

- 文件清单与高风险文件
- 指令层风险
- 脚本执行层风险
- 敏感数据读取
- 外部数据外传
- 持久化与系统修改
- 供应链扩张点

## 误报处理

不要仅凭正则命中直接下结论。

以下情况要标记为 `FALSE POSITIVE`：

- 文档只是在讲解 prompt injection 风险
- 文档只是在列举危险命令作为反例
- 文档只是在说明如何检测数据外传

如果无法确认，就明确写：

`需要人工复核`

## 输出要求

### 1. 用户选择

先写明本次执行的是：

- `中文备注+安全审计`
- `仅中文备注`
- `仅安全审计`

### 2. 中文备注结果

如果执行了中文备注，输出：

- 扫描范围
- 待处理数量
- dry-run 结果
- 实际写入结果
- 跳过项

### 3. 安全审计结果

如果执行了安全审计，按严重级别分组：

- `🔴 高危`
- `🟡 中危`
- `🟢 低危`

每条发现包含：

- 名称
- 文件路径
- 风险类别
- 触发内容摘要
- 是否误报
- 为什么重要

### 4. 最终结论

根据本次执行的流程，使用下列结论：

- `可继续使用`
- `建议修正后使用`
- `不建议使用`

## 复核原则

- 如果功能冲突或重复，以安全扫描规则和中文备注规则的明确脚本流程为准。
- 不要把“未检查”写成“无问题”。
- 不要修改 `name` 字段。
- 不要改动 `description` 以外的无关 frontmatter。
- 如果用户只选择其中一项，不要额外执行另一项。
