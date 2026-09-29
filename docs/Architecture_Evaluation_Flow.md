# 架构评估流程 — 完整架构设计
## Orchestrator + Stage Agents + Skills

> **目的**：AI 驱动的微架构评估流程。覆盖规格分析、微架构权衡探索、性能建模、功耗/面积估算和架构 sign-off。作为数字设计流水线的第一阶段，为后续 RTL Design 提供输入。

---

## 1. 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│               ARCHITECTURE EVALUATION ORCHESTRATOR           │
│  输入：Product spec、performance target、power budget         │
│  输出：Microarchitecture document、已验证的 trade-off          │
└────────────────────────┬─────────────────────────────────────┘
                         │
     ┌───────────────────┼───────────────────────┐
     ▼                   ▼                       ▼
┌──────────┐     ┌──────────────┐       ┌───────────────┐
│  Stage   │     │   Stage      │       │   Stage       │
│  Agent   │     │   Agent      │  ...  │   Agent       │
│  Spec    │     │  MicroArch   │       │  Sign-off     │
│  Analysis│     │  Exploration │       │               │
└────┬─────┘     └──────┬───────┘       └───────┬───────┘
     │                  │                       │
     ▼                  ▼                       ▼
┌──────────┐     ┌──────────────┐       ┌───────────────┐
│  SKILL   │     │    SKILL     │       │    SKILL      │
│  spec    │     │  microarch   │       │   arch-signoff│
└──────────┘     └──────────────┘       └───────────────┘
```

---

## 2. 共享状态对象

```json
{
  "run_id": "arch_eval_001",
  "design_name": "my_soc",
  "inputs": {
    "product_spec":     "path/to/spec.pdf",
    "perf_targets":     { "throughput": "10Gbps", "latency": "<10ns" },
    "power_budget":     "500mW",
    "area_budget":      "5mm2",
    "technology":       "tsmc7nm",
    "use_cases":        ["streaming", "inference", "control"]
  },
  "stages": {
    "spec_analysis":         { "status": "pending", "output": {} },
    "arch_exploration":      { "status": "pending", "output": {} },
    "perf_modelling":        { "status": "pending", "output": {} },
    "power_area_estimation": { "status": "pending", "output": {} },
    "risk_assessment":       { "status": "pending", "output": {} },
    "arch_signoff":          { "status": "pending", "output": {} }
  },
  "selected_architecture": null,
  "trade_off_matrix": [],
  "flow_status": "not_started"
}
```

---

## 3. Stage Sequence 与 Loop-Back 逻辑

```
[Spec Analysis] ──► [Arch Exploration] ──► [Perf Modelling]
                           ▲                      │
                           │ perf miss            │
                           └──────────────────────┘
                                                  │ pass
                              ▼
                    [Power/Area Estimation] ──► [Risk Assessment]
                              ▲                      │
                              │ budget miss          │
                              └──────────────────────┘
                                                  │ pass
                              ▼
                         [Arch Sign-off]
                              │ fail → back to Arch Exploration
                              ▼ pass
                     [Microarch Document]
```

### Loop-Back Rules

| 失败条件 | 回退到 | 最大迭代次数 |
|---|---|---:|
| Performance target 未满足 | Arch Exploration | 3 |
| Power/area 超预算 | Arch Exploration | 2 |
| Risk level 过高且未缓解 | Risk Assessment | 2 |
| Sign-off：spec coverage 不完整 | Spec Analysis | 1 |

---

## 4. Skill 文件说明

### 4.1 `sv-arch-spec/SKILL.md`

```markdown
# Skill: Architecture — Specification Analysis

## Purpose
将 product specification 拆解为正式的 architecture requirement，
识别歧义，并生成结构化 requirement document。

## Domain Rules
1. Requirement 分类：functional、performance、power、area、interface
2. 找出描述不足的区域并要求澄清
3. 把 use case 映射到所需硬件 block（datapath、control、memory、IO）
4. 提取 interface requirement：AXI、PCIe、USB、Ethernet 等协议
5. 如适用，识别 ISO 26262、FIPS 等 safety/security requirement
6. 为每项 requirement 标记 Must-Have / Should-Have / Nice-to-Have

## QoR Metrics
- Requirement coverage：spec 每一章节都映射到 architecture requirement
- Ambiguity count：所有未解决歧义必须被标记
- Interface completeness：所有外部 interface 均已识别

## Output Required
- 结构化 requirement document（JSON 或 Markdown）
- 含 protocol/bandwidth 的 interface list
- 给 product/system team 的 open-question list
```

---

### 4.2 `sv-arch-exploration/SKILL.md`

```markdown
# Skill: Architecture — Microarchitecture Exploration

## Purpose
枚举并评估候选 microarchitecture，对照 performance、power、area target 做权衡。

## Domain Rules
1. 至少生成 3 个候选：conservative、balanced、aggressive
2. 评估 pipeline depth：更深通常 frequency 更高，但 area/power 更大
3. 评估 parallelism：SIMD、superscalar、spatial unrolling
4. Cache/memory hierarchy：size、associativity、latency 与 area 的权衡
5. Interconnect topology：bus、crossbar、NoC，比较 bandwidth 与 complexity
6. 优先考虑已有 hard macro/licensed IP 复用
7. 记录每个 candidate 的 assumption

## Trade-off Matrix Template
| Candidate | Freq Target | Area Est. | Power Est. | Risk | Notes |
|---|---:|---:|---:|---|---|
| Option A | 1GHz | 3mm2 | 300mW | Low | ... |
| Option B | 2GHz | 6mm2 | 700mW | High | ... |

## QoR Metrics
- 至少探索 3 个差异明显的 candidate
- 每个 candidate 的 performance estimate 与 target 偏差在 20% 内
- 只推荐一个 preferred candidate，并给出量化理由

## Output Required
- Trade-off matrix
- 推荐 candidate 及 justification
- 每个 candidate 的 assumption/risk
```

---

### 4.3 `sv-arch-perf/SKILL.md`

```markdown
# Skill: Architecture — Performance Modelling

## Purpose
建立 analytical 或 simulation-based performance model，
验证选定 microarchitecture 是否满足 throughput/latency target。

## Domain Rules
1. 初期使用 Amdahl、Roofline 等 analytical model
2. 复杂 pipeline 使用 TLM/SystemC 或 Python model
3. 建模 compute、memory bandwidth、IO throughput 等全部 bottleneck
4. Sweep clock frequency、parallelism、cache size 等关键参数
5. 使用 use-case list 中有代表性的 workload 验证
6. 包含 best/typical/worst-case scenario

## QoR Metrics
- Throughput：至少比 target 高 10% margin
- Latency：worst-case workload 下满足 target
- Memory bandwidth：不得超过 DRAM/SRAM bandwidth ceiling
- Model confidence：未验证 assumption 必须标记

## Output Required
- Performance model（script 或 spreadsheet）
- 每 use case throughput/latency 结果
- Sensitivity analysis
- 与 target 的比较
```

---

### 4.4 `sv-arch-ppa/SKILL.md`

```markdown
# Skill: Architecture — Power and Area Estimation

## Purpose
在 RTL 编写前，为选定 microarchitecture 做早期 power/area 估算。

## Domain Rules
1. Area estimate 使用目标 technology library scaling data（gates/mm2）
2. Dynamic power：P = α × C × V² × f
3. Leakage：根据目标 Vt mix 的 library characterization
4. Memory area：使用 SRAM/ROM/register-file compiler estimate
5. IO pad area：依据 pad-ring rule
6. 全部 estimate 增加 15–20% margin
7. Estimate 超过 budget 80% 时告警

## Clock Gating Opportunity Analysis
利用 dynamic power 已有 activity factor：

1. 记录每个 clock domain 的 activity factor α
2. 分类：
   - α < 0.15：**high gating opportunity**，作为 RTL must-have
   - 0.15 ≤ α < 0.40：**moderate gating opportunity**，作为 RTL should-have
   - α ≥ 0.40：**always-active**，记录为 always-on
3. 生成 `clock_power_budget`：

| Domain | Frequency | α (activity) | Est. Clock Power (mW) | Gating Class |
|---|---:|---:|---:|---|
| core | 1 GHz | 0.08 | 45 | high |
| dsp | 500 MHz | 0.55 | 30 | always-on |

4. 把 `clock_power_budget` 放入 RTL handoff package。

## QoR Metrics
- Area estimate < budget 80%
- Dynamic power < budget 80%
- Leakage < estimated total power 15%
- High-opportunity domain clock-gating coverage ≥60% register-bank bit
- Confidence：HIGH / MEDIUM / LOW

## Output Required
- 分 block area breakdown
- Dynamic/leakage/per-domain power breakdown
- Target margin analysis
- `clock_power_budget`
```

---

### 4.5 `sv-arch-risk/SKILL.md`

```markdown
# Skill: Architecture — Risk Assessment

## Purpose
识别、分类并制定 selected microarchitecture 的技术风险缓解方案。

## Domain Rules
1. Risk 类别：schedule、technical feasibility、IP availability、tool support、verification complexity、power closure
2. 每项 Risk Score = Probability(1–5) × Impact(1–5)
3. Risk Score ≥15 为 HIGH，必须有 mitigation plan
4. IP risk：确认 availability 与 licensing timeline
5. Tool risk：确认目标 technology 的 EDA support
6. Verification risk：预计 TB complexity >6 个月时告警

## QoR Metrics
- Sign-off 时无未缓解 HIGH risk
- 每项 risk 有 owner 和 mitigation
- Schedule risk 已结合 team capacity 评估

## Output Required
- Risk register
- 管理层评审用 Top 5 risk
```

---

### 4.6 `sv-arch-signoff/SKILL.md`

```markdown
# Skill: Architecture — Sign-off

## Purpose
确认 selected microarchitecture 满足全部 requirement，
可以进入 RTL Design。

## Sign-off Checklist
- [ ] 所有 Must-Have requirement 已覆盖
- [ ] Performance model 达标并有 margin
- [ ] Power/area estimate 在 budget 内
- [ ] HIGH risk 全部已缓解
- [ ] Interface specification 完整并达成一致
- [ ] Memory map 已定义
- [ ] Clock domain 与 CDC strategy 已明确
- [ ] Reset strategy 已定义
- [ ] DFT strategy 已确认
- [ ] Verification strategy 已确认
- [ ] 已生成 `clock_power_budget` 并完成每个 domain 分类
- [ ] High-opportunity domain clock-gating coverage ≥60%
- [ ] RTL handoff package 包含 `clock_power_budget`

## Output Required
- Signed-off microarchitecture document
- Final trade-off decision record
- RTL design guideline
- RTL team handoff package
```

---

## 5. Stage Agent 接口

```
INPUT:  { state_object, stage_name, skill_content }
OUTPUT: {
  "stage": "arch_exploration",
  "status": "PASS" | "FAIL" | "WARN",
  "output": { ... structured results ... },
  "issues": [ { "severity": "ERROR|WARN", "description": "...", "fix": "..." } ],
  "suggested_next_step": "proceed | loop_back_to:<stage> | retry_stage | escalate | abandon"
}
```

机器字段、枚举和值保持英文，以保证与 Agent contract 兼容。

---

## 6. Orchestrator 规格

### System Prompt

```
You are the Architecture Evaluation Orchestrator for chip design.

You receive a product specification and guide a multi-stage evaluation
that produces a validated microarchitecture document.

STAGE SEQUENCE:
  spec_analysis → arch_exploration → perf_modelling →
  power_area_estimation → risk_assessment → arch_signoff

LOOP-BACK RULES:
  - perf_modelling FAIL          → arch_exploration (max 3x)
  - power_area_estimation FAIL   → arch_exploration (max 2x)
  - risk_assessment: HIGH risks  → risk_assessment (max 2x)
  - arch_signoff FAIL            → spec_analysis if coverage gap (max 1x)
                                 → arch_exploration if PPA gap (max 2x)

On completion, produce a microarchitecture document and hand-off
package for the RTL design team.
```

> 上述 stage 名、状态值和固定接口文本属于机器协议，因此保留英文；对应含义均已在正文中文化。

---

## 7. 输出：Microarchitecture 文档模板

```markdown
# Microarchitecture Specification: [Design Name]
**Version**: 1.0 | **Status**: Approved for RTL

## 1. Design Overview
## 2. Block Diagram
## 3. Performance Summary (vs targets)
## 4. Power/Area Summary (vs budget)
## 5. Block Descriptions (per major block)
## 6. Clock Domain Architecture
## 7. Reset Architecture
## 8. Memory Map
## 9. Interface Specifications
## 10. DFT Strategy
## 11. Verification Strategy
## 12. Risk Register (summary)
## 13. Open Items
```

> 模板中的固定章节名可按项目需要继续中文化；如果该模板被自动脚本解析，建议保持这些英文标题。
