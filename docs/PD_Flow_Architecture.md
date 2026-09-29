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

## 3. Stage Sequence 与 Loop-Back

```
[Floorplan] ──► [Placement] ──► [CTS] ──► [Routing]
                    ▲                          │
                    │   timing fail loop       │
                    └──────────────────────────┘
                                               │
                              ▼ pass
                    [Timing Optimization] ──► [Power Optimization]
                              ▲                        │
                              │   power/timing loop    │
                              └────────────────────────┘
                                               │
                              ▼ pass
                    [Area Optimization] ──► [Sign-off]
                                               │
                              ┌────────────────┘
                              │ DRC/LVS fail → Routing
                              │ Timing fail → Timing Opt
                              ▼ all pass
                           [DONE — GDS]
```

### Loop-Back Rules

| 失败条件 | 回退到 | 最大次数 |
|---|---|---:|
| Post-placement WNS < -0.5 ns | Floorplan | 2 |
| Post-route WNS <0 | Timing Optimization | 3 |
| Power 超预算 | Power Optimization | 2 |
| DRC violation >0 | Routing | 3 |
| LVS mismatch | Routing | 2 |
| Area utilization >85% | Area Optimization | 2 |

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
2. Foundry DRC deck：0 violation
3. LVS：0 error
4. ERC/EM/IR clean
5. Antenna =0
6. Metal density 在 foundry window
7. Final GDS 合并 layer/seal ring 后再做 chip-level DRC

## QoR Metrics
- STA：所有 corner WNS ≥0、TNS=0、hold ≥0
- DRC =0
- LVS =0
- IR drop <5% VDD
- Antenna =0
- Density PASS

## Output Required
- All-corner STA
- DRC/LVS clean report
- Final GDS-II
- Tape-out checklist
```

---

## 5. Stage Agent 规范

所有 stage 使用相同接口：

```
INPUT:  { state_object, stage_name, skill_content }
OUTPUT: { updated_state_object, stage_result }

内部步骤：
  1. 加载本 stage Skill
  2. 从 state_object 提取输入
  3. 执行/分析 stage
  4. 按 Skill 评估 QoR
  5. 分类 PASS | FAIL | WARN
  6. 写回 state_object.stages[stage_name]
  7. 返回给 Orchestrator
```

结构化输出中的 `stage/status/qor/issues/suggested_next_step/output`
属于机器接口，保持英文。

---

## 6. Orchestrator 规范

PD Orchestrator 管理从 floorplan 到 tape-out sign-off 的多阶段实现流程。
核心职责：

- 按 Stage Sequence 调度
- 在每 stage 前加载对应 Skill
- 根据 QoR 决定 proceed / loop-back / escalation
- 维护共享 state 和 loop count
- 不允许 FAIL 被跳过
- 最终只有 timing、DRC、LVS、power/IR 等 sign-off gate 全部实际通过，
  才输出 tape-out-ready GDS
