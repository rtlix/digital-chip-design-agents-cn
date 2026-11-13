# Physical Design 流程 — 完整架构设计
## Orchestrator + Stage Agents + Skills

> **目的**：定义 AI 驱动 Physical Design（PD）流程的完整架构。覆盖所有 Skill、Stage Agent 和顶层 Orchestrator，从 gate-level netlist 一直到 tape-out-ready GDS。

---

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                   ORCHESTRATOR AGENT                        │
│  输入：Netlist、SDC、LEF/DEF、technology file                │
│  管理：Stage sequence、QoR state、loop-back logic             │
│  输出：Final GDS、timing/power/area report                    │
└────────────────────┬────────────────────────────────────────┘
                     │ dispatches to
     ┌───────────────┼───────────────────────┐
     ▼               ▼                       ▼
┌─────────┐   ┌─────────────┐         ┌──────────────┐
│ Stage   │   │  Stage      │   ...   │  Stage       │
│ Agent 1 │   │  Agent 2    │         │  Agent N     │
│Floorplan│   │ Placement   │         │  Sign-off    │
└────┬────┘   └──────┬──────┘         └──────┬───────┘
     │               │                       │
     ▼               ▼                       ▼
┌─────────┐   ┌─────────────┐         ┌──────────────┐
│  SKILL  │   │   SKILL     │         │    SKILL     │
│floorplan│   │  placement  │         │   signoff    │
└─────────┘   └─────────────┘         └──────────────┘
```

### 核心原则

- **Skills**：每个 stage 的 domain knowledge、rule、heuristic、constraint 与 metric
- **Stage Agents**：执行单个 stage、评估 QoR、返回结构化结果
- **Orchestrator**：按顺序调度 stage、传递 state、处理 failure 和 loop-back

---

## 2. 共享数据契约（State Object）

所有 Agent 通过同一个 JSON state object 通信：

```json
{
  "run_id": "pd_run_001",
  "technology": "tsmc7nm",
  "design_name": "my_chip",
  "inputs": {
    "netlist": "path/to/netlist.v",
    "sdc": "path/to/constraints.sdc",
    "lef": ["tech.lef", "cells.lef"],
    "def": "path/to/floorplan.def",
    "upf": "path/to/power_intent.upf",
    "lib": ["tt.lib", "ss.lib", "ff.lib"]
  },
  "stages": {
    "floorplan": {"status":"pending","qor":{},"issues":[],"output":{}},
    "placement": {"status":"pending","qor":{},"issues":[],"output":{}},
    "cts": {"status":"pending","qor":{},"issues":[],"output":{}},
    "routing": {"status":"pending","qor":{},"issues":[],"output":{}},
    "timing_optimization": {"status":"pending","qor":{},"issues":[],"output":{}},
    "power_optimization": {"status":"pending","qor":{},"issues":[],"output":{}},
    "area_optimization": {"status":"pending","qor":{},"issues":[],"output":{}},
    "signoff": {"status":"pending","qor":{},"issues":[],"output":{}}
  },
  "global_qor": {
    "wns": null,
    "tns": null,
    "worst_slack": null,
    "total_power": null,
    "core_area_util": null,
    "drc_violations": null
  },
  "loop_count": {},
  "current_stage": null,
  "flow_status": "not_started"
}
```

---

## 3. Stage Sequence

```text
floorplan → placement → cts → routing → extraction → timing_optimization → power_optimization → area_optimization → ir_em → signoff
```

回退规则（目标阶段、迭代上限以及需要升级处理而非继续循环的失败）见 [`physical-design-orchestrator.md`](../plugins/pd/agents/physical-design-orchestrator.md) 的 `## Loop-Back Rules`。以该文件为准，本文不重复这些规则。

---

## 4. Skill 文件说明

### 4.1 Floorplanning

```markdown
# Skill: Physical Design — Floorplanning

## Purpose
规划 die/core、IO、macro、power grid 和 blockage。

## Domain Rules
1. Core utilization 目标约 70–80%
2. Macro 靠 edge/corner，留 5–10 μm halo
3. IO 与 package pin assignment 一致
4. Power strap 间距按 technology rule
5. Analog/RF macro 周围加 hard blockage
6. Aspect ratio 尽量 1:1

## QoR Metrics
- Congestion >80% 告警
- Floorplan-stage WNS < -2 ns 告警
- IR drop >10% VDD 告警

## Output Required
- floorplan.def
- Power-grid script/DEF
- Macro placement report
- Congestion map
```

### 4.2 Placement

```markdown
# Skill: Physical Design — Placement

## Domain Rules
1. Global placement → legalization → detailed placement
2. Pre-CTS timing 使用 ideal clock
3. Partition utilization <80%
4. High-fanout net 提前 buffer/constraint
5. Critical path 可加 placement guidance
6. Placement 后 scan reorder

## QoR Metrics
- Pre-CTS WNS > -0.3 ns
- Local density >90% 告警
- Routing overflow >1% 告警

## Output Required
- placement.def
- Pre-CTS setup/hold report
- Density/congestion report
```

### 4.3 Clock Tree Synthesis（CTS）

```markdown
## Domain Rules
1. Clock skew target <100 ps 或按项目 SDC
2. Insertion delay 尽量小，并与 set_clock_latency intent 一致
3. Clock max transition 常见 150–200 ps
4. Buffer max fanout 常见 16–32
5. Useful skew 只在明确 sign-off 场景使用
6. Clock-gating cell 与 CTS 集成
7. 多 clock domain 独立处理并复查 CDC

## QoR Metrics
- Global skew >150 ps 告警
- Insertion delay >500 ps 告警
- Post-CTS WNS < -0.2 ns 告警
- Routing 前 hold slack 应 ≥0
- Clock-tree power > dynamic power 20% 告警

## Output Required
- Post-CTS DEF
- Clock-tree report
- Post-CTS setup/hold report
```

### 4.4 Routing

```markdown
## Domain Rules
1. Global route → track assignment → detailed route → search/repair
2. 严格遵循 foundry DRC
3. Clock/analog critical net 做 shielding
4. Upper metal 优先 power，lower metal 优先 signal
5. Antenna 用 diode/jump-via 修复
6. 先进节点处理 multi-patterning/color

## QoR Metrics
- DRC =0
- LVS =0
- Post-route WNS <0 告警
- Routing overflow =0

## Output Required
- routed.def
- DRC/LVS report
- Post-route timing report
```

### 4.5 Timing Optimization

```markdown
## Domain Rules
1. Multi-corner：SS setup、FF hold、TT typical
2. Setup：driver upsize、repeater、retime
3. Hold：delay buffer，优先 HVT
4. Critical path 可做 Vt swap
5. ECO 后 placement/routing/STA 重新验证
6. Scan-chain order 未经 DFT 批准不得修改
7. Sign-off 使用 foundry-approved AOCV/POCV

## QoR Metrics
- 所有 corner WNS ≥ target
- TNS = target（通常 0）
- Hold slack ≥0
- ECO cell >2% 总 cell 时告警

## Output Required
- All-corner timing closure report
- ECO list
- SPEF
- Post-ECO routed DEF
```

### 4.6 Power Optimization

```markdown
## Domain Rules
1. Dynamic power：clock gating、operand isolation、multi-Vt
2. Leakage：非 critical cell 换 HVT，每批后重查 timing
3. 验证 UPF isolation/level-shifter/retention
4. 每个 voltage island 检查 IR drop
5. Always-on logic 使用正确 cell
6. Power-gating routing 修改前验证 wakeup/shutdown sequence

## QoR Metrics
- Total power 在 budget 内
- Leakage < total power 15%
- IR drop <5% VDD
- Post-opt WNS ≥0

## Output Required
- Per-domain dynamic/static power report
- IR-drop report
- Updated DEF
- UPF compliance report
```

### 4.7 Area Optimization

```markdown
## Domain Rules
1. 删除冗余 buffer/inverter
2. Downsize 非 critical cell
3. 回收 unused standard-cell site
4. WNS margin 不低于 50 ps
5. Area ECO 后重跑 DRC

## QoR Metrics
- Core utilization 70–80%，hard limit 85%
- 跟踪 cell-count reduction
- WNS 保持 ≥0
- DRC 保持 clean

## Output Required
- Pre/post area report
- Updated DEF
- Cell-count/type breakdown
```

### 4.8 Sign-off

```markdown
## Domain Rules
1. 所有 required PVT 跑 sign-off STA
2. DRC：运行代工厂批准规则，允许违规数为零
3. LVS：比较网表与版图，允许错误数为零
4. ERC：电迁移及 IR drop 签核
5. 天线检查：违规为零
6. Metal density 在 foundry window
7. Final GDS 合并 layer/seal ring 后再做 chip-level DRC

## QoR Metrics (All Must Pass)
- STA: 所有 corner 均 WNS ≥ 0、TNS = 0、Hold ≥ 0
- DRC violations: 0
- LVS errors: 0
- ERC: 无电迁移违规，IR drop < 5% VDD
- Antenna violations: 0
- Density check: PASS

## On Failure
签核失败的处理目标由编排器的 `## Loop-Back Rules` 决定，见
[`physical-design-orchestrator.md`](../plugins/pd/agents/physical-design-orchestrator.md).

## Output Required
- All-corner STA
- DRC/LVS clean report
- Final GDS-II
- Tape-out checklist
```

---

## 5. Stage Agent 规范

所有阶段使用相同接口：

```text
INPUT:  { state_object, stage_name, skill_content }
OUTPUT: { updated_state_object, stage_result }
```

内部步骤：加载本阶段 Skill；从 state_object 提取相关输入；分析/执行任务；按 Skill 评价 QoR；分类 PASS/FAIL/WARN；写回 state_object.stages[stage_name]；向编排器返回更新状态。

### 阶段 Agent 提示词模板

实现各阶段 Agent 时，采用以下系统提示词结构：

```text
你是物理设计阶段 Agent，负责 [STAGE NAME]。
输入：当前 PD 状态（JSON）、阶段 Skill（领域规则、QoR、修复）、相关设计文件或报告。
职责：分析本阶段输入；应用 Skill 领域规则；评价 QoR；识别问题并建议修复；返回结构化 JSON。
```

```json
{
  "stage": "[stage_name]",
  "status": "PASS | FAIL | WARN",
  "qor": {},
  "issues": [{"severity": "ERROR|WARN", "description": "...", "fix": "..."}],
  "suggested_next_step": "proceed | loop_back_to:<stage> | retry_stage | escalate | abandon",
  "output": {}
}
```

不要进入下一阶段，只返回结果。

---

## 6. 编排器完整规范

### 6.1 编排器系统提示词

编排器的系统提示词即其 Agent 定义 [`physical-design-orchestrator.md`](../plugins/pd/agents/physical-design-orchestrator.md)，包括阶段顺序、回退、阶段门控和升级规则。本文不重复这些内容。

### 6.2 编排器决策逻辑（伪代码）

```python
def run_pd_flow(state):
    stage_sequence = [
        "floorplan", "placement", "cts", "routing",
        "timing_optimization", "power_optimization",
        "area_optimization", "signoff"
    ]

    current_index = 0

    while current_index < len(stage_sequence):
        stage = stage_sequence[current_index]
        state["current_stage"] = stage

        # Load skill for this stage
        skill = load_skill(f"sv-pd-{stage}/SKILL.md")

        # Dispatch to stage agent
        result = dispatch_stage_agent(stage, state, skill)

        # Write result into state
        state["stages"][stage] = result
        update_global_qor(state, result["qor"])

        if result["status"] == "PASS":
            current_index += 1  # proceed to next stage

        elif result["status"] == "FAIL":
            loop_target = resolve_loop_back(stage, result, state)

            if loop_target is None:
                # No loop-back possible — escalate
                escalate_to_user(state, result)
                return

            loop_key = f"{stage}_to_{loop_target}"
            state["loop_count"][loop_key] = state["loop_count"].get(loop_key, 0) + 1

            max_loops = get_max_loops(loop_key)
            if state["loop_count"][loop_key] > max_loops:
                escalate_to_user(state, result)
                return

            # Jump back
            current_index = stage_sequence.index(loop_target)

        elif result["status"] == "WARN":
            # Log warning, proceed
            log_warning(stage, result)
            current_index += 1

    # All stages passed
    state["flow_status"] = "COMPLETE"
    return generate_final_report(state)
```

### 6.3 编排器最终报告模板

流程完成后，编排器按以下格式生成报告：

```markdown
# 物理设计运行报告
**设计**：[design_name]
**工艺**：[technology]
**Run ID**：[run_id]
**状态**：TAPE-OUT READY / FAILED

## QoR 摘要
| 指标 | 值 | 目标 | 状态 |
|---|---|---|---|
| WNS（setup）| Xns | ≥ 0 | PASS |
| TNS | 0ps | 0 | PASS |
| Hold Slack | Xps | ≥ 0 | PASS |
| 总功耗 | XmW | < [budget] | PASS |
| 核心利用率 | X% | 70–80% | PASS |
| DRC 违规 | 0 | 0 | PASS |
| LVS 错误 | 0 | 0 | PASS |

## 阶段执行日志
| 阶段 | 状态 | 迭代次数 | 主要问题 |
|---|---|---|---|
| Floorplan | PASS | 1 | — |
| Placement | PASS | 1 | — |
| CTS | PASS | 1 | — |
| Routing | PASS | 2 | DRC 短路，已修复 |
| Timing Optimization | PASS | 1 | — |
| Power Optimization | PASS | 1 | — |
| Area Optimization | WARN | 1 | 利用率 82%，在允许范围内 |
| Sign-off | PASS | 1 | — |

## 输出文件
- 最终 GDS：[path]
- 签核 STA 报告：[path]
- DRC 干净报告：[path]
- LVS 干净报告：[path]
- 功耗报告：[path]
```

---

## 7. 新会话实现指南

按以下顺序实现：

### 步骤 1：创建 Skill 文件

在指定路径创建各 Skill，填入第 4 节内容。这些文件是只读参考文档。

### 步骤 2：实现阶段 Agent

为 8 个阶段分别按第 5 节接口创建 Agent：接收 `(state_object, skill_content)`，返回结构化 JSON，使用 Claude API（`claude-sonnet-4-20250514`）分析，调用时注入该阶段系统提示词。

### 步骤 3：实现编排器

根据 [Agent 定义](../plugins/pd/agents/physical-design-orchestrator.md)（6.1 节）与 6.2 节决策逻辑构建编排器：它是唯一直接与用户交互的 Agent，管理全部状态，以程序方式派发阶段 Agent，处理全部回退与升级逻辑。

### 步骤 4：连接状态对象

每次运行开始时，根据用户输入初始化第 2 节状态对象；每次 Agent 调用传入该对象，并在调用间持久化。

### 步骤 5：使用简单设计检查

完整流程前，使用已知正常输入独立检查每个阶段 Agent，确认 Skill 加载与 QoR 评价正确。

---

## 8. 关键设计决策摘要

| 决策 | 选择 | 理由 |
|---|---|---|
| Agent 粒度 | 每个 PD 阶段一个 Agent | 分离职责，便于逐阶段调试和迭代 |
| 状态管理 | 单一共享 JSON 对象 | 统一接口，便于流程中途检查 |
| 回退控制 | 仅由编排器处理 | 阶段 Agent 不作流程决策，职责更清晰 |
| Skill 格式 | 每阶段一个 Markdown | 人可读，更新领域规则无需改代码 |
| 最大循环次数 | 按转换硬编码 | 防止无限循环，携带上下文升级 |
| 模型 | claude-sonnet-4-20250514 | 平衡 EDA 分析推理质量与速度 |

---

*架构文档结束，可开始实现。*
