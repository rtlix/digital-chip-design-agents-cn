---
name: pipeline-orchestration
description: >
  芯片设计流水线的跨领域闭环编排。提供 fix_request 协议、迭代上限逻辑、
  escalation 模板，以及把 verification/formal 失败路由给 RTL Orchestrator 再返回验证端的
  dispatch 模式。适用于驱动 verification↔RTL 闭环反馈。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill: Pipeline Orchestration（流水线编排）

## Invocation

- **用户直接提出 pipeline-loop 任务**：立即启动
  `digital-chip-design-agents:pipeline-orchestrator`，传入完整请求和所有可用上下文。
  不要直接执行 stage。
- **在另一个 Orchestrator 内被调用**：读取 `design_state.json`，
  汇总 open 的 `fix_requests[]` 后返回；不要再启动 subagent（防递归）。

## Purpose

本 Skill 定义 verification↔RTL 的闭环反馈协议。Simulation 或 formal verification
发现 DUT bug 后，必须以机器可执行形式传递给 RTL Orchestrator，并不断迭代，
直到 bug 修复或达到 iteration cap。

协议包含三个参与方：

| Participant | Role |
|---|---|
| **verification-orchestrator / formal-orchestrator** | 发现 bug；向 `design_state.fix_requests[]` 写入 `status=open` 的 `fix_request`，并以 `decision=escalate` 结束。 |
| **rtl-design-orchestrator** | 读取 open `fix_request`，设置 `status=claimed`；修改 RTL；完成后写 `status=fixed` 和 `rtl_response`。 |
| **pipeline-orchestrator** | 检测 open request；分配 `pipeline_session_id`；顺序 dispatch RTL 再 re-verification；执行可配置迭代上限（默认 3，由 `pipeline_config.max_cross_domain_iterations` 控制）；divergence 只在当前 session 内判断；sign-off 时归档 resolved request；超过上限时通过 `pending_approval` 升级给用户。 |

## Domain Rules

### fix_request Schema (authoritative)

`design_state.fix_requests[]` 中的全部条目必须符合以下 schema。
机器可读 companion 是 `docs/design_state.schema.json`（JSON Schema Draft 2020-12），
CI 会用它验证 fixture；其中的 enum、required field 以及下文
`failure_class → retry_strategy` 映射才是权威机器编码。

```json
{
  "id": "fr_<pipeline_session_id>_<YYYYMMDD>_<HHMMSS>_<seq>",
  "created_at": "<ISO-8601>",
  "updated_at": "<ISO-8601>",
  "created_by": "verification-orchestrator | formal-orchestrator",
  "failure_class": "functional | protocol | coverage_gap | formal_cex",
  "retry_strategy": "refine",
  "test_name": "<directed test or property name>",
  "property_or_assertion": "<assertion id or null>",
  "seed": 0,
  "waveform_path": "<path or null>",
  "log_path": "<path or null>",
  "suspected_rtl": {
    "module": "<module name>",
    "signal": "<signal or null>",
    "file": "<rtl/path.sv or null>",
    "line_range": [0, 0]
  },
  "summary": "<one-line bug description>",
  "expected_behavior": "<spec excerpt or null>",
  "observed_behavior": "<observed RTL behaviour>",
  "session_id": "<pipeline_session_id or null>",
  "status": "open | claimed | fixed | abandoned",
  "rtl_response": null,
  "history": []
}
```

> **保留字段——`route_to`（可选）。**
> Schema 接受一个可选 `route_to` 字符串，用来指明负责修复的 servicer domain，
> 默认 `rtl-design`。当前它只是**面向未来的兼容脚手架**：
> pipeline-orchestrator 的 `dispatch_to_producer` 仍固定调用 RTL Orchestrator，
> producer 无需设置它。预留该字段是为了未来增加 multi-servicer dispatch 时
> 不必再迁移 schema，也与 analog pipeline 的模式保持一致。

`rtl_response` 由 rtl-design-orchestrator 在关闭 request 时填写：

```json
{
  "fixed_at": "<ISO-8601>",
  "diff_summary": "<one-paragraph description of changes>",
  "files_changed": ["rtl/path.sv"],
  "commit_ref": null
}
```

`fix_request.history[]`：每次状态转换一条记录：

```json
{
  "timestamp": "<ISO-8601>",
  "agent": "<agent name>",
  "from_status": "<previous status>",
  "to_status": "<new status>",
  "note": "<optional one-liner>"
}
```

### Ownership rules

- `rtl-design-orchestrator` 拥有 `open→claimed` 和 `claimed→fixed|abandoned` 状态转换。
- 只有 `rtl-design-orchestrator` 可以把 `claimed` 改为 `fixed` 或 `abandoned`。
- 只有 `pipeline-orchestrator` 可以设置 `cross_domain_iteration_count`、
  `pipeline_session_id`、`pipeline_config`，并把 resolved entry 移入
  `archive_fix_requests[]`。
- Domain Orchestrator **只允许在两个 gate 设置 `pending_approval`**：
  自己 sign-off stage 的 `type:"checkpoint"`，
  以及 stage-entry constraint validation 的 `type:"constraint_gap"`。
  `type:"escalation"` 仅由 `pipeline-orchestrator` 设置。
  Domain Orchestrator 因其他原因升级（loop cap 用尽、上游 artifact 有问题）时，
  只写 terminal `history[]`，不设置 `pending_approval`。
- `approved_checkpoints[]` 由用户写入，或者由执行明确批准指令的 Orchestrator 写入；
  所有 Orchestrator 只读取它进行 sign-off gate 判断。
- 所有 Agent 都可向 `fix_request.history[]` 追加 entry，但不得覆盖其他 Agent 的记录。

### Iteration cap

`design_state.json` 中的 `cross_domain_iteration_count` 记录当前 pipeline session
总共执行了多少次 verification↔RTL dispatch cycle。

上限由 `pipeline_config.max_cross_domain_iterations` 控制，缺失时默认 3。
判定采用 **`>= max_cross_domain_iterations`**，而不是 `>`。
计数一旦达到或超过上限，就立即写入 `pending_approval` 并退出，
避免 off-by-one 再多跑一轮：

```json
{
  "pending_approval": {
    "type": "escalation",
    "stage": null,
    "agent": "pipeline-orchestrator",
    "reason": "fix_request loop exceeded 3 cross-domain iterations",
    "fix_request_id": "<id>",
    "last_summary": "<last rtl_response.diff_summary>",
    "requires_user": true
  }
}
```

用户需要检查 escalation，手工修 RTL 或调整 testbench，
然后在重新调用 pipeline-orchestrator 前：
- 将 `pending_approval` 设为 `null`
- 将 `cross_domain_iteration_count` 重置为 0

如果确实需要更多自动迭代，可以显式提高
`pipeline_config.max_cross_domain_iterations`。

### Pipeline session fields

以下 `design_state.json` 顶层字段由 pipeline-orchestrator 及相关基础设施管理：

- **`pipeline_session_id`**：
  格式 `"ps_<YYYYMMDD>_<HHMMSS>"` 或 null。
  进入闭环时设置，成功 sign-off 后清空。
  Divergence 与 archive 都只对当前 session 生效，旧 session entry 不参与 divergence 判断。

- **`pipeline_config`**：
  用户可调整的 pipeline 设置。首次运行可写默认值；已有用户值绝不能覆盖。
  - `max_cross_domain_iterations`：整数，默认 3
  - `checkpoints`：string array，默认 `[]`。列出 domain 在宣告 sign-off 前必须人工批准的 stage。
    空数组表示完全自动，保持 backward compatibility。
    示例：`["arch_signoff","rtl_signoff","signoff"]`。
    该字段由用户写，domain Orchestrator 只读。

- **`approved_checkpoints[]`**：
  用户已经批准的 stage：
  `{"stage":"<stage name>","approved_at":"<ISO-8601>","approved_by":"user"}`。

- **`archive_fix_requests[]`**：
  已完成 pipeline session 的 resolved fix_request。
  由 pipeline-orchestrator 在成功 sign-off 时把当前 session 的条目移到这里。
  Domain Orchestrator 不写该数组。

### Constraints Schema (authoritative)

`design_state.constraints` 是所有 domain Orchestrator 的设计意图参数唯一可信来源。
Schema 只在这里定义一次；各 domain `SKILL.md` 引用对应 key，并说明自己的 fallback。

```json
"constraints": {
  "clock": {
    "clk_mhz": null,
    "clk_uncertainty_ps": null
  },
  "pvt_corners": [
    { "name": "ss_setup", "process": "SS", "voltage_v": null, "temp_c": null, "checks": ["setup"] },
    { "name": "ff_hold",  "process": "FF", "voltage_v": null, "temp_c": null, "checks": ["hold"] }
  ],
  "timing": {
    "wns_ns_target": 0,
    "tns_ns_target": 0,
    "fanout_max": 32,
    "skew_ps_max": 100,
    "transition_ps_max": 200,
    "insertion_delay_ps_max": 500
  },
  "area": {
    "area_um2": null,
    "utilization_pct_target": 75,
    "utilization_pct_max": 85
  },
  "power": {
    "power_mw": null,
    "leakage_pct_max": 15,
    "ir_drop_pct_max": 5,
    "gating_coverage_pct_min": 60,
    "activity_factors": { "default": 0.15, "high": 0.40 }
  },
  "coverage": {
    "functional_pct": 100,
    "line_pct": 95,
    "branch_pct": 90,
    "toggle_pct": 85,
    "fsm_state_pct": 100,
    "fsm_transition_pct": 95,
    "assertion_pct": 100
  },
  "dft": {
    "saf_coverage_pct": 99,
    "transition_coverage_pct": 95,
    "cell_aware_coverage_pct": 95,
    "bridging_coverage_pct": 90,
    "mbist_coverage_pct": 99,
    "chain_balance_pct": 5
  },
  "hls": {
    "target_ii": null,
    "target_latency_cycles": null,
    "cosim_tolerance_pct": 5
  },
  "memory_ip": {
    "vmin_margin_mv": 50,
    "repair_yield_pct_min": 99,
    "ecc_required": false,
    "fit_target_fit_per_mb": 100,
    "max_aspect_ratio": 4.0,
    "retention_required": true
  },
  "fpga": {
    "lut_util_pct_max": 70,
    "bram_util_pct_max": 80,
    "dsp_util_pct_max": 80
  }
}
```

非 null 值是**文档化默认值**，与现有 Skill 中历史 hardcoded literal 保持一致。
对于需要 design-specific constraint 的 domain，null 值必须由用户提供。

#### Required vs. optional constraints

| Constraint key | Required by（缺失/null 时 hard-fail） |
|---|---|
| `clock.clk_mhz` | architecture, rtl-design, synthesis, sta, pd, soc, fpga |
| `area.area_um2` | architecture, synthesis, pd |
| `power.power_mw` | architecture, synthesis, pd |
| `pvt_corners`（至少一项 `voltage_v/temp_c` 非 null） | sta, pd |
| `hls.target_ii` 或 `hls.target_latency_cycles`（至少一项非 null） | hls |

其他 key 均为 **optional**；缺失时采用 schema default，同时产生 WARN。

#### Stage-entry constraint validation rule

每个需要 constraint 的 domain Orchestrator，在**第一个消费设计约束的 stage**
执行以下规则。若 prompt 中传入 `fix_request.id`，说明处于 fix-request-servicing 模式，
则整个 constraint gate 跳过：

1. 读取 `design_state.constraints`；缺失按 `{}` 处理。
2. 对该 domain 的每个 required key：如果缺失或 null，执行原子 RMW 并设置：

```json
{
  "type": "constraint_gap",
  "stage": "<entry stage name>",
  "agent": "<this-orchestrator>",
  "reason": "required constraint <key> missing from design_state.constraints",
  "fix_request_id": null,
  "last_summary": "<comma-separated list of missing keys>",
  "requires_user": true
}
```

同时追加 history：
- `decision:"escalate"`
- `confidence:"high"`
- `failure_class:"spec_gap"`
- `suggested_next_step:"escalate"`
- `constraint_ref:"<missing key>"`

输出 gate message 后**停止**。

3. Optional 缺失项使用 schema default，并在 stage history `reason` 中写 fallback note。

**恢复方式：**
补齐 `design_state.constraints` 中缺失的 key，
设置 `pending_approval=null`，重新调用 Orchestrator。

#### Decision tagging via `constraint_ref`

任何 stage 如果用 constraint 判断 QoR，都应在对应 `history[]` entry 中设置
`constraint_ref`，使用 dot-path，例如
`timing.wns_ns_target`、`clock.clk_mhz`、`area.utilization_pct_max`。
一个 stage 依赖多个 key 时可用逗号分隔。其他 entry 保持 null。

#### Decision tagging via `retry_strategy`

每条 `history[]` 必须根据下节映射从 `failure_class` 推导 `retry_strategy`。
`failure_class:"none"`（PASS、`await_approval`）使用 `retry_strategy:"none"`。
Pipeline Orchestrator 会同时读取 `retry_strategy`、`confidence`、`suggested_next_step`
做程序化决策。

### Failure Classification & Retry Strategy

每个 failure 都要结构化分类，让 recovery 不依赖解析自由文本。

- `failure_class`：发生了什么
- `retry_strategy`：怎么恢复

`retry_strategy ∈ none | regenerate | refine | escalate`：

- **regenerate**：丢弃错误 artifact，从 clean state 重新执行生成 stage，携带 error log。
  典型场景：tool crash、malformed output、DRC/LVS、broken connectivity。
- **refine**：保留 artifact，针对具体 defect 带详细反馈增量修正，如 failing test + waveform、
  timing path、coverage hole、interface violation。
- **escalate**：自动流程无法改进，需要人工输入，如 ambiguous spec、iteration cap、resource limit。
- **none**：没有 failure，只与 `failure_class:"none"` 配对。

`retry_strategy` 是策略标签，`suggested_next_step` 是具体 action，两者互补。

#### Mapping (authoritative — `failure_class` → default `retry_strategy`)

| `failure_class` | `retry_strategy` | 理由 | legacy alias |
|---|---|---|---|
| `none` | `none` | 无 failure | — |
| `functional` | `refine` | 带 failing test + waveform 重跑 rtl_coding | verification_failure |
| `timing` | `refine` | 针对 failing path 优化 | — |
| `power_area` | `refine` | 针对超预算项优化 | — |
| `coverage_gap` | `refine` | 增加 targeted stimulus 关闭 hole | — |
| `connectivity` | `refine` | 针对 interface/connection 修正 | interface_mismatch |
| `drc_lvs` | `regenerate` | 从 clean state 重新 place/route | — |
| `tool_error` | `regenerate` | 同 stage 从头重跑 | invalid_rtl |
| `spec_gap` | `escalate` | spec 缺失/歧义 | incomplete_spec |
| `resource_limit` | `escalate` | iteration/memory 上限 | — |

Legacy alias 只是早期草案到 live enum 的映射，不引入第二套 taxonomy。
Verification/Formal 产生 fix_request 时，其 `retry_strategy` 固定为 `refine`。

#### Actionable escalation guidance

当 `retry_strategy=escalate` 或达到 max-iteration cap，
`reason` 必须同时包含 `failure_class` 和用户要提供什么才能解锁。

示例：
- spec_gap：澄清具体 ambiguous requirement，并给出预期 behavior/value。
- resource_limit：说明哪个 stage 达到 N 次 cap，并让用户选择放宽 constraint、提高 cap 或接受当前 QoR。

### format_version

`design_state.json` 版本层级：

- **1.1**：`fix_requests[]`、`cross_domain_iteration_count`
- **1.2**：history 增加 `confidence`、`failure_class`、`suggested_next_step`
- **1.3**：checkpoint/approval + per-stage history
- **1.4**：authoritative `constraints` + constraint validation + `constraint_gap`
- **1.5**：每条 history 增加 `retry_strategy`，escalation 带 actionable guidance

所有 Orchestrator：
- 缺失或版本 1.0–1.4 时升级到 1.5，不 downgrade 更高版本。
- 缺 `fix_requests/cross_domain_iteration_count` 按 `[]/0`。
- 旧 history 缺标准字段时兼容读取；缺 `retry_strategy` 时根据 mapping 推导。
- 缺 checkpoints/approved_checkpoints 时按空数组。
- 缺 pending_approval.type 时按 escalation。
- 缺 constraints 时按空 object；optional 用 default，required 按规则 halt。

### Approval Checkpoints

可配置 stage boundary 上的主动 human-in-the-loop gate，与 failure-driven escalation 分离。

#### Checkpoint configuration

```json
{
  "pipeline_config": {
    "checkpoints": ["arch_signoff", "rtl_signoff", "signoff"]
  },
  "approved_checkpoints": [
    { "stage": "arch_signoff", "approved_at": "<ISO-8601>", "approved_by": "user" }
  ]
}
```

默认 `checkpoints:[]`：完全自动。

#### Gate logic

设置 domain `signoff=true` 前：

1. Prompt 有 `fix_request.id` 时跳过 gate；repair loop 不被 checkpoint 阻塞。
2. 若当前 sign-off stage 在 checkpoints 中且未在 approved_checkpoints：
   设置 `pending_approval.type:"checkpoint"`，写 stage/agent/reason/last_summary；
   追加 `decision:"await_approval"` history；
   **不得**设置 signoff=true；打印 gate message 后停止。
3. 重新调用时若已批准，清空 pending_approval 后继续。

#### Resume paths

- **Manual edit**：向 approved_checkpoints 追加 stage/approved_at/approved_by，并清空 pending_approval。
- **Approval instruction**：用 prompt 明确 “approve checkpoint <stage>”，由 Orchestrator 原子写入并继续。

#### pending_approval type-awareness

Pipeline Orchestrator 遇到任何非 null pending_approval 都先停止：
- checkpoint：提示等待批准
- escalation：提示 fix-request loop 需要 review
- constraint_gap：提示补齐 design_state.constraints

#### Per-stage history trace

每个内部 stage（PASS/FAIL/WARN）都写一条 history；最后一条是 Pipeline Orchestrator
的 terminal decision source。1.5 起包含 `retry_strategy`，形成 10-field schema。

### Programmatic branching on standardized history[] fields

| `confidence` | `failure_class` | `retry_strategy` | `suggested_next_step` | Pipeline action |
|---|---|---|---|---|
| any | `resource_limit` | `escalate` | any | 通过 pending_approval 升级 |
| `low` | any | any | `escalate` | 升级，结果不可靠 |
| `low` | any | any | 非 escalate | 仍升级，low confidence 优先 |
| any | `tool_error` | `regenerate` | `retry_stage` | 同一 Orchestrator 重试一次，仍失败则升级 |
| any | `drc_lvs` \| `connectivity` | `refine` | `loop_back_to:<stage>` | 带 error log 重跑 generating Orchestrator |
| any | `functional` \| `coverage_gap` | `refine` | `escalate` | 新建 fix_request，经 RTL 闭环 |
| any | `timing` \| `power_area` | `refine` | `loop_back_to:<stage>` | 带 QoR feedback 定向优化 |
| any | `spec_gap` | `escalate` | `escalate` | 升级，要求澄清 spec |
| `high` \| `medium` | `none` | `none` | `proceed` | 下一 stage / signoff |
| any | any | any | `abandon` | 升级，child 判定不可恢复 |

`resource_limit` 和 low confidence 始终优先升级。
未匹配组合采用最保守规则：宁可 escalate，不盲目 retry。
程序化 branch 只能读取结构化字段，不得重新解析自由文本 `reason`。

### Dispatch pattern (pipeline-orchestrator)

严格串行：

1. RTL Orchestrator 修 bug，等待完成。
2. Verification/Formal Orchestrator 验证修复，等待完成。

Spawn：
- RTL：`subagent_type: chip-design-rtl:rtl-design-orchestrator`
- Verification：`subagent_type: chip-design-verification:verification-orchestrator`
- Formal：`subagent_type: chip-design-formal:formal-orchestrator`

始终在 child prompt 传 `fix_request.id`。

### V2 extension points（V1 尚未连接）

- Architecture↔RTL refinement：未来 `architecture.refinement_needed=true` 可触发 arch re-run。
- Formal property-bug routing：未来可根据 formal owner 路由给 Formal，而非 RTL。
- LEC unmatched-points：V1 故意不接 fix_request；其正确 consumer 是 synthesis-orchestrator，推迟到 V2。

## QoR Metrics

- `cross_domain_iteration_count`：RTL↔verify dispatch cycle 数，clean design 目标 ≤2
- `time_to_signoff`：首个 open fix_request 到 verification signoff 的 wall-clock time
- `escalation_rate`：hit 3-iteration cap 的 session 比例，目标 <10%
- `fix_request_abandonment_rate`：最终 abandoned 的 request 比例，目标 0%

## Output Required

- 当前 pipeline session 的 fix_request 最终达到 fixed 或 abandoned
- `cross_domain_iteration_count` 更新
- 写入 `memory/meta/experiences.jsonl`
- Console summary：处理了哪些 request、用了多少轮、结果为 converged / escalated / no open requests
