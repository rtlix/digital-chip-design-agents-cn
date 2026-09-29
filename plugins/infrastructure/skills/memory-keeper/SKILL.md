---
name: memory-keeper
description: >
  将累计的 experience record（experiences.jsonl）蒸馏为更新后的领域知识摘要
  （knowledge.md），适用于任意 chip-design domain。建议每 10 次 Orchestrator
  session 后运行，或在某领域积累了新的 issue/fix pattern 时按需运行。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill: Memory Keeper（经验蒸馏）

## Invocation

```text
/chip-design-infrastructure:memory-keeper [--domain <name>] [--all] [--min-records <n>] [--init]
```

- `--domain <name>` —— 蒸馏单个 domain，例如 synthesis、sta、pd
- `--all` —— 对所有拥有足够 `experiences.jsonl` record 的 domain 蒸馏
- `--min-records <n>` —— 最小记录数，默认 5；低于阈值跳过
- `--init` —— 解析并初始化中央 Memory root，把 repo-local runtime data 迁移过去；只初始化，不做蒸馏

如果没有给 `--domain`、`--all`、`--init`，要求用户选择。

---

## Memory Root Resolution

Memory **不是**固定使用相对路径 `memory/`。活动 root 由
`memory_root.py` 解析，它也是 `distill.py` 与 `tools/qor_trends.py` 共用的唯一来源，
优先级：

1. 显式 `--memory-root PATH`
2. `$CHIP_DESIGN_MEMORY_ROOT`
3. 中央默认：
   `${XDG_DATA_HOME:-$HOME/.local/share}/chip-design-agents/digital/memory`
   （Windows：`%LOCALAPPDATA%\chip-design-agents\digital\memory`）
4. 仓库 `memory/` seed；仅中央路径不可写时 fallback

仓库里的 `memory/` 是版本控制的 **seed**：第一次解析时，如果中央 root 中缺少某
`<domain>/knowledge.md`，就复制过去；绝不覆盖已经积累的数据。
Runtime `experiences.jsonl/run_state.md` 从不作为 seed。
Orchestrator 在 session start 解析相同 root，并用 `<MEM>` 进行全部读写。

```bash
python3 plugins/infrastructure/skills/memory-keeper/memory_root.py
python3 plugins/infrastructure/skills/memory-keeper/memory_root.py --init
```

若希望按项目隔离，可：
`export CHIP_DESIGN_MEMORY_ROOT="$PWD/memory"`
或给脚本传 `--memory-root ./memory`。

---

## Purpose

每次 Orchestrator run 后都会向 `memory/<domain>/experiences.jsonl` 写一条 JSON record。
随着时间积累，其中包含 issue 描述、applied fix、metric range 和 tool flag 经验。
本 Skill 读取这些证据，把新知识 merge 到 `memory/<domain>/knowledge.md`，
即每个 Orchestrator 启动时都会读取的 Tier-2 summary。
若长期不蒸馏，knowledge.md 会逐渐过时，而 evidence log 不断膨胀。

---

## Domains

有效 domain 对应 `memory/` 下子目录：

| Domain | JSONL path |
|---|---|
| `architecture` | `memory/architecture/experiences.jsonl` |
| `compiler` | `memory/compiler/experiences.jsonl` |
| `dft` | `memory/dft/experiences.jsonl` |
| `firmware` | `memory/firmware/experiences.jsonl` |
| `formal` | `memory/formal/experiences.jsonl` |
| `fpga` | `memory/fpga/experiences.jsonl` |
| `hls` | `memory/hls/experiences.jsonl` |
| `infrastructure` | `memory/infrastructure/experiences.jsonl`（opt-in，按环境分 key） |
| `memory-ip` | `memory/memory-ip/experiences.jsonl` |
| `pd` | `memory/pd/experiences.jsonl` |
| `rtl-design` | `memory/rtl-design/experiences.jsonl` |
| `soc` | `memory/soc/experiences.jsonl` |
| `sta` | `memory/sta/experiences.jsonl` |
| `synthesis` | `memory/synthesis/experiences.jsonl` |
| `verification` | `memory/verification/experiences.jsonl` |

---

## Stage: load_experiences

### Domain Rules
1. 读取 `memory/<domain>/experiences.jsonl`，每行一个 JSON object。
2. 统计合法 record；若少于 `--min-records`（默认 5），打印 skip 信息并停止。
3. 文件不存在或为空也同样 skip。
4. 解析全部 record；malformed line 忽略但必须 WARN。
5. 按三条轴组织分析：
   - **Issues + fixes**：收集 `issues_encountered` / `fixes_applied`
   - **Tool flags**：在 notes/fixes 中找显式 flag/command pattern
   - **Metric ranges**：每个 numeric `key_metrics` 字段计算 min/max/median/latest

### QoR Metrics to Evaluate
- `records_read`：合法记录数，目标 ≥ threshold
- `records_skipped`：malformed line，目标 0
- `signoff_rate`：`signoff_achieved:true` 比例，仅信息性

### Output Required
生成内存中的结构化 summary：
```json
{
  "domain":"<domain>",
  "record_count":"<n>",
  "date_range":["<oldest>","<newest>"],
  "signoff_rate":"<fraction>",
  "issue_fix_pairs":[{"issue":"...","fix":"...","count":"<n>"}],
  "tool_flag_candidates":["<flag or command>"],
  "metric_ranges":{"<metric>":{"min":"x","max":"y","median":"z","latest":"w"}},
  "free_notes":["<note>"]
}
```

---

## Stage: distil_knowledge

### Domain Rules
1. 完整读取现有 `memory/<domain>/knowledge.md`。
2. 从 load_experiences summary 中找出当前 knowledge 尚未覆盖的新证据：
   - **Known Failure Patterns** 中没有的新 issue/fix
   - **Successful Tool Flags** 中没有的成功 flag
   - **PDK / Tool Quirks** 尚未记录的 PDK/tool 特殊行为
3. 每项新发现写成简洁 bullet：
   - **粗体**开头写 symptom/scenario
   - 后面写 cause + fix
   - 每项最多 2–4 句
4. 新条目追加到对应 section 下，不删除已有条目；若新证据与旧条目直接冲突，要显式标记矛盾。
5. 若 signoff rate <50%，在 **Notes** 记录常见未 signoff failure mode。
6. 更新 Notes：
   `_Last distilled: <ISO-8601 date> from <n> experience records._`
   并替换旧的同类行。
7. 写回 `knowledge.md`。

### Merge Policy
| 场景 | 动作 |
|---|---|
| 新 issue/fix | 加到 Known Failure Patterns |
| 已有条目被 ≥3 record 验证 | 增加 `(confirmed across N runs)` |
| 已有条目被 ≥3 record 反证 | 删除线标旧内容，再增加修正版 |
| 新 tool flag 出现 ≥2 次 | 加到 Successful Tool Flags |
| 单条 observation | 仅 signoff=true 且 notes 足够详细时加入 |

### QoR Metrics to Evaluate
- `new_failure_patterns`
- `new_tool_flags`
- `existing_entries_annotated`
- `contradictions_flagged`，矛盾绝不能静默覆盖

### Output Required
- 更新后的 `memory/<domain>/knowledge.md`
- Console summary：各 section 新增数量、注释/纠正数量

### Optional: claude-mem index
写完 `knowledge.md` 后，如果 `mcp__plugin_ecc_memory__add_observations` 可用，
把新 issue/fix pair 作为 observation 写到 `chip-design-<domain>-fixes`。
工具不可用则静默跳过；`knowledge.md` 与 `experiences.jsonl` 才是 canonical record。

---

## Stage: report

### Domain Rules
打印每 domain 蒸馏报告：
```text
Domain:        <domain>
Records read:  <n>
Date range:    <oldest> → <newest>
Signoff rate:  <pct>%
New entries:   +<k> Known Failure Patterns, +<j> Successful Tool Flags, +<i> PDK Quirks
Annotations:   <m> existing entries updated
knowledge.md:  memory/<domain>/knowledge.md  [updated]
```

使用 `--all` 时再打印所有 processed domain summary table。
被 skip 的 domain 列出当前 record count。

### QoR Metrics to Evaluate
- `domains_processed`：目标 ≥1
- `domains_skipped`：信息性

### Output Required
- Per-domain distillation report
- `--all` 时输出 processed/skipped summary table

---

## Sign-off Checklist
- [ ] 已读取 experiences，record count 达到阈值
- [ ] 已生成 issue/fix、metric range、tool flag summary
- [ ] 分析阶段只读现有 knowledge
- [ ] 新条目符合已有风格
- [ ] 矛盾条目显式标记
- [ ] Notes 中 distillation timestamp 已更新
- [ ] knowledge.md 已写回
- [ ] Console report 已打印

---

## Example Invocations
```bash
# 蒸馏 synthesis domain（至少 5 条）
/chip-design-infrastructure:memory-keeper --domain synthesis

# 对至少 10 条记录的所有 domain 蒸馏
/chip-design-infrastructure:memory-keeper --all --min-records 10

# 仅 3 条也强制蒸馏，用于早期反馈/debug
/chip-design-infrastructure:memory-keeper --domain sta --min-records 3
```
