# 可测性设计（DFT）流程——完整架构设计
## Orchestrator + Stage Agent + Skill

> **目的**：由 AI 驱动完整 DFT 流程，包括 scan insertion、ATPG、BIST、JTAG/boundary scan 以及 DFT sign-off。确保制造出来的芯片具备完整可测试性，并满足 DPPM、fault coverage 等质量目标。

---

## 1. 共享状态对象

```json
{
  "run_id": "dft_001",
  "design_name": "my_chip",
  "inputs": {
    "netlist":          "path/to/netlist.v",
    "sdc":              "constraints.sdc",
    "dft_spec":         "dft_architecture.md",
    "tech_lib":         "cells.lib",
    "fault_coverage_target": 99.0,
    "dppm_target":      10
  },
  "stages": {
    "dft_architecture":   { "status": "pending", "output": {} },
    "scan_insertion":     { "status": "pending", "output": {} },
    "atpg":               { "status": "pending", "output": {} },
    "bist_insertion":     { "status": "pending", "output": {} },
    "jtag_setup":         { "status": "pending", "output": {} },
    "dft_signoff":        { "status": "pending", "output": {} }
  },
  "fault_coverage": 0.0,
  "scan_chains":    [],
  "flow_status": "not_started"
}
```

---

## 2. Stage Sequence

```
[DFT Architecture]
        │
        ▼
[Scan Insertion] ───────┐
        │                │
        ▼                │
      [ATPG]             │
        │ coverage < target
        └────────────────┘
        │ coverage met
        ▼
[BIST Insertion]
        │
        ▼
[JTAG Setup]
        │
        ▼
[DFT Sign-off]
        │
        ├─ fail → Scan Insertion / 对应失败 stage
        └─ pass → Tape-out Ready
```

### Loop-Back Rules

| Failure | Loop Back To | Max |
|---|---|---:|
| ATPG 后 fault coverage < target | Scan Insertion | 2 |
| Scan chain length imbalance > 20% | Scan Insertion | 2 |
| DFT sign-off 缺失 JTAG connectivity | JTAG Setup | 2 |
| DFT sign-off BIST failure | BIST Insertion | 2 |

---

## 3. Skill 文件规格

### 3.1 `sv-dft-architecture/SKILL.md`

```markdown
# Skill: DFT — Architecture Planning（架构规划）

## Purpose
在进行任何 DFT insertion 之前定义完整 DFT 策略。

## DFT Strategy Elements
1. Scan 架构：full-scan 与 partial-scan 决策
2. Scan chain 数：在 test time 与 routing overhead 之间权衡
   - 经验值：chain 数约为总 flip-flop 数的平方根
3. Scan chain length：等长平衡，目标 ±5%
4. Compression：大设计（>1M FF）使用 EDT/OPMISR
5. BIST：所有 embedded SRAM 使用 MBIST；logic 可选 LBIST
6. JTAG：IEEE 1149.1 TAP controller；IO test 使用 boundary scan
7. At-speed test：LOC（launch-on-capture）或 LOS（launch-on-shift）
8. Test mode：scan_mode、mbist_mode、jtag_mode，必须互斥
9. Power domain：scan 架构必须遵守 UPF power-domain 边界

## DFT Constraints
- Scan enable (SE)：primary input，ATE 必须可控
- Scan data in (SDI)：每条 chain 一个
- Scan data out (SDO)：每条 chain 一个
- Test clock：独立于 functional clock，或使用其 gated 版本

## QoR Metrics
- DFT spec completeness：全部元素都已定义
- Estimated fault coverage：insertion 前 analytical estimate
- Estimated test time：满足 ATE budget

## Output Required
- DFT architecture 文档
- Scan chain plan（数量、预计长度、IO）
- Test mode 定义
```

---

### 3.2 `sv-dft-scan/SKILL.md`

```markdown
# Skill: DFT — Scan Insertion

## Purpose
将普通 flip-flop 替换为 scan flip-flop，并在 gate-level netlist 中连接 scan chain。

## Domain Rules
1. 所有普通 FF 替换为对应 scan cell（SDFF、SDFFRQ 等）
2. Clock-gating enable、async set/reset path（无专用 care cell 时）避免直接插 scan
3. 从 scan 中排除 memory-mapped register、MBIST controller、JTAG cell
4. 平衡 chain length；最长 chain 决定 test time bottleneck
5. FF >100K 时考虑 EDT compressor/decompressor
6. 跨 clock-domain chain 插入 lockup latch
7. Scan reorder 以最小 routing wirelength 为目标，优先 placement-aware reorder
8. 低覆盖率 net 可插入 controllability/observability test point

## Scan DRC Rules
- Clock 不得进入 scan data path
- Scan path 中不得出现 combinational feedback loop
- Functional mode 下 scan enable 必须 glitch-free
- 所有 scan FF 的 SI/SE 连接正确

## QoR Metrics
- Scan FF count：除明确排除项外覆盖全部 sequential element
- Chain count：符合架构规格
- Chain length balance：目标 ±5%
- Scan DRC：0 error

## Output Required
- Scan-inserted netlist
- Scan chain definition file (.scandef)
- Scan DRC report
```

---

### 3.3 `sv-dft-atpg/SKILL.md`

```markdown
# Skill: DFT — ATPG（Automatic Test Pattern Generation）

## Purpose
生成达到目标 fault coverage 的 test pattern，并形成可交付 ATE 的测试程序。

## Fault Models
| Fault Model | 说明 | Target Coverage |
|---|---|---:|
| Stuck-at (SAF) | Net stuck at 0/1 | ≥99% |
| Transition Delay | Slow-to-rise / slow-to-fall | ≥95% |
| Path Delay | Critical path timing fault | Critical paths |
| Bridging | 两条 net 短路 | ≥90% |
| Cell-Aware | Cell 内部 defect（PDK-based） | ≥95% |

## ATPG Domain Rules
1. 使用多个 capture clock 运行 ATPG
2. 使用 X-bounding 改善 pattern quality
3. 配置合理 abort limit
4. Untestable fault 分类为 Redundant 或 ATPG-Untestable，并记录
5. EDT design 使用 compressed pattern
6. At-speed pattern 由 STA 确认 launch/capture timing
7. Good-machine simulation failure 必须为 0

## QoR Metrics
- SAF coverage ≥99%
- Transition coverage ≥95%
- Pattern count 尽可能少，降低 ATE cost
- Good-machine simulation：0 failure

## Output Required
- STIL/WGL test pattern
- 各 fault model coverage report
- Untestable fault list + classification
```

---

### 3.4 `sv-dft-bist/SKILL.md`

```markdown
# Skill: DFT — BIST（Built-In Self Test）

## Purpose
为 embedded memory 插入并验证 MBIST controller，并按需对 logic 实施 LBIST。

## MBIST Rules
1. 相同 width/depth class 的 memory group 共用一个 MBIST controller
2. 使用 MATS+、March-C 或质量规范指定的 March algorithm
3. 覆盖 SRAM stuck-at、transition、coupling fault
4. BIST 期间 memory 与 functional logic 隔离
5. 所有 memory 同时 BIST 时验证 IR drop
6. 通过 JTAG TAP 或 dedicated BIST port 访问

## LBIST Rules
1. STUMPS：PRPG + MISR + scan chain
2. Alias probability <1e-10
3. LBIST clock 与 functional clock 分离
4. 排除 analog、IO 与 hard-macro internals

## QoR Metrics
- 所有 memory instance 均被 MBIST 覆盖
- MBIST fault coverage ≥99%
- Test power 满足 IR-drop budget
- LBIST alias probability 满足目标

## Output Required
- BIST-inserted netlist
- BIST controller connection report
- MBIST fault coverage report
- BIST power estimate
```

---

### 3.5 `sv-dft-jtag/SKILL.md`

```markdown
# Skill: DFT — JTAG and Boundary Scan

## Purpose
实现 IEEE 1149.1 TAP controller 与 boundary scan，用于 chip-level interconnect test 和 debug access。

## Domain Rules
1. TAP：TCK、TMS、TDI、TDO、TRST_N，需要 dedicated pin
2. 所有 digital IO pin 必须有 boundary-scan cell
3. 最少实现 BYPASS、IDCODE、SAMPLE/PRELOAD、EXTEST
4. IDCODE：32 bit，每个 device 唯一，符合 IEEE 1149.1
5. DR chain：boundary-scan register → BYPASS → user register
6. Core reset 时 TAP 仍应可访问
7. Pin 受限设计可选 IEEE 1149.7 Compact JTAG
8. Production 提供 OTP/fuse-based JTAG lockout

## QoR Metrics
- TAP DRC：全部必需 instruction 已实现
- Boundary scan chain：覆盖所有 IO
- JTAG connectivity simulation：PASS
- IDCODE：唯一且编程正确

## Output Required
- JTAG-inserted netlist
- BSDL file
- TAP connectivity report
```

---

## 4. Orchestrator System Prompt

```text
你是 DFT Orchestrator。

你负责从 DFT architecture、scan insertion 到 ATPG pattern generation 和 DFT sign-off
的完整流程。

STAGE SEQUENCE:
  dft_architecture → scan_insertion → atpg →
  bist_insertion → jtag_setup → dft_signoff

LOOP-BACK RULES:
  - atpg: SAF coverage < 99%      → scan_insertion（增加 test point，最多 2×）
  - scan_insertion: DRC fail      → scan_insertion（最多 3×）
  - dft_signoff: BIST fail        → bist_insertion（最多 2×）
  - dft_signoff: JTAG connectivity→ jtag_setup（最多 2×）

在 state_object.fault_coverage 中持续跟踪 fault coverage。
SAF coverage 未达到 target 前，不得进入 dft_signoff。
```
