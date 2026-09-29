# 后续工作

以下条目来自两级 Agent Memory 系统实现过程中暂缓的事项（参见 `memory/README.md`）。
初版 Memory 系统发布后，应将这些内容继续作为后续 issue 跟踪。

## 1. Memory-Keeper Skill ✓ 已实现

**状态：** 已发布 —— `plugins/infrastructure/skills/memory-keeper/`

该 Skill 会周期性地把 `memory/<domain>/experiences.jsonl`
中的运行记录蒸馏为更新后的 `memory/<domain>/knowledge.md` 摘要。

当前实现包括：

- `SKILL.md` —— 三阶段 Agent Skill：
  `load_experiences → distil_knowledge → report`
- `distill.py` —— CLI 辅助工具：解析 JSONL，提取 issue/fix 对、指标范围和工具参数候选，
  并输出结构化 JSON 摘要供 Agent 使用
- 可通过
  `/chip-design-infrastructure:memory-keeper --domain <name>`
  或 `--all` 调用
- 阈值保护：当某个 domain 的记录数少于 N（默认 5）时跳过

## 2. Experiences 语义搜索 ✓ 已实现（分阶段）

**状态：** 已发布（分阶段）——
`tools/experience_search.py`、
`plugins/infrastructure/tools/mcp-memory.py`
以及
`plugins/infrastructure/mcp/mcp-memory.json`。

新增 MCP Memory Server
（`chip-design-memory`，工具 `query_experiences`），
允许 Orchestrator 根据相似度检索历史 experience record，
而不是每次读取整个文件。

例如：

> “之前在 sky130 上遇到 WNS 问题时，哪种修复方法有效？”

实现采用 **fallback-first** 策略，以同时满足两个目标：

1. 只有当 experience 数量足够大时才值得使用 embedding，目标约为每个 domain 50 条记录
2. 仓库保持零依赖、仅使用 Python stdlib 的约定

实现细节：

- **默认 keyword backend** —— 使用纯 stdlib 的 TF-IDF + cosine，
  对自由文本字段进行排序。
  无论 dataset 大小都可使用，不需要 index 或第三方依赖。
- **可选 embedding backend** —— 接口已保留，但默认不启用。
  只有在通过 `get_embedding_backend()` 提供 embedding library，
  且 domain 中记录数 ≥ `--min-records`（默认 50）时才启用。
  Vector 缓存到 stdlib `sqlite3` index 中，
  以 record content hash 作为 key；
  使用 `--reindex` 可增量重建 embedding。
  如果低于阈值或 backend 不存在，则自动回退到 keyword，
  并标记 `fell_back: true`。
- 所有 16 个 Orchestrator 都带有可选的 session-start 查询说明：
  当 MCP 工具可用时调用它，否则继续使用 `knowledge.md`。

原先考虑过以下方案，但为了保持零依赖约定而**放弃**：

- ~~SQLite + sqlite-vec extension~~
  （sqlite-vec 是 native extension，不属于 stdlib）
- ~~Chroma 或 Qdrant（本地 Docker 容器）~~
- ~~托管服务：Pinecone、Weaviate Cloud~~

如果某个部署环境确实需要真正的 semantic ranking，
只需要实现 `get_embedding_backend`。

## 3. 跨设计 QoR 指标趋势 ✓ 已实现

**状态：** 已发布 —— `tools/qor_trends.py`

该报告工具会读取所有
`memory/<domain>/experiences.jsonl`，
针对指定设计输出 QoR 趋势表，并可选生成 matplotlib 图。

典型用途：

- Regression detection：当指标在多次运行中变差时标记告警
- PDK 对比：同一个 RTL 在 sky130 与 GF180 上比较 WNS/area，
  使用 `--group-by pdk`
- Tool 对比：同一个设计比较 Yosys 与 DC 综合面积，
  使用 `--group-by tool`

注意：
`tools/qor_trends.py` 会先应用 `--pdk` / `--tool` 过滤，
再执行 `--group-by`。
因此，如果同时指定：

```bash
--group-by pdk --pdk VALUE
```

或者：

```bash
--group-by tool --tool VALUE
```

最终只会剩一个 group，从而失去比较意义。

使用方法：

```bash
# 查看设计 aes_core 在所有 domain 中的文本趋势表
python3 tools/qor_trends.py --design aes_core

# 仅查看 synthesis domain 的 WNS 趋势
python3 tools/qor_trends.py --design aes_core --domain synthesis --metric wns_ns

# 保存 matplotlib 图
python3 tools/qor_trends.py --design aes_core --plot --output aes_core_qor.png
```

## 4. Infrastructure Orchestrator Memory ✓ 已实现

**状态：** 已发布 ——
`memory/infrastructure/`
以及 infrastructure-orchestrator 的 opt-in Memory 规则。

该功能会跨运行记录：

- 工具版本
- module 版本
- MCP / setup 配置

并存放到
`memory/infrastructure/`，
仍然遵循两级 Memory 模式。

之所以设计为 **opt-in，默认关闭**，是因为：

- infrastructure 状态依赖具体环境
- machine A 与 machine B 不等价
- 工具版本更适合由 lockfile 固定
- MCP 配置已经存在于 `.claude/settings.json`

启用方式：

- `design_state.pipeline_config.track_infrastructure == true`
- 或调用 Orchestrator 时加 `--track-memory`

否则不会访问
`memory/infrastructure/`。

记录采用 **environment-keyed** 方式，
环境 fingerprint 包括：

- `host`
- `os`
- `os_version`
- `arch`

这样不同机器的数据不会冲突。

`key_metrics.tool_versions`
会在 `environment_validation` 阶段保存每个工具的版本映射，
方便定位反复出现的 version mismatch。

该域已经完整接入 memory-keeper：

- `infrastructure` 已加入 `distill.py` 的
  `VALID_DOMAINS`
- 已加入 `METRIC_FIELDS`
- 已加入 Memory-Keeper Skill 的 Domains 表

因此，多次运行积累出的环境 quirks 可以被蒸馏到
`memory/infrastructure/knowledge.md`。

完整说明见：

- `memory/README.md` 中
  “Infrastructure memory (opt-in, environment-keyed)”
- infrastructure-orchestrator 中
  “Infrastructure Memory” 章节

## 5. 中央 Design State ✓ 已实现

**状态：** 已发布 —— 所有 16 个 Orchestrator 进入时读取
`design_state.json`，
退出时写回各自 domain 子对象，并追加 `history[]`。

Schema 覆盖：

- `spec`
- `interfaces`
- `constraints`
- `architecture`
- `rtl`
- `verification_status`
- `synthesis`
- `dft`
- `sta`
- `hls`
- `pd`
- `soc`
- `compiler`
- `firmware`
- `fpga`
- `environment`
- `tool_feedback`
- `pending_approval`
- `history[]`

以前每个 Orchestrator 只维护自己 session 内的 state object，
没有一个跨 Orchestrator 边界长期存在的共享 artifact。
因此下游 Agent 无法读取上游决策，
例如 RTL coding 无法查询 architecture trade-off 的理由。

现在引入持久化
`design_state.json`，
存放在工作目录。
每个 Orchestrator 进入时读取，退出时追加结果。

它取代了
`docs/MASTER_INDEX.md`
中记录的临时跨 Orchestrator handoff package。

### 最小字段

```json
{
  "spec": { "raw": "<natural language>", "structured": {} },
  "interfaces": [{ "name": "AXI3-lite", "width": 32, "role": "subordinate" }],
  "constraints": { "clk_mhz": 500, "area_um2": null, "power_mw": null },
  "rtl": { "top_module": null, "files": [], "lint_clean": false, "cdc_clean": false },
  "verification_status": { "coverage_pct": null, "signoff": false },
  "tool_feedback": [],
  "history": []
}
```

`history[]` 会记录：

- agent
- stage
- decision
- reason
- constraint reference

因此整个设计演进过程可以跨 session 追溯。

**以下条目的前置条件：** 6、8、9、11。

## 6. 持续验证闭环

**状态：已发布** ——
`plugins/meta/agents/pipeline-orchestrator.md`
以及
`design_state.json`
中的结构化 `fix_request` schema
（`format_version 1.1`）。

详见 `CHANGELOG.md`。

**前置条件：** 条目 5，
因为 fix request 的跨域 handoff 必须依赖 `design_state.json`。

## 7. Agent Contract 标准化

**状态：已发布** ——
全部 16 个 Orchestrator `.md`
现在每个 stage 都输出扩展的
`output_format`，
同时写入标准化 `history[]`。

`design_state.json` 的
`format_version`
升级到 `"1.2"`。

Canonical schema 位于：

`docs/MASTER_INDEX.md`

程序化 branching 决策表位于：

`plugins/meta/skills/pipeline-orchestration/SKILL.md`

已发布 schema：

```json
{
  "stage": "<stage_name>",
  "status": "PASS | FAIL | WARN",
  "confidence": "high | medium | low",
  "failure_class": "none | functional | timing | power_area | drc_lvs | coverage_gap | connectivity | tool_error | spec_gap | resource_limit",
  "qor": {},
  "issues": [{ "severity": "ERROR | WARN", "description": "...", "fix": "..." }],
  "suggested_next_step": "proceed | loop_back_to:<stage> | retry_stage | escalate | abandon",
  "output": {}
}
```

`confidence`
（`high|medium|low`）
用于 pipeline-orchestrator 判断是否自动继续或升级。

`failure_class`
用于 retry strategy 表。

`suggested_next_step`
替代旧的自由文本 `recommendation`，
使 Orchestrator 逻辑能够程序化执行。

## ~~8. Constraint Awareness~~ ✓ 已完成（format_version 1.4）

~~过去 constraint 主要以自然语言存在于 SKILL.md 中，
或者以 SDC、LEF 文件路径存在于 Orchestrator state。
Agent 会把固定约束值硬编码进规则，
因此一旦修改 clock target，就需要同步修改多个 Skill 文件。~~

在 `format_version 1.4` 中已经实现：

`design_state.constraints`
成为全部设计约束值的唯一可信来源。

11 个需要 constraint 的 domain Skill
全部改为引用：

`design_state.constraints.<key>`

而不再直接依赖硬编码值。
原有 literal 仍保留为文档化默认值。

Stage-entry validation 会在必需 key 缺失或为 null 时，
使用：

`pending_approval.type: "constraint_gap"`

停止流程。

`history[]` 中的
`constraint_ref`
用于标记每次 QoR 判断依赖哪个 constraint key。

详细内容见：

- `plugins/meta/skills/pipeline-orchestration/SKILL.md`
  的 Constraints Schema
- `CHANGELOG.md`

## 9. Architecture Exploration 改进

architecture Skill 已经要求生成 3 个候选：

- conservative
- balanced
- aggressive

并使用 trade-off matrix 进行比较。

当前不足在于：

- candidate 只存在于 session context
- 没有持久化
- 下游失败不能反向触发 architecture refinement

例如 synthesis 无法满足 timing 时，
不能自动携带 violation 返回 architecture 重新评估。

### 改进方向

- 把完整 trade-off matrix 保存到
  `design_state.json` 的
  `architecture.candidates[]`
  中，使下游 Agent 可以引用之前被拒绝的方案
- 增加 `refinement_needed` 标记：
  如果 synthesis 或 PD 写入：

  `design_state.architecture.refinement_needed = true`

  并附 reason，
  architecture-orchestrator 重新进入
  `perf_modelling`，
  以已保存 candidate 为起点，
  而不是完全从头生成
- 扩展
  `memory/architecture/experiences.jsonl`
  schema，记录：
  - `candidates_evaluated`
  - `winning_candidate_profile`

  用于跨设计学习

这样可以减少早期错误决策对后续流程的影响，
又不要求用户在初始 prompt 中一次性提供完美信息。

**前置条件：** 条目 5。

## ~~10. Structured Failure Handling~~ ✓ 已完成（format_version 1.5）

在 `format_version 1.5` 中已经实现：

每条 `history[]`
都包含一个 `retry_strategy`：

```
regenerate | refine | escalate | none
```

其值根据 `failure_class`
由
`plugins/meta/skills/pipeline-orchestration/SKILL.md`
中的权威表确定。

继续使用已有 10-value
`failure_class`
枚举，没有引入新的 taxonomy。

下面四个早期草案中的 class
被映射为 alias：

- `invalid_rtl` → `tool_error` / regenerate
- `verification_failure` → `functional` / refine
- `interface_mismatch` → `connectivity` / refine
- `incomplete_spec` → `spec_gap` / escalate

pipeline-orchestrator 的决策表现在会根据
`retry_strategy`
进行 branching。

发生 escalation 时，
必须同时包含：

- `failure_class`
- 用户需要补充什么信息才能继续

所有 15 个写 history 的 Orchestrator、
示例 fixture 和 CI
（`validate.yml`）
都已经更新。

原先的问题是：

~~所有失败都只进入 `issues[]`，
只有 `ERROR | WARN` severity。
Orchestrator 虽然有硬编码 loop-back，
但无法结构化区分“可恢复代码错误”和“规格不完整”。~~

### Failure class taxonomy

| Class | 定义 | 默认 retry strategy |
|---|---|---|
| `invalid_rtl` | 生成 RTL 中的 syntax、lint 或 CDC error | `regenerate` —— 带 error context 重新执行 rtl_coding |
| `verification_failure` | 仿真发现 DUT 功能 bug | `refine` —— 带 failing test + waveform 返回 rtl_coding |
| `interface_mismatch` | AXI/协议 violation 或 port width 冲突 | `refine` —— 针对具体 interface 问题重新执行 rtl_coding |
| `incomplete_spec` | 缺失或模糊需求阻塞流程 | `escalate` —— 停止并要求用户澄清 |

### Agent 行为变化

- 每个 FAIL status 必须标记上述四类之一
- 在 issue 上附带 `retry_strategy`
- 达到最大 loop 次数时，
  escalation message 必须包含 failure class
  以及用户需要提供什么信息才能解锁流程

**前置条件：** 条目 7，
因为需要 output contract 中的 `failure_class`。

## ~~11. Human-in-the-loop Control Points + Observability~~ ✓ 已完成（format_version 1.3）

过去只有：

- 初次 invocation
- 达到 max iteration 后 escalation

才有人机交互点。

没有可选 approval gate，
也没有结构化记录 Agent 为什么做某个决定。

现在已在 `format_version 1.3` 中实现：

- `pipeline_config.checkpoints`
- `approved_checkpoints[]`
- `pending_approval.type`
- 每 stage 一条 `history[]`
- 所有 15 个 domain Orchestrator 中的 checkpoint gate logic

详见：

`plugins/meta/skills/pipeline-orchestration/SKILL.md`
的 Approval Checkpoints 章节。

### Approval Checkpoints

可以在
`design_state.json`
中给指定 stage transition 加
`require_approval`。

触发后 Orchestrator 会：

1. 把人类可读摘要写到
   `design_state.pending_approval`
2. 停止执行
3. 等用户批准后继续

用户可以通过设置：

`design_state.approved_by_human: true`

或使用 `--approve`
恢复流程。

建议默认 checkpoint：

- `arch_signoff` 后 —— RTL coding 前
- `rtl_signoff` 后 —— verification/synthesis 前
- tape-out 前 —— PD 的 `signoff`

### Execution Trace

每个 stage 完成后，
向 `design_state.history[]`
追加：

```json
{
  "timestamp": "2026-04-18T10:00:00Z",
  "agent": "architecture-orchestrator",
  "stage": "arch_signoff",
  "decision": "proceed",
  "reason": "Balanced candidate meets timing with >20% WNS headroom.",
  "constraint_ref": "clk_core_500MHz"
}
```

这样每个 decision 都可以追溯到对应输出，
无需重新播放完整 Agent 对话。

**前置条件：**

- 条目 5：`design_state.json`
- 条目 7：使用 confidence 判断是否需要 approval

## 12. 新的相邻 Agent Domain

下面这些领域与当前 16-plugin 流水线紧密相关，
但尚未覆盖。

每个领域都有独立：

- 专业方法
- toolchain
- sign-off 标准

> **已实现：**
> Memory IP Design 原本是一个未明确列出的缺口，
> 现在已经作为第 16 个插件
> `chip-design-memory-ip`
> 发布。
> 它负责 memory macro selection、array architecture、
> redundancy/repair 和 view QA。
> MBIST 插入仍归 DFT，
> floorplan 归 PD，
> timing sign-off 归 STA。

| Domain | 原因 | 主要工具 |
|---|---|---|
| **Power Intent / UPF** | 多电压、低功耗设计，包括 UPF/CPF 编写、power-domain verification、isolation/retention cell 插入。移动/IoT 芯片通常必需，目前 RTL/Synthesis/PD Agent 都没有完整覆盖。 | Synopsys MVSIM、Cadence CPF tools、uvmf-power |
| **Silicon Validation / Debug** | Post-silicon failure analysis、ATE interface bring-up、scan dump triage、silicon characterization。现有 Agent 基本未覆盖。 | Teradyne UltraFLEX、Advantest V93000、内部 ATE scripts |
| **Package & Chiplet / 2.5D-3D** | Die-to-die interface（UCIe、HBM）、bump/RDL floorplan、package-level SI/PI。与芯片内部 PD 是不同问题。 | Cadence Sigrity、Synopsys 3DIC Compiler、KiCad |
| **Security / Hardware Roots-of-Trust** | Side-channel analysis、fault injection modeling、secure boot ROM、PUF integration。横跨 RTL/firmware，但适合单独 specialist Agent。 | ChipWhisperer、SideChannelMarvels、Synopsys DesignWare Security |
| **NoC / Interconnect Design** | NoC topology exploration、latency/bandwidth modeling、flit-level simulation。目前隐含在 SoC Integration 内，但复杂度足以独立。 | gem5 network mode、Noxim、OpenSoC Fabric |
| **Emulation Platform（ZeBu/Palladium）** | Hardware emulation bring-up 与 FPGA prototyping 不同：partitioning、transaction interface、tool flow 都不一样。 | Synopsys ZeBu、Cadence Palladium、Mentor Veloce |
| **AMS Integration** | Analog IP（PLL、ADC、LDO、SerDes）qualification、behavioral/Verilog-A model 生成、digital co-simulation，以及 analog peripheral firmware bring-up。定位为 integration Agent，不尝试端到端自动完成完整模拟闭环。 | ngspice、Xyce、Xschem、Spectre（仅 behavioral model generation） |

**建议优先级：**

1. Power Intent / UPF
2. Silicon Validation
3. AMS Integration

前两项能直接补齐现有流程最明显的空缺。
AMS Integration 对包含大量 analog IP 的 SoC 也很有价值。
其他 domain 属于更长期扩展。

## 13. Domain Breakdown：子 Agent 专业化

若干现有 Agent 覆盖范围较大，
进一步拆分成专门子 Agent 可以：

- 提高并行性
- 减少 context-window 压力
- 让 sign-off 标准更明确

中央 Design State（条目 5）
是清晰 sub-agent handoff 的前提。

### 建议拆分

**Physical Design → 3 个 sub-agent**
（最高优先级，当前覆盖面最广）

- `pd-floorplan`：
  I/O placement、macro placement、power-grid planning，
  utilization target 70–80%
- `pd-implementation`：
  Placement、CTS（skew <150 ps）、routing、DRC/LVS clean
- `pd-signoff`：
  Antenna fix、fill insertion、GDS export、tape-out checklist

**Verification → 3 个 sub-agent**
（Design State 完成后）

- `verification-tb`：
  UVM TB architecture、agent design、scoreboard、coverage-model definition
- `verification-regression`：
  test-plan execution、constrained-random stimulus、coverage closure（≥95%）
- `verification-emulation`：
  FPGA/emulator prototype 上 firmware-driven verification

**Firmware → 3 个 sub-agent**
（Design State 完成后）

- `firmware-bsp`：
  BSP、linker script、startup code、peripheral driver
- `firmware-rtos`：
  FreeRTOS/Zephyr port、task design、IPC primitive
- `firmware-bringup`：
  chip bring-up script、JTAG/UART debug、post-silicon smoke test

**暂不拆分：**
STA 与 DFT。
目前已经足够聚焦，
继续拆分带来的 overhead 大于收益。

### 更细粒度拆分的优点

| # | 优点 |
|---|---|
| 1 | SKILL.md 更聚焦，一个文件一个明确职责，更容易维护 |
| 2 | 单次运行 context 更小，可以给设计 artifact 留出更多 token |
| 3 | 独立 sub-agent 可以并行运行 |
| 4 | 更容易针对单一工具做深入集成 |
| 5 | 每个 Agent 的 sign-off gate 更清晰 |

### 更细粒度拆分的缺点

| # | 风险 |
|---|---|
| 1 | Cross-agent state 爆炸；没有中央 Design State 时 handoff 很容易丢信息 |
| 2 | Orchestration overhead 增加，parent 需要管理更多 child 和更多 failure mode |
| 3 | Shared context 会被多个 Agent 重复加载 |
| 4 | Marketplace 中 20+ entry 会增加用户选择成本 |
| 5 | 更多 plugin.json、SKILL.md 和 Memory 目录需要同步维护 |

**所有拆分的前置条件：**
条目 5 的中央 Design State 必须先完成，
否则 sub-agent 之间很容易丢 artifact 和状态。

## 14. 多 Servicer Fix Dispatch（`route_to`）

当前 pipeline-orchestrator 的
`dispatch_to_producer`
总是只调用一个 producer：

RTL Orchestrator。

具体位置：

`plugins/meta/agents/pipeline-orchestrator.md`

中的 `dispatch_to_producer`。

现阶段这是合理的，
因为 RTL 是唯一真正负责“修复”的 domain：

- verification/formal 负责发现问题
- fix_request 最终都返回 RTL
- re-validation 已经根据
  `fix_request.created_by`
  返回原始检测方
  （`verification-orchestrator` 或 `formal-orchestrator`）

Schema 中已经预留
`route_to`
字段，
作为可选且 forward-compatible 的 hint，
默认 servicer 为 `rtl-design`。

定义位置：

- `docs/design_state.schema.json`
  的 `$defs.fixRequest.route_to`
- `plugins/meta/skills/pipeline-orchestration/SKILL.md`
  的 fix_request Schema

该字段目前只被文档化，
dispatch logic 还没有真正使用它，
所以未来启用时无需 schema migration。

同系列
`analog-chip-design-agents`
仓库已经实现完整模式：

pipeline-orchestrator 会根据
`route_to`
把 open fix 分发到多个 servicer domain：

- `circuit-design`
- `behavioral-modeling`
- `custom-layout`
- `em-modeling`

然后再根据 `created_by`
返回原始检测方 re-validate。

这可以作为数字芯片版本的参考实现。

### 什么时候实现

当 digital pipeline 新增更多真正能够**解决** fix 的 domain 时再实现。

可能的候选包括：

- synthesis：constraint / UPF fix
- PD：DRC/LVS/floorplan fix
- 条目 12 中新增的专业 domain

在那之前，
multi-target dispatch 只会增加没有实际 target 的 scaffolding。

### 实现时需要做的工作

- 让 `dispatch_to_producer` 读取
  `fix_request.route_to`
  并启动对应 servicer Orchestrator
- `route_to` 缺失时继续默认 `rtl-design`
- 等 servicer 集合固定后，
  在 `docs/design_state.schema.json`
  中把 `route_to` 限制为 enum
- verification/formal 以及未来 detector
  在问题属于非 RTL domain 时写入对应 `route_to`
- 增加 positive/negative fixture，
  覆盖每个 route target
- 扩展 `validate.yml`
  的 schema 检查

**前置条件：**

- 条目 12 和/或 13：需要有额外 fix-servicer domain
- 条目 5：中央 Design State 用于跨域 handoff
