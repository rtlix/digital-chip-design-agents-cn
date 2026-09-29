# 静态时序分析（STA）流程 — 完整架构设计
## Orchestrator + Stage Agents + Skills

> **目的**：AI 驱动的 multi-corner、multi-mode timing closure 流程。覆盖 constraint validation、timing analysis、exception handling 和 pre-silicon/ECO cycle 的 timing sign-off。

---

## 1. 共享状态对象

```json
{
  "run_id": "sta_001",
  "design_name": "my_chip",
  "inputs": {
    "netlist":     "routed.v",
    "spef":        ["rc_best.spef", "rc_worst.spef"],
    "sdc":         "constraints.sdc",
    "libs":        { "ss": "ss_lib.lib", "ff": "ff_lib.lib", "tt": "tt_lib.lib" },
    "corners": [
      { "name": "setup_worst", "lib": "ss", "spef": "rc_worst", "voltage": 0.9, "temp": 125 },
      { "name": "hold_best",   "lib": "ff", "spef": "rc_best",  "voltage": 1.1, "temp": -40 },
      { "name": "typical",     "lib": "tt", "spef": "rc_worst", "voltage": 1.0, "temp": 25  }
    ]
  },
  "stages": {
    "constraint_validation": { "status": "pending", "output": {} },
    "multi_corner_analysis": { "status": "pending", "output": {} },
    "path_analysis":         { "status": "pending", "output": {} },
    "exception_review":      { "status": "pending", "output": {} },
    "eco_guidance":          { "status": "pending", "output": {} },
    "sta_signoff":           { "status": "pending", "output": {} }
  },
  "timing": {
    "setup_wns": null, "setup_tns": null,
    "hold_wns":  null, "hold_tns":  null,
    "failing_paths": []
  },
  "flow_status": "not_started"
}
```

---

## 2. Stage Sequence

```
[Constraint Validation] ──► [Multi-Corner Analysis] ──► [Path Analysis]
                                                              │ violations
                                                              ▼
                                                       [Exception Review]
                                                              │ invalid exceptions
                                                              └──► Path Analysis
                                                              │ valid
                                                              ▼
                                                       [ECO Guidance]
                                                              │ ECO applied
                                                              └──► Multi-Corner Analysis
                                                              │ clean
                                                              ▼
                                                       [STA Sign-off]
```

---

## 3. Skill 文件说明

### 3.1 `sv-sta-constraints/SKILL.md`

```markdown
# Skill: STA — Constraint Validation

## Purpose
在 timing analysis 前验证全部 SDC constraint 完整、一致，并准确表达 design intent。

## Validation Checks
1. 所有 clock 定义正确 period/waveform
2. Generated clock source/divide/multiply 正确
3. report_timing -unconstrained：0 path
4. CDC 使用正确 false_path/max_delay
5. Multicycle path 同时有 setup 与 hold
6. Input/output delay 与 system budget 一致
7. Exception 不得过宽
8. Operating condition 与 corner 一致
9. Pre-CTS ideal / post-CTS propagated clock 模式正确

## Common Constraint Errors
- MCP 缺 hold correction
- False path 过宽
- Generated clock 缺失
- Clock period 错误
- Test-mode set_case_analysis 缺失

## QoR Metrics
- Unconstrained path =0
- Clock-definition error =0
- Exception 全部 review/document

## Output Required
- Constraint QA report
- Clock summary
- Exception list + justification
```

---

### 3.2 `sv-sta-analysis/SKILL.md`

```markdown
# Skill: STA — Multi-Corner Timing Analysis

## Purpose
在全部 required PVT corner 运行 setup/hold analysis 并解释结果。

## Required Corner Matrix
| Mode | Setup Corner | Hold Corner |
|---|---|---|
| Functional | SS/0.9V/125°C | FF/1.1V/-40°C |
| Test (at-speed) | SS/0.9V/125°C | FF/1.1V/25°C |
| Low Power | SS/0.9V/125°C | FF/1.1V/25°C |

## POCV/AOCV Application
1. AOCV：按 depth/location derate
2. POCV：sigma-based variation
3. Early flow 可 flat OCV，sign-off 用 POCV
4. Pre-CTS ideal uncertainty 与 post-CTS propagated clock 分开

## Path Analysis Priority
1. 每 corner WNS path
2. TNS contribution
3. 带 max_delay 的 CDC path
4. At-speed launch/capture path

## QoR Metrics
| Metric | Target |
|---|---|
| Setup WNS | ≥0，全部 corner |
| Setup TNS | =0，全部 corner |
| Hold WNS | ≥0，全部 corner |
| Hold TNS | =0，全部 corner |

## Output Required
- Per-corner setup/hold report
- WNS/TNS summary
- Top 100 violating path
```

---

### 3.3 `sv-sta-eco/SKILL.md`

```markdown
# Skill: STA — ECO Guidance

## Purpose
分析 timing violation，并给出具体 resize/buffer/reroute/retime ECO 建议。

## ECO Decision Tree
```
Setup violation:
  Logic depth 大?       → Retime / pipeline
  Long wire?            → Buffer / reroute
  Weak driver?          → Upsize
  High-Vt critical?     → Swap SVT/LVT
  Reconvergent fanout?  → Clone / split net

Hold violation:
  CTS skew-induced?     → Useful skew / delay buffer
  Short path?           → HVT delay buffer
  ECO 新路径?           → Targeted hold buffer
```

## ECO Rules
1. 用最小 ECO footprint 修最多 violation
2. 优先 resize，减少 routing impact
3. 使用 reserved ECO site/spare cell
4. 每批 ECO 后重跑 STA
5. 每批 ECO 后跑 LEC
6. 修 setup 不得引入 hold，反之亦然

## QoR Metrics
- ECO efficiency
- ECO cell <2% 总 cell
- Post-ECO LEC EQUIVALENT

## Output Required
- ECO change list
- Pre/post timing comparison
- ECO LEC result
```

---

## 4. Orchestrator System Prompt

```
You are the STA Orchestrator.

You run multi-corner, multi-mode timing analysis, identify violations,
review timing exceptions, and guide ECO closure until timing is clean.

STAGE SEQUENCE:
  constraint_validation → multi_corner_analysis → path_analysis →
  exception_review → eco_guidance → sta_signoff

LOOP-BACK RULES:
  - path_analysis: violations found        → eco_guidance
  - eco_guidance: ECO applied              → multi_corner_analysis (max 10x total)
  - exception_review: invalid exceptions   → path_analysis (max 3x)
  - eco_guidance: ECO count > 2% cells     → escalate to PD team

Sign-off requires: WNS ≥ 0 and TNS = 0 at all corners.
```

> 固定 stage 名和状态文本保留英文。
