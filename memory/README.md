# Agent Memory System（Agent 记忆系统）

本目录是数字芯片设计 Orchestrator 所使用的持久化文件 Memory 的**版本控制 seed**。
运行时的 live memory **不**直接存放在这里，而是位于机器级中央 Memory root，
这样不同 working directory 可以共享同一套累计经验。

每个 Agent 在 session 开始时读取 Memory；在第一 stage 前写 run-state；
每个 stage 完成后按 `run_id` upsert experience record。
不需要额外数据库或服务。

## Where Memory Lives (Resolution)（Memory 存放位置与解析规则）

活动 Memory root 由
[`plugins/infrastructure/skills/memory-keeper/memory_root.py`](../plugins/infrastructure/skills/memory-keeper/memory_root.py)
统一解析。它是 Orchestrator、`distill.py` 和 `tools/qor_trends.py`
共同使用的唯一可信来源，优先级如下：

1. 脚本显式传入的 `--memory-root PATH`
2. `$CHIP_DESIGN_MEMORY_ROOT` 环境变量
3. 中央默认路径：
   `${XDG_DATA_HOME:-$HOME/.local/share}/chip-design-agents/digital/memory`
   （Windows：`%LOCALAPPDATA%\chip-design-agents\digital\memory`）
4. 本仓库 `memory/` tree，仅当中央 root 不可写时作为 seed fallback

第一次解析时，会创建中央 root，并把本仓库各
`<domain>/knowledge.md`
在目标不存在时复制过去。
已经积累的数据**绝不会被覆盖**；
runtime `experiences.jsonl` / `run_state.md` 也绝不会作为 seed 复制。

Analog 与 Digital 使用不同子目录
（`.../analog/` 与 `.../digital/`），
因此同名 domain 不会冲突。

```bash
# 查看我的 Memory 实际存放在哪里
python3 plugins/infrastructure/skills/memory-keeper/memory_root.py

# 初始化中央 root、迁移 repo-local runtime data，然后打印结果
python3 plugins/infrastructure/skills/memory-keeper/memory_root.py --init
```

**按项目隔离 Memory（不使用中央 store）：**

```bash
export CHIP_DESIGN_MEMORY_ROOT="$PWD/memory"
```

或者给脚本传：

```bash
--memory-root ./memory
```

本文中的 `<MEM>` 都表示已经解析出的 Memory root。
Orchestrator 使用其绝对路径，而不是字面量 `memory/`。

---

## Two-Tier Design（两级 Memory 设计）

### Tier 1 — `experiences.jsonl`

JSONL 文件，以 `run_id` 为 key，
每个 stage 完成后执行 upsert/overwrite。

每次 Orchestrator run 最终只有一条 record，
随着 stage 完成不断更新。

特点：

- Machine-parseable
- 随运行不断积累
- 不应手工编辑

### Tier 2 — `knowledge.md`

供人和 Agent 阅读的蒸馏摘要。

Seed 中预置：

- 已知 failure pattern
- 成功的 tool flag
- PDK/tool quirk

随着 experience record 累积，
应定期通过 memory-keeper Skill 更新
`knowledge.md`。

---

## Experience Record Schema

```json
{
  "run_id": "<domain>_<YYYYMMDD>_<HHMMSS>",
  "timestamp": "<ISO-8601>",
  "domain": "<domain>",
  "design_name": "<from state>",
  "pdk": "<from state if known, else null>",
  "tool_used": "<primary tool>",
  "stages_completed": ["<stage>", "..."],
  "loop_backs": {"<stage>": "<count>", "..."},
  "key_metrics": { "<domain-specific fields — see table below>" },
  "issues_encountered": ["<description>", "..."],
  "fixes_applied": ["<description>", "..."],
  "signoff_achieved": false,
  "notes": "<free-text observations>"
}
```

`signoff_achieved` 是 JSON boolean，默认 `false`。
只有 sign-off stage 的**全部判据都通过**时才能设置为 `true`。

以下情况始终保持 `false`：

- escalated
- abandoned
- partial / interrupted run

`distill.py` 只把真正的 JSON boolean `true` 计为 sign-off。
字符串 `"true"` 不算。

---

## Domain key_metrics Fields

| Domain | `key_metrics` fields |
|---|---|
| architecture | `selected_arch`, `estimated_mhz`, `estimated_area_um2` |
| compiler | `isa_tests_passed`, `abi_compliant`, `regression_pass_rate` |
| dft | `scan_coverage_pct`, `atpg_fault_coverage_pct` |
| firmware | `build_pass`, `flash_size_kb`, `bsp_tests_passed` |
| formal | `proved`, `failed`, `unknown` |
| fpga | `lut_count`, `fmax_mhz`, `timing_met` |
| hls | `latency_cycles`, `dsp_count`, `ii_achieved` |
| infrastructure | `tools_detected`, `tools_missing`, `wrappers_deployed`, `mcp_servers_configured`, `module_system`, `tool_versions` |
| memory-ip | `memory_instances`, `total_memory_area_um2`, `worst_access_time_ns`, `view_qa_errors`, `projected_repair_yield_pct` |
| pd | `wns_ns`, `drc_violations`, `lvs_errors`, `gds_area_um2` |
| rtl-design | `lint_errors`, `cdc_violations`, `synth_check_pass` |
| soc | `ip_blocks_integrated`, `simulation_pass`, `memory_map_conflicts` |
| sta | `setup_wns_ns`, `hold_wns_ns`, `tns_ns`, `failing_paths` |
| synthesis | `wns_ns`, `cells`, `area_um2`, `lec_unmatched` |
| verification | `functional_coverage_pct`, `regression_failures`, `assertions_triggered` |

---

## Directory Layout（目录结构）

```text
memory/
├── README.md                    ← 本文件
├── designs/                     ← 每设计 QoR 历史（未来使用）
│   └── .gitkeep
├── architecture/
│   ├── knowledge.md             ← Tier 2：seeded domain knowledge
│   ├── experiences.jsonl        ← Tier 1：第一次运行时创建
│   └── run_state.md             ← active run identity，session start 时创建
├── compiler/
├── dft/
├── firmware/
├── formal/
├── fpga/
├── hls/
├── infrastructure/             ← opt-in，按环境分 key
├── memory-ip/
├── pd/
├── rtl-design/
├── soc/
├── sta/
├── synthesis/
└── verification/
```

### Infrastructure memory（opt-in，按环境分 key）

`infrastructure` domain 的 Memory **默认关闭**。

只有以下任一条件满足时，infrastructure-orchestrator 才写
`experiences.jsonl`：

- `design_state.pipeline_config.track_infrastructure == true`
- invocation 带 `--track-memory`

默认关闭的原因是：

- Infrastructure 状态强依赖当前机器
- Lockfile 仍然是精确版本的主要 source of truth
- 只有 tool-version mismatch 导致反复跨 session debugging 时，
  持久化这类经验才真正有价值

启用后，每条 record 带环境 fingerprint：

- `host`
- `os`
- `os_version`
- `arch`

以及：

`key_metrics.tool_versions`

Record 是 **environment-keyed**。
读取时优先使用
`environment.host/os`
与当前机器匹配的记录，因为版本与 quirk 往往无法跨主机直接迁移。

---

## Design State

`design_state.json`
位于当前 working directory，
是所有 Orchestrator 共享的跨 domain 状态文件。

它持久保存：

- Product spec
- Interface
- Constraint
- 各 domain 输出
- Bug/fix handoff
- Approval 状态
- Execution history

全部 16 个 Orchestrator 都在 session start
（读取 `knowledge.md` 之后）读取它，
并在 session end 与
`experiences.jsonl`
一起执行原子 read-modify-write。

### 主要顶层字段

- `spec`
  — 原始及结构化 product specification，由 architecture 写入

- `interfaces`
  — AXI/协议 interface list，由 architecture 写入

- `constraints`
  — timing、area、power 等共享 target，由 architecture 或用户写入

- `architecture`、`rtl`、`synthesis`、`sta`、`pd` 等
  — 每 domain 的 sign-off state

- `history[]`
  — append-only execution trace。
  从 format_version 1.3 开始是**每 stage 一条**，不再是每 run 一条。

每个 history entry 包含：

```text
timestamp
agent
stage
decision
confidence
failure_class
retry_strategy
suggested_next_step
reason
constraint_ref
```

其中：

- `decision`：
  `proceed | escalate | abandoned | await_approval`

- `confidence`：
  `high | medium | low`

- `retry_strategy`（format_version 1.5+）：
  `none | regenerate | refine | escalate`

- `suggested_next_step`：
  `proceed | loop_back_to:<stage> | retry_stage | escalate | abandon`

- `fix_requests[]`
  — verification/formal 发现 DUT bug 时写入的结构化 RTL fix request；
  RTL Orchestrator 消费，Pipeline Orchestrator 负责 dispatch。
  从 format_version 1.2+ 支持。

- `cross_domain_iteration_count`
  — Pipeline Orchestrator 驱动的 verification↔RTL feedback cycle 计数。
  默认达到 3 次后升级。

- `pipeline_config.checkpoints`
  — 需要人类批准才能宣告 sign-off 的 stage 名列表
  （format_version 1.3+）。

  缺失或 `[]` 表示完全自动。

  示例：

```json
["arch_signoff", "rtl_signoff", "signoff"]
```

该字段由用户写，
Orchestrator 绝不覆盖。

- `approved_checkpoints[]`
  — 用户已经批准的 checkpoint：

```json
{
  "stage": "<name>",
  "approved_at": "<ISO-8601>",
  "approved_by": "user"
}
```

- `pending_approval`
  — 当需要人工决策时非 null。

`type` 区分：

1. `"checkpoint"`
   — domain Orchestrator 在自己的 sign-off boundary 设置的主动 gate

2. `"constraint_gap"`
   — stage-entry validation 发现 required constraint 缺失

3. `"escalation"`
   — failure-driven escalation，
   **只由 pipeline-orchestrator 设置**

Domain Orchestrator 因 loop cap 耗尽或上游 fault 而升级时，
只在 terminal `history[]` 记录，
不设置 escalation 类型的 pending_approval。

附加字段：

```text
stage
agent
reason
fix_request_id
last_summary
requires_user
```

### `failure_class`

`history[]` 支持：

```text
none
functional
timing
power_area
drc_lvs
coverage_gap
connectivity
tool_error
spec_gap
resource_limit
```

该枚举与
`fix_request.failure_class`
不同；后者只用于 verification/formal 的 root cause。

### format_version 层级

- **`"1.1"`**
  — 增加 `fix_requests[]`、`cross_domain_iteration_count`

- **`"1.2"`**
  — history 增加标准化
  `confidence/failure_class/suggested_next_step`

- **`"1.3"`**
  — 增加
  `pipeline_config.checkpoints`、
  `approved_checkpoints[]`、
  `pending_approval.type/stage/agent`；
  每 stage 写一条 history

- **`"1.4"`**
  — 增加 authoritative `constraints` object、
  stage-entry validation、
  `pending_approval.type:"constraint_gap"`

- **`"1.5"`**
  — 每个 history entry 增加
  `retry_strategy`；
  escalation 必须包含
  `failure_class` + actionable guidance

当 `fix_requests[]` 有
`status=open`
的条目时，
`chip-design-meta` 的
`pipeline-orchestrator`
负责把它路由给 RTL Orchestrator，
修复后再重新运行 verification。

---

## Atomic Write Protocol（原子写入与多写者保护）

为了同时防止：

- Partial write
- Concurrent Orchestrator lost update

对 `design_state.json`
采用以下协议：

1. 获取独占锁，例如 `flock` 或应用级 mutex
2. 读取 `design_state.json`，不存在则使用 `{}`
3. 记录 version/checksum
4. 修改对象
5. 写入唯一临时文件，例如：

```text
design_state.<pid>.<uuid>.tmp
```

6. 再次检查原文件 version/checksum 是否变化
7. 如果变化，重新执行整个 RMW
8. 仍持锁时把临时文件 rename 为 `design_state.json`
9. Rename 完成后释放锁

如果多个 writer 可能同时写
`experiences.jsonl`，
upsert 操作也使用同样策略。

---

## How Orchestrators Use This（Orchestrator 如何使用 Memory）

### Session start

第一 stage 前读取：

```text
<MEM>/<domain>/knowledge.md
<MEM>/<domain>/run_state.md
```

`knowledge.md`
提供已知 failure pattern 与 tool flag。

如果 `run_state.md` 存在，
它可能表示上次流程被中断，
应据此判断是否 resume。

### Before first stage

写入：

```text
<MEM>/<domain>/run_state.md
```

内容包括：

- `run_id`
- `design_name`
- `tool`
- `start_time`
- `last_stage`

每 stage 完成后更新
`last_stage`。

### Per stage

按 `run_id`
upsert 一条：

```text
<MEM>/<domain>/experiences.jsonl
```

运行过程中：

```json
"signoff_achieved": false
```

只有最终 sign-off 的全部判据真实通过后，才允许把该布尔字段更新为成功状态；任何 partial、escalated、abandoned 或 unverified 运行都必须继续保持 `false`。

同一 `run_id`
**不得追加第二行**；
应覆盖原有那一行。

### Optional — claude-mem index

如果 session 中存在：

`mcp__plugin_ecc_memory__add_observations`

可把 applied fix 同时写入：

`chip-design-<domain>-fixes`

作为额外跨 session 搜索索引。

如果工具不存在，
静默跳过。

**JSONL 才是 canonical record**；
claude-mem 只是辅助索引。

---

## Distilling New Knowledge（蒸馏新知识）

积累足够多运行记录后
（默认阈值 5 条），
把新的经验合并回
`knowledge.md`：

```text
/chip-design-infrastructure:memory-keeper --domain synthesis
/chip-design-infrastructure:memory-keeper --all --min-records 10
```

Memory-Keeper 会：

1. 读取 JSONL record
2. 找出新的 issue/fix pattern
3. 找出新的 tool flag
4. 与已有 knowledge 比较
5. 在不丢弃仍然有效旧内容的前提下更新相关 section

---

## QoR Trend Analysis（QoR 趋势分析）

使用
`tools/qor_trends.py`
跟踪同一 design 多次运行的关键指标。

```bash
# 查看 aes_core 在所有 domain 的文本趋势
python3 tools/qor_trends.py --design aes_core

# 只看 synthesis WNS，并自动检测 regression
python3 tools/qor_trends.py --design aes_core --domain synthesis --metric wns_ns

# 保存 matplotlib 图
python3 tools/qor_trends.py --design aes_core --plot --output aes_core_qor.png

# 对比 sky130 与 gf180mcu 的 area/timing
python3 tools/qor_trends.py --design aes_core --domain synthesis --group-by pdk

# 同一个 design/PDK 比较 Yosys 与 DC
python3 tools/qor_trends.py --design aes_core --pdk sky130 --group-by tool --plot
```

当指标向错误方向变化时会自动触发 regression alert，例如：

- WNS 变差
- Coverage 下降

---

## Semantic / Keyword Experience Search（语义 / 关键词经验搜索）

`tools/experience_search.py`
可以根据自然语言 query
对过去的 experience record 做相关性排序。

例如：

> 以前 sky130 的 WNS 问题是怎么解决的？

这样 Orchestrator 无需每次读取完整 JSONL。

它复用统一的 Memory-root resolver，
以及其他工具相同的
`load_records` / filter helper，
因此读取到的就是 Orchestrator 实际写入的内容。

### Backend

两个 backend 共用同一稳定 contract。

#### keyword（默认，始终可用）

纯 Python stdlib 实现：

- TF-IDF
- cosine similarity

主要对以下自由文本字段排名：

- `issues_encountered`
- `fixes_applied`
- `notes`

优点：

- 任意 dataset size 都可工作
- 无 index
- 无外部 dependency

#### embedding（可选，默认休眠）

只有两个条件同时满足才启用：

1. 通过 `get_embedding_backend()`
   接入 embedding library
2. 当前 domain record 数量达到
   `--min-records`
   （默认 **50**）

Vector cache 使用 Python stdlib
`sqlite3`：

```text
<domain>/.experience_index.sqlite3
```

以 record content hash 作为 key，
因此 re-embedding 可以增量进行。

如果：

- 未达到 threshold
- backend 不存在

则透明回退 keyword，并返回：

```json
{
  "backend": "keyword",
  "fell_back": true
}
```

### CLI 示例

```bash
# Keyword search，任何规模都可用
python3 tools/experience_search.py --domain synthesis \
  --query "what fixed WNS on sky130" --pdk sky130

# JSON 输出，MCP Server 也使用同一 shape
python3 tools/experience_search.py --domain synthesis \
  --query "wns closure" --json

# 预热/刷新 embedding cache
# 没接 embedding backend 时为 no-op
python3 tools/experience_search.py --domain synthesis --reindex
```

### MCP Memory Server

`plugins/infrastructure/tools/mcp-memory.py`
通过 MCP stdio 暴露相同查询能力：

`query_experiences`

Protocol 与 EDA tool adapter 一致：

`2024-11-05`

配置模板：

`plugins/infrastructure/mcp/mcp-memory.json`

Server name：

`chip-design-memory`

把其中的
`mcpServers`
block 粘贴进：

`.claude/settings.json`

并替换 repo path placeholder。

### Optional Orchestrator Read Path

如果
`query_experiences`
MCP 可用，
Orchestrator 可以在 session start 调用它。

建议参数：

- 当前 `domain`
- 当前目标/问题作为 `query`
- 已知 filter：
  - `pdk`
  - `tool_used`
  - `design_name`

这只用于**增强**，
永远不能替代
`knowledge.md`
的读取。

如果工具不存在，
Orchestrator 按原流程继续，
只使用 `knowledge.md`。

全部 16 个 Orchestrator
都携带这条可选说明。
