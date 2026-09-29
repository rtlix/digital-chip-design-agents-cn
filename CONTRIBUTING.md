# 为 digital-chip-design-agents 贡献代码

## Skill 文件规范

每个 `SKILL.md` 都必须按以下顺序包含这些章节：

```markdown
---                          ← YAML frontmatter（必需）
name: domain-name
description: >
  用于 Claude Code Skill 自动发现的一句话描述。
version: x.y.z
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill: Domain Name

## Purpose
用一个段落说明该 Skill 能让 Claude 完成什么工作。

## Stage: stage_name          ← 每个 stage 重复一组

### Domain Rules
使用编号规则。必须具体，模糊规则没有实际价值。

### QoR Metrics to Evaluate
可测量的 pass/fail 判据，并注明单位（ns、%、count）。

### Common Issues & Fixes
表格：Issue | Fix

### Output Required
列出该 stage 必须生成的文件或 artifact。
```

## 添加新的 Skill

1. 按上述规范创建
   `plugins/<new-domain>/skills/<new-domain>/SKILL.md`。

2. 在 `.claude-plugin/marketplace.json` 中添加条目：

```json
{
  "name": "chip-design-<new-domain>",
  "source": { "source": "github", "repo": "chuanseng-ng/digital-chip-design-agents" },
  "description": "One-line description",
  "category": "engineering",
  "keywords": ["keyword1", "keyword2"]
}
```

3. 创建
   `plugins/<new-domain>/agents/<new-domain>-orchestrator.md`，
   最低结构如下：

```markdown
---
name: <new-domain>-orchestrator
description: >
  说明何时调用该 Orchestrator。
model: sonnet
effort: high
maxTurns: 50
skills:
  - digital-chip-design-agents:<new-domain>
---

## Stage Sequence
stage_1 → stage_2 → stage_3

## Loop-Back Rules
- stage_2 FAIL (condition)  → stage_1  (max N×)

## Sign-off Criteria
- metric_name: value

## Behaviour Rules
1. ...
```

4. 添加共享章节。每个 Orchestrator 都需要携带一组完全一致的 guard
   （stage gating、escalation，以及当该领域没有 MCP server 时的 execution note）。
   这些内容**不要手工复制**：

```bash
python3 tools/sync_agent_sections.py          # 将共享区块写入各 Agent
python3 tools/sync_agent_sections.py --list   # 显示每个区块会同步到哪里
```

共享文本只维护在
`tools/agent_shared_sections.md`，
脚本会把内容插入到 `## Behaviour Rules` 之后，
并放在 `BEGIN SHARED` / `END SHARED` 标记之间。

如果要修改共享规则，只修改
`tools/agent_shared_sections.md` 后重新运行同步脚本；
**不要直接编辑标记之间的内容**。
若新 Agent 不应包含某个共享区块，把它加入该区块的 `except:` 列表。

5. 本地运行校验：

```bash
python3 -c "
import glob
for p in sorted(glob.glob('plugins/*/skills/*/SKILL.md')):
    c = open(p, encoding='utf-8').read()
    assert c.startswith('---'), f'{p}: missing frontmatter'
    for s in ['## Purpose','## Domain Rules','## QoR Metrics','## Output Required']:
        assert s in c, f'{p}: missing {s}'
    print(f'OK: {p}')
"
python3 tools/sync_agent_sections.py --check
python3 -m pytest tests/ -q
```

6. 创建 Pull Request。合并前 CI 中的 `validate.yml` 必须通过。

## 改进已有 Skill

- **Domain Rules**：写得更具体，增加工具相关命令，更新指标
- **QoR Metrics**：补充单位，并根据真实项目经验收紧目标
- **Orchestrator 中的 loop-back rules**：增加新的状态转换，或降低最大迭代次数

## Pull Request 检查清单

- [ ] `SKILL.md` 的 YAML frontmatter 包含 `name`、`description`、`version`
- [ ] `SKILL.md` 包含全部四个必需章节
- [ ] 新增 domain 时已经更新 `marketplace.json`
- [ ] Orchestrator `.md` 的 frontmatter 包含 `model`、`effort`、`maxTurns`、`skills`
- [ ] Orchestrator `.md` 包含 `## Stage Sequence`、`## Loop-Back Rules`、`## Sign-off Criteria`、`## Behaviour Rules`
- [ ] 共享章节保持同步：`python3 tools/sync_agent_sections.py --check`
- [ ] 本地校验通过（见上文）
- [ ] 数量保持一致：agents 数量 = marketplace entries 数量，且 skills ≥ agents（一个 plugin 可以注册多个 Skill）

## 版本规则

- `PATCH`（x.x.1）—— 修复问题，或澄清已有 Skill
- `MINOR`（x.1.0）—— 增加新的 Skill 或 Orchestrator domain
- `MAJOR`（2.0.0）—— 对 frontmatter schema 或 stage interface 做不兼容变更

## plugin.json 中的共享元数据

每个 `plugins/<domain>/.claude-plugin/plugin.json` 都重复包含相同的
`author`、`homepage`、`repository` 和 `license` 字段。
这是有意设计的，因为插件安装器会独立读取每个 manifest，并要求这些字段存在。

权威值如下：

```json
"author":     { "name": "chuanseng-ng", "url": "https://github.com/chuanseng-ng" },
"homepage":   "https://github.com/chuanseng-ng/digital-chip-design-agents",
"repository": "https://github.com/chuanseng-ng/digital-chip-design-agents",
"license":    "MIT"
```

更新这些字段时，必须同时修改全部 16 个 `plugin.json`
以及 `.claude-plugin/marketplace.json`。
