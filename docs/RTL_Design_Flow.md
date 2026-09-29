# RTL 设计流程 — 完整架构设计
## Orchestrator + Stage Agents + Skills

> **目的**：AI 驱动的 SystemVerilog RTL 设计流程。覆盖 module planning、RTL coding、lint、CDC/RDC、synthesis-readiness sign-off。输入 microarchitecture 文档，输出可直接交付综合的 RTL package。

---

## 1. 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                    RTL DESIGN ORCHESTRATOR                   │
│  输入：Microarch doc、interface spec、coding guideline        │
│  输出：Lint-clean、CDC-clean、synthesis-ready RTL              │
└────────────────────────┬─────────────────────────────────────┘
                         │
     ┌───────────────────┼───────────────────────┐
     ▼                   ▼                       ▼
┌──────────┐     ┌──────────────┐       ┌───────────────┐
│  Stage   │     │   Stage      │       │   Stage       │
│  Agent   │     │   Agent      │  ...  │   Agent       │
│  Module  │     │  RTL Coding  │       │  Synth Ready  │
│  Planning│     │  & Review    │       │  Sign-off     │
└────┬─────┘     └──────┬───────┘       └───────┬───────┘
     │                  │                       │
     ▼                  ▼                       ▼
  SKILL               SKILL                   SKILL
```

---

## 2. 共享状态对象

```json
{
  "run_id": "rtl_design_001",
  "design_name": "my_block",
  "inputs": {
    "microarch_doc":   "path/to/microarch.md",
    "interface_spec":  "path/to/interfaces.md",
    "coding_guidelines": "path/to/guidelines.md",
    "technology":      "tsmc7nm",
    "target_frequency": "1GHz"
  },
  "stages": {
    "module_planning":   { "status": "pending", "output": {} },
    "rtl_coding":        { "status": "pending", "output": {} },
    "lint_check":        { "status": "pending", "output": {} },
    "cdc_rdc_analysis":  { "status": "pending", "output": {} },
    "synth_check":       { "status": "pending", "output": {} },
    "rtl_signoff":       { "status": "pending", "output": {} }
  },
  "module_list":    [],
  "lint_errors":    [],
  "cdc_violations": [],
  "flow_status": "not_started"
}
```

---

## 3. Stage Sequence 与 Loop-Back

```
[Module Planning] ──► [RTL Coding] ──► [Lint Check]
                           ▲                 │ fail
                           └─────────────────┘
                                             │ pass
                              ▼
                       [CDC/RDC Analysis]
                           ▲      │ violations
                           └──────┘
                                  │ pass
                              ▼
                       [Synth Check]
                           ▲      │ fail (timing/area)
                           └──────┘
                                  │ pass
                              ▼
                       [RTL Sign-off]
                              │ fail → RTL Coding
                              ▼ pass
                    [Synthesis-Ready RTL Package]
```

### Loop-Back Rules

| 失败条件 | 回退到 | 最大次数 |
|---|---|---:|
| Lint error >0 | RTL Coding | 5 |
| 未 waive 的 CDC violation | RTL Coding | 3 |
| Synth timing 比 target margin 差 >20% | RTL Coding | 2 |
| Synth area > estimate 120% | RTL Coding | 2 |
| Sign-off 缺失模块/coverage | Module Planning | 1 |

---

## 4. Skill 文件说明

### 4.1 `sv-rtl-planning/SKILL.md`

```markdown
# Skill: RTL — Module Planning

## Purpose
写任何 RTL 前，先把 microarchitecture 拆成职责清晰、接口明确的 module hierarchy。

## Domain Rules
1. Top-down decomposition
2. 每 module 单一职责
3. Coding 前冻结 port list：direction/width/type
4. 标出每个 module 的 clock domain 和所有 CDC
5. 标出 reset domain，同步/异步方式
6. Width/depth 尽量参数化
7. Top-level integration module 只 wiring，不放逻辑
8. Datapath 与 control 尽量分模块

## Module Descriptor Template
```json
{
  "module_name": "my_fifo",
  "purpose": "Async FIFO for CDC crossing",
  "clock_domain": ["clk_a", "clk_b"],
  "reset": "arst_n (async active-low)",
  "parameters": ["DEPTH", "WIDTH"],
  "ports": [],
  "sub_modules": [],
  "complexity_estimate": "LOW | MEDIUM | HIGH"
}
```

## QoR Metrics
- 所有 microarch block 至少映射一个 module
- 所有 interface 映射 port
- CDC crossing 显式标记

## Output Required
- Module hierarchy tree
- Per-module descriptor JSON
- Interface/port document
```

---

### 4.2 `sv-rtl-coding/SKILL.md`

```markdown
# Skill: RTL — SystemVerilog Coding Standards

## Purpose
保证 RTL 可综合、可读、可维护。

## Domain Rules — General
1. 使用 logic，不依赖 wire/reg 旧式区分
2. Port 全部显式 type/direction
3. `default_nettype none`，禁止 implicit net
4. always_comb 必须完整赋值，不推 latch
5. always_ff 不用 blocking assignment
6. always_comb 不用 non-blocking assignment
7. 一个 register/register-group 对应一个 always block
8. Register 必须有明确 reset 策略

## Naming Conventions
- Clock：clk_[domain]
- Reset：rst_n_[domain] 或 rst_[domain]
- Active-low：_n
- Registered：_q
- Next-state/combinational：_d
- Parameter：UPPER_SNAKE_CASE
- Module/signal：lower_snake_case

## Synthesis Constraints
1. RTL 中禁止 #delay
2. ASIC RTL 不使用 initial block
3. 避免 casez/casex，优先 unique case
4. Fanout >32 时必须有 buffering intent
5. Pipeline register 用 _q 标识
6. 禁止 combinational loop

## CDC Rules
1. Single-bit crossing：2-FF synchronizer
2. Multi-bit data：async FIFO/handshake
3. Async-FIFO pointer crossing：Gray code
4. 禁止同步逻辑直接采样 asynchronous data

## Power Intent — Clock Gating
优先读取 architecture handoff 的 `clock_power_budget`；
不存在时可用 toggle coverage 估计 activity。

1. High opportunity（α<0.15）：在最外层 enable boundary 插 library ICG，不能只依赖 synthesis inference
2. Moderate（0.15≤α<0.40）：宽度 >32 bit 的 register file/datapath 建议 sub-block ICG
3. Always-on（α≥0.40 或有架构理由）：不强制 ICG，但在 clock port 记录原因
4. ICG enable 必须注册，combinational enable 是 lint error
5. 只用 library-approved ICG cell，不写 behavioral clock-gating
6. `clock_gating_coverage = ICG 后 register bits / domain total register bits ×100%`
   High-opportunity domain QoR gate ≥60%

## Output Required
- 每 module RTL .sv
- Self-checking SVA
- 非显然逻辑 inline comment
- Per-domain clock_gating_coverage
```

---

### 4.3 `sv-rtl-lint/SKILL.md`

```markdown
# Skill: RTL — Lint Checking

## Purpose
在 simulation/synthesis 前发现 coding error、style violation 和 synthesis mismatch。

## Lint Rule Categories
1. ERROR：latch、incomplete assignment、X propagation、undriven output、multi-driver
2. WARNING：unused port/parameter、constant condition、truncation、bit-width mismatch
3. INFO：naming/comment coverage，可 waive

## Recommended Tools
- Synopsys SpyGlass
- Cadence HAL
- Siemens 0-In
- Verilator

## Waiver Process
- Waiver 必须包含 signal、rule ID、justification、approver
- ERROR-level waiver 需要 architect approval
- 全部 waiver 写入 lint_waivers.csv

## QoR Metrics
- ERROR =0
- WARNING 全部 review/waive
- 全部 RTL file 都必须检查

## Output Required
- Lint report
- Waiver file
- Clean lint summary
```

---

### 4.4 `sv-rtl-cdc/SKILL.md`

```markdown
# Skill: RTL — CDC and RDC Analysis

## Purpose
综合前验证全部 CDC/RDC crossing 正确处理。

## CDC Rules
1. 每个 crossing 使用 approved synchronizer
2. Single-bit control 至少 2-FF
3. Multi-bit data 使用 async FIFO/handshake
4. Pulse crossing 使用 pulse stretcher + synchronizer
5. 检查 metastability、missing synchronizer、reconvergent fanout

## RDC Rules
1. 明确定义全部 reset domain
2. Reset deassertion 在 receiving clock domain 同步
3. Reset source 间禁止组合逻辑
4. Powered-down domain 需要 isolation
5. Retention register 的 UPF annotation 正确

## QoR Metrics
- CDC unwaived =0
- RDC unwaived =0
- Tool constraint 中全部 clock domain 都覆盖

## Output Required
- CDC/RDC report
- Synchronizer instance list
- Waiver file
```

---

### 4.5 `sv-rtl-synth-check/SKILL.md`

```markdown
# Skill: RTL — Synthesis Readiness Check

## Purpose
在正式 synthesis handoff 前做早期综合，提前发现 timing/area/synthesis 问题。

## Domain Rules
1. Target frequency + typical corner 综合
2. 检查 unmapped cell
3. Critical path 给 architect review
4. Area 与 microarch estimate 对比，<120% 可接受
5. 检查 multi-driven net / unresolved X
6. 找 high-fanout net
7. Clock definition 全部能综合

## QoR Metrics
- WNS > -0.5ns 作为未充分优化早期综合的参考
- Area < microarch estimate 120%
- Unmapped cell =0
- Multi-driven net =0

## Output Required
- Area report
- Timing critical-path report
- RTL fix recommendation
```

---

### 4.6 `sv-rtl-signoff/SKILL.md`

```markdown
# Skill: RTL — Design Sign-off

## Purpose
确认 RTL 完整、正确，可以交付 simulation/synthesis。

## Sign-off Checklist
- [ ] Planning 中全部 module 已实现
- [ ] Lint 0 error，warning 全 review
- [ ] CDC 0 unwaived
- [ ] RDC 0 unwaived
- [ ] Synth check timing 可接受
- [ ] Integration port 全连接
- [ ] 关键 property 有 SVA
- [ ] Code review 完成
- [ ] filelist/compile order 完整
- [ ] High/moderate gating domain 已按策略插 ICG
- [ ] Always-on domain 有原因说明
- [ ] High-opportunity domain clock_gating_coverage ≥60%

## Output Required
- RTL file package
- filelist.f
- Compile-order document
- Assertion library
- RTL sign-off record
```

---

## 5. Orchestrator System Prompt

```
You are the RTL Design Orchestrator for SystemVerilog chip design.

You take a microarchitecture document and guide RTL development through
module planning, coding, lint, CDC analysis, synthesis check, and sign-off.

STAGE SEQUENCE:
  module_planning → rtl_coding → lint_check → cdc_rdc_analysis →
  synth_check → rtl_signoff

LOOP-BACK RULES:
  - lint_check FAIL               → rtl_coding (max 5x)
  - cdc_rdc_analysis FAIL         → rtl_coding (max 3x)
  - synth_check FAIL (timing)     → rtl_coding (max 2x)
  - synth_check FAIL (area)       → rtl_coding or module_planning (max 2x)
  - rtl_signoff FAIL (missing)    → module_planning (max 1x)
  - rtl_signoff FAIL (quality)    → rtl_coding (max 2x)

Output: Synthesis-ready RTL package with sign-off report.
```

> 固定 stage 名、枚举和机器接口保留英文。
