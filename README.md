<img width="2382" height="1724" alt="image" src="https://github.com/user-attachments/assets/13f1178a-215b-43d9-aa29-d96499ead223" /># chn-skill-annotator

这是一个小工具，用来给当前目录里的 `SKILL.md` 文件补中文 `description`。

如果一个技能文件的 `description` 只有英文，它会帮你把中文摘要加在前面，保留后面的英文内容。  
如果已经有中文了，它会跳过，不重复修改。

## 它是做什么的

简单说，这个项目就是：

- 扫描当前目录下的 `SKILL.md`
- 找出还没有中文描述的文件
- 先预览会改什么
- 再把中文描述写进去

写进去后会像这样：

```yaml
description: 中文摘要｜Original English description
```
大概会是这样一个效果。

<img width="2382" height="1724" alt="image" src="https://github.com/user-attachments/assets/e212603f-b730-46aa-a3b7-46ff4cba4620" />


## 适合什么时候用

如果你有一批技能文件，里面的描述大多是英文，想批量补上一句简短中文说明，就可以用这个项目。

## 怎么用

先检查有哪些文件需要处理：

```bash
python scripts/annotate_descriptions.py check
```

生成一个计划文件：

```bash
python scripts/generate_plan.py --output ./plan.json --include-original
```

先预览，不真的修改文件：

```bash
python scripts/annotate_descriptions.py dry-run --plan ./plan.json
```

确认没问题后，正式写入：

```bash
python scripts/annotate_descriptions.py annotate --plan ./plan.json
```

## 项目里有什么

- `scripts/annotate_descriptions.py`：检查、预览、写入
- `scripts/generate_plan.py`：生成 plan 文件
- `SKILL.md`：这个工具自己的技能说明

## 说明

这个工具只会处理 `SKILL.md` 里的 `description` 字段，不会乱改别的内容。
