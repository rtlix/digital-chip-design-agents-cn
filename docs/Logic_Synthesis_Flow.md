# 逻辑综合流程 — 完整架构设计
## Orchestrator + Stage Agents + Skills

> **目的**：AI 驱动的 RTL→gate-level netlist 逻辑综合流程。覆盖 constraint setup、speed/area/power optimization、netlist quality check，以及 Physical Design handoff。

---

## 1. 共享状态对象

```json
{
  "run_id": "synth_001",
  "design_name": "my_block",
  "inputs": {
    "rtl_filelist":   "filelist.f",
    "sdc":            "constraints.sdc",
    "liberty_files":  ["tt.lib", "ss.lib", "ff.lib"],
    "target_freq":    "1GHz",
    "target_corner":  "ss_0p9v_125c",
    "effort":         "high"
  },
  "stages": {
    "constraint_setup":   { "status": "pending", "output": {} },
    "compile_explore":    { "status": "pending", "output": {} },
    "compile_final":      { "status": "pending", "output": {} },
    "netlist_qc":         { "status": "pending", "output": {} },
    "synthesis_signoff":  { "status": "pending", "output": {} }
  },
  "qor": {
    "wns": null, "tns": null,
    "area_um2": null, "cell_count": null,
    "power_mw": null
  },
  "flow_status": "not_started"
}
```

---

## 2. Stage Sequence

```
[Constraint Setup] ──► [Compile Explore] ──► [Compile Final]
                              ▲                     │ timing fail
                              └─────────────────────┘
                                                    │ pass
                              ▼
                       [Netlist QC] ──► [Synthesis Sign-off]
                                              │ fail → Compile Final
                                              ▼ pass → Gate Netlist
```

### Loop-Back Rules

| 失败 | 回退到 | 最大次数 |
|---|---|---:|
| compile_final 后 WNS <0 | compile_final | 3 |
| Area 超预算 | compile_explore | 2 |
| Netlist 有 unmapped cell | compile_final | 2 |
| Power 超预算 | compile_explore | 2 |

---

## 3. Skill 文件说明

### 3.1 `sv-synth-constraints/SKILL.md`

```markdown
# Skill: Synthesis — Constraint Setup (SDC)

## Purpose
在综合前建立并验证所有 SDC constraint。

## Domain Rules
1. create_clock：全部 primary clock，明确 period/waveform/name
2. create_generated_clock：全部 derived/divided clock
3. set_clock_uncertainty：pre-CTS setup uncertainty 通常 200–500 ps，或按项目 constraint
4. set_clock_latency：有 CTS estimate 时明确设置
5. set_input_delay / set_output_delay：全部 primary IO
6. set_false_path：仅真实 async/test/reset 等 intent
7. set_multicycle_path：setup/hold 配套
8. set_dont_touch：IP、memory macro、手工 cell
9. set_max_fanout：按 library 建议，常见 32
10. set_max_transition：按 technology rule
11. Operating condition 显式设置，禁止依赖默认值

## Common SDC Mistakes
- Generated clock 漏定义
- MCP 缺 hold adjustment
- IO 过约束导致 area 浪费
- IO 欠约束掩盖 timing issue

## QoR Metrics
- report_clocks：全部 clock 定义
- report_port -verbose：全部 IO constrained
- report_timing：unconstrained path = 0

## Output Required
- Validated SDC
- Clock summary
- Constraint QA report
```

---

### 3.2 `sv-synth-compile/SKILL.md`

```markdown
# Skill: Synthesis — Compile and Optimization

## Purpose
选择正确 effort/strategy 运行综合，满足 timing、area 和 power target。

## Recommended Flow
1. read_hdl / analyze+elaborate
2. check_design / report_lint
3. Compile explore
4. Incremental compile
5. Final high-effort compile
6. report_timing / report_area / report_power

## Optimization Strategies
| Priority | Strategy |
|---|---|
| Timing | compile_ultra、path-group weighting、retiming |
| Area | high area effort、resource sharing |
| Power | power-aware compile、clock-gating insertion |
| Balanced | compile_ultra -no_autoungroup + incremental |

## Domain Rules
1. Worst-case setup corner 做主综合
2. 有条件时使用 multi-scenario compile
3. Enable clock-gating synthesis
4. 有 placement intent 的 block 保留 hierarchy
5. 小 module 可 ungroup
6. Critical path 必须人工审查是否应 RTL restructure

## QoR Metrics
- WNS ≥0 或项目 target
- TNS =0 或项目 target
- Area 在 budget 内
- Power 在 budget 内
- Final netlist unmapped cell =0

## Output Required
- Gate-level netlist
- Setup/hold timing report
- Area report
- Power report
- Synthesis log
```

---

### 3.3 `sv-synth-netlist-qc/SKILL.md`

```markdown
# Skill: Synthesis — Netlist Quality Check

## Purpose
验证 gate-level netlist 正确并可交付 PD。

## Checks to Perform
1. 全部 module elaborated/mapped
2. Blackbox =0
3. DFT 场景 scan chain intact
4. Power/ground tie 正确
5. Floating gate/tie-off 合法
6. Combinational loop =0
7. RTL vs netlist LEC 必须 PASS
8. Netlist SDC 与 RTL SDC intent 一致

## Formal Equivalence
- Golden：post-lint/post-CDC-clean RTL
- Revised：gate-level netlist
- 全部 compare point EQUIVALENT
- 任何 UNMATCHED point 必须在 PD 前关闭

## QoR Metrics
- LEC 100% equivalent
- Blackbox =0
- Combinational loop =0
- Scan-chain integrity verified

## Output Required
- LEC report
- Netlist QC checklist
- Final gate netlist
- Back-annotated SDC
```

---

## 4. Orchestrator System Prompt

```
You are the Logic Synthesis Orchestrator.

You take RTL and constraints and produce a timing-clean, verified
gate-level netlist ready for physical design.

STAGE SEQUENCE:
  constraint_setup → compile_explore → compile_final →
  netlist_qc → synthesis_signoff

LOOP-BACK RULES:
  - compile_final: WNS < 0          → compile_final (max 3x)
  - compile_final: area over budget  → compile_explore (max 2x)
  - netlist_qc: LEC fail             → compile_final (max 2x)
  - netlist_qc: unmapped cells       → compile_final (max 2x)

On completion: produce PD handoff package (netlist, SDC, constraints doc).
```

> 固定 stage 名、枚举和接口文本保留英文。
