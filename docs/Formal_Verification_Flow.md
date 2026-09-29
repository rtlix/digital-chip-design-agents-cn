# 形式验证流程 — 完整架构设计
## Orchestrator + Stage Agents + Skills

> **目的**：AI 驱动的 Formal Verification 流程，覆盖 Formal Property Verification（FPV）、Logical Equivalence Checking（LEC）以及 CDC/RDC formal analysis。它与 simulation-based verification 互补，用穷尽证明补足仿真覆盖不到的状态空间。

---

## 1. 共享状态对象

```json
{
  "run_id": "formal_001",
  "design_name": "my_block",
  "inputs": {
    "rtl_filelist":  "filelist.f",
    "properties":    "properties.sva",
    "assumptions":   "assumptions.sva",
    "golden_netlist": "rtl.v",
    "revised_netlist": "netlist.v"
  },
  "stages": {
    "property_planning":   { "status": "pending", "output": {} },
    "environment_setup":   { "status": "pending", "output": {} },
    "fpv_run":             { "status": "pending", "output": {} },
    "cex_analysis":        { "status": "pending", "output": {} },
    "lec_run":             { "status": "pending", "output": {} },
    "formal_signoff":      { "status": "pending", "output": {} }
  },
  "properties": {
    "proven": [], "failed": [], "vacuous": [], "inconclusive": []
  },
  "lec_result": null,
  "flow_status": "not_started"
}
```

---

## 2. Stage Sequence（阶段顺序）

```
[Property Planning] ──► [Environment Setup] ──► [FPV Run]
                                                     │ CEX found
                                                     ▼
                                              [CEX Analysis]
                                                     │ RTL bug → fix RTL
                                                     │ assumption issue → fix env
                                                     └──────► [FPV Run] (retry)
                                                     │ all proven
                              ▼
                          [LEC Run] ──► [Formal Sign-off]
                              │ unmatched points → fix netlist
                              └──────► [LEC Run] (retry)
```

### Loop-Back Rules

| 失败 | 回退到 | 最大次数 |
|---|---|---:|
| FPV：发现 CEX（RTL bug） | Fix RTL → FPV | N/A |
| FPV：vacuous proof | Environment Setup | 3 |
| FPV：inconclusive/bound 太小 | FPV Run，增加 bound | 3 |
| LEC：unmatched point | Fix netlist → LEC | 3 |

---

## 3. Skill 文件说明

### 3.1 `sv-formal-property/SKILL.md`

```markdown
# Skill: Formal — Property Planning

## Purpose
定义需要 formal proof 的完整 property 集合。

## Property Categories
1. Safety：“坏事永远不会发生”
   → `assert property (@(posedge clk) !(error && valid));`
2. Liveness：“好事最终会发生”
   → `assert property (@(posedge clk) req |-> ##[1:MAX] ack);`
3. Stability：condition 成立时 output 保持稳定
   → `assert property (@(posedge clk) valid |-> $stable(data));`
4. Reachability：某个 state 可达，使用 cover
5. Equivalence：两个实现等价，用于 LEC

## Property Writing Rules
1. 每条 property 有明确名称和 failure message
2. Liveness 必须有有限 bound
3. Assumption 必须经过 vacuity validation
4. 优先使用 $past()/$rose()/$fell()，避免手工 delay model
5. Reset 条件使用 disable iff

## QoR Metrics
- 每个 spec feature 至少映射到 property 或 cover point
- 关键 state 的 reachability 可证明

## Output Required
- Property plan
- SVA property file
- SVA assumption file
```

---

### 3.2 `sv-formal-environment/SKILL.md`

```markdown
# Skill: Formal — Environment Setup

## Purpose
构建正确完整的 formal environment（constraint/assumption），真实模拟 DUT 所处上下文。

## Domain Rules
1. Primary input 只约束到合法值
2. Protocol assumption 模拟上游行为
3. Reset assumption 强制 time 0 的正确 reset sequence
4. Over-constraining 会造成 vacuous proof
5. Under-constraining 会产生环境导致的假 CEX
6. Vacuity check：禁用 assumption 后，property 不应仍无条件成立
7. Helper assumption 谨慎使用并逐条文档化

## Common Assumptions Template
```systemverilog
// Reset behavior
assume property (@(posedge clk) $rose(rst_n) |-> ##1 !rst_n throughout ##[0:5] rst_n);

// AXI valid stability
assume property (@(posedge clk) (s_axi_awvalid && !s_axi_awready) |=>
                                 $stable(s_axi_awaddr));
```

## QoR Metrics
- 所有 property vacuity check PASS
- 无明显 over-constraining
- Environment review 已由 verification lead sign-off

## Output Required
- Formal environment file
- Vacuity report
- Environment review record
```

---

### 3.3 `sv-formal-fpv/SKILL.md`

```markdown
# Skill: Formal — Property Verification (FPV) Execution

## Purpose
运行 formal property verification，并分类全部 property 结果。

## Result Classifications
| Result | 含义 | 动作 |
|---|---|---|
| PROVEN | 所有 reachable state 都满足 property | 记录并继续 |
| CEX | 发现 counterexample | 分析并修复 |
| VACUOUS | antecedent 从未触发导致“证明” | 修 assumption/property |
| INCONCLUSIVE | Bound 不够或 state space 太大 | 增加 bound / abstraction |
| UNREACHABLE | Cover point 不可达 | 核实或 waive |

## Strategies for Inconclusive Results
1. 增加 BMC bound / k-induction depth
2. 使用 data/counter abstraction
3. 分解 property，再组合证明
4. Formal + simulation 混合
5. 无法收敛时必须记录 justification，不能伪装成 PASS

## QoR Metrics
- 目标：P0 全部 PROVEN，且无 vacuous proof
- 无未分析 CEX
- 所有 INCONCLUSIVE 有明确说明

## Output Required
- Per-property FPV report
- Failure 的 CEX trace/waveform
```

---

### 3.4 `sv-formal-lec/SKILL.md`

```markdown
# Skill: Formal — Logical Equivalence Checking (LEC)

## Purpose
证明同一设计的两种表示（RTL vs netlist、pre-ECO vs post-ECO）逻辑等价。

## LEC Flow
1. Read golden/reference
2. Read revised
3. Map sequential/combinational compare point
4. 验证所有 point 的 cone-of-influence
5. 报告 EQUIVALENT / UNMATCHED / ABORTED

## Domain Rules
1. Golden/revised 使用同一套 SDC
2. Scan mode 对两边必须一致处理
3. Blackbox 必须一致
4. Clock gating mapping 要正确
5. Unmatched point 必须 root-cause，不能无理由 waive
6. 每次 ECO 后都运行 LEC，不只 sign-off 时运行

## Common LEC Failures
- Optimizer 删除逻辑
- RTL/netlist SDC 不一致
- Scan-chain reorder
- 只有一侧存在 blackbox

## QoR Metrics
- 所有 compare point EQUIVALENT
- UNMATCHED = 0
- ABORTED = 0

## Output Required
- LEC run report
- Unmatched point analysis
- EQUIVALENT sign-off record
```

---

## 4. Orchestrator System Prompt

```
You are the Formal Verification Orchestrator.

You manage FPV and LEC flows, track property results, and ensure
all design properties are proven before RTL sign-off.

STAGE SEQUENCE:
  property_planning → environment_setup → fpv_run →
  cex_analysis (if needed) → lec_run → formal_signoff

LOOP-BACK RULES:
  - fpv_run: CEX found           → (RTL fix) → fpv_run (unlimited, RTL-gated)
  - fpv_run: vacuous             → environment_setup (max 3x)
  - fpv_run: inconclusive        → fpv_run with larger bound (max 3x)
  - lec_run: unmatched           → (netlist fix) → lec_run (max 3x)

Track all property results in state_object.properties.
Flag any unproven P0 property as a blocker for sign-off.
```

> 固定 stage 名、枚举和机器接口保持英文，正文已中文化。
