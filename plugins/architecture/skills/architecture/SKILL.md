---
name: architecture
description: >
  面向数字芯片设计的微架构探索、PPA 估算、风险评估和架构 sign-off。
  适用于评估设计候选、估算功耗/面积/性能、评估技术风险，
  或生成交付 RTL 设计的 microarchitecture 文档。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill: Architecture Evaluation（架构评估）

## Invocation
- **用户直接调用**并提出设计任务时：立即启动
  `digital-chip-design-agents:architecture-orchestrator`，传入完整用户请求和所有可用上下文，不要直接执行 stage。
- **由 `architecture-orchestrator` 在流程中调用**时：不要再启动新 Agent。将本文件作为只读规则库，仅返回调用方所需 stage rule、sign-off criteria 或 loop-back guidance。

在已运行的 Orchestrator 内再次启动自身会造成递归委派，必须禁止。

## Pre-run Context
执行或建议**任何** stage 前，若以下文件存在，先读取：
1. `memory/architecture/knowledge.md` —— 已知 failure pattern、有效 tool flag、PDK/tool quirks。
2. `memory/architecture/run_state.md` —— 当前 `run_id`、`design_name`、`tool`、`last_stage`，用于中断后恢复。

无论本 Skill 由用户加载还是 Orchestrator 中途读取，都执行该预读。

## Purpose
指导从产品 specification 到可交付 RTL 的 signed-off microarchitecture 文档的完整评估流程。覆盖规格拆解、候选架构探索、performance/PPA modelling、risk assessment 和 sign-off。

---

## Supported EDA Tools

### Open-Source
- **gem5**（`gem5`）—— 全系统微架构性能仿真
- **McPAT**（`mcpat`）—— 处理器 power/area/timing 估算
- **CACTI**（`cacti`）—— SRAM/cache power 和 area 估算
- **Python estimation scripts**（`python3 estimate.py`）—— 自定义 PPA 模型

### Proprietary
- **Synopsys Platform Architect** —— IP 级 performance/power exploration
- **ARM Performance Models** —— cycle-accurate ARM subsystem model
- **Cadence VSP** —— SoC 级 virtual prototyping

---

## Stage: spec_analysis

### Domain Rules
1. 将每项 requirement 分类为 functional、performance、power、area、interface、safety/security。
2. 识别描述不足的区域，列为 product team open question。
3. 将每个 use case 映射到所需 hardware block（datapath、control、memory、IO）。
4. 提取全部 interface requirement 与协议（AXI、PCIe、USB、Ethernet 等）。
5. 如适用，识别 ISO 26262、FIPS、CC 等安全/功能安全要求。
6. 优先级标为 Must-Have / Should-Have / Nice-to-Have。
7. 开始架构工作前必须形成结构化 requirements document。

### QoR Metrics to Evaluate
- Requirement coverage：spec 每一章节都至少映射到一项 requirement
- Ambiguity：所有 unresolved item 都进入 open-question list
- Interface completeness：所有外部接口均明确协议和 bandwidth

### Common Issues & Fixes
| Issue | Fix |
|---|---|
| Spec section 未映射 | 加入 open questions，不自行假设 |
| Interface bandwidth 未说明 | 继续前向 product team 请求 |
| Requirement 冲突 | 标记 blocker 并请求决策 |

### Output Required
- 结构化 requirements 文档（JSON/Markdown）
- 带 protocol/bandwidth 的 interface list
- Open questions list

---

## Stage: arch_exploration

### Domain Rules
1. 至少生成 3 个候选：conservative、balanced、aggressive。
2. 评估 pipeline depth：更深可提高 frequency，但增加 area/power。
3. 评估 parallelism：SIMD、superscalar、spatial unrolling，并计入 area/power 成本。
4. 按 use case 权衡 cache/memory hierarchy 的 size、associativity、latency 与 area。
5. 比较 bus、crossbar、NoC 等 interconnect topology 的 bandwidth/complexity。
6. 自研前先识别可复用 hard macro / licensed IP。
7. 每个 candidate 的假设必须显式记录。
8. 生成所有候选的 trade-off matrix。

### Trade-off Matrix Template
| Candidate | Freq Target | Area Est. | Power Est. | Risk | Notes |
|---|---:|---:|---:|---|---|
| Option A | 1GHz | 3mm² | 300mW | Low | ... |
| Option B | 2GHz | 6mm² | 700mW | High | ... |

### QoR Metrics to Evaluate
- 至少 3 个具有明显不同 trade-off profile 的 candidate
- 每个 candidate 的 performance estimate 与 target 偏差在 20% 内
- 最终只能有一个推荐 candidate，并提供明确量化依据

### Output Required
- 全部候选的 trade-off matrix
- 推荐 candidate 与量化理由
- 每个 candidate 的 assumption/risk summary

---

## Stage: perf_modelling

### Domain Rules
1. 初期使用 Amdahl、Roofline 等 analytical model。
2. 复杂 pipeline 使用 TLM/SystemC 或 Python model。
3. 建模 compute、memory bandwidth、IO throughput 等所有 bottleneck。
4. Sweep clock frequency、parallelism、cache size 等关键参数。
5. 使用 use-case list 中具有代表性的 workload 验证。
6. 覆盖 best/typical/worst case。
7. 未验证的 model assumption 必须标记。

### QoR Metrics to Evaluate
- Throughput：至少比 target 高 10% margin
- Latency：worst-case workload 下满足 target
- Memory bandwidth：不得超过 DRAM/SRAM ceiling
- Model confidence：HIGH / MEDIUM / LOW

### Output Required
- Performance model（script/spreadsheet）
- 各 use case throughput/latency 结果
- Sensitivity analysis
- Modelled vs target 对比表

---

## Stage: power_area_estimation

### Domain Rules
1. Area 使用目标工艺库 scaling data（gates/mm²）。
2. Dynamic power：`P = α × C × V² × f`，activity factor 来自 use case。
3. Leakage：按目标 Vt mix 的 library characterization 估算。
4. Memory area：使用 SRAM compiler 的 depth × width 估算。
5. IO pad area：按 pad-ring 设计规则。
6. 加 15–20% margin，因为 RTL 实现不可能绝对最小。
7. 任一 estimate 超过 budget 的 80% 时立即告警。

### Clock Gating Opportunity Analysis
使用 dynamic power 已收集的 activity factor：
1. 对每个 clock domain 记录 use-case workload sweep（gem5 或 analytical model）得到的 α。
2. 使用 `design_state.constraints.power.activity_factors`（默认 `{default:0.15, high:0.40}`）分类：
   - α < default：**high gating opportunity**，预计可节省该 domain >30% dynamic power，列为 RTL must-have
   - default ≤ α < high：**moderate gating opportunity**，建议 clock gating，列为 should-have
   - α ≥ high：**always-active**，无明显 gating 收益，记录为 always-on
3. 生成 `clock_power_budget` 表：

| Domain | Frequency | α | Est. Clock Power (mW) | Gating Class |
|---|---:|---:|---:|---|
| core | 1 GHz | 0.08 | 45 | high |
| dsp | 500 MHz | 0.55 | 30 | always-on |

4. McPAT `clocking` 已建模 clock-network power，frequency sweep 必须反映每个 domain 的实际 frequency，不能只用单一 global clock。
5. 将 `clock_power_budget` 放入 RTL handoff，供 RTL Agent 定向插 ICG。

### Supported Tools for Clock/Power Analysis
| Tool | 类型 | 用途 |
|---|---|---|
| McPAT | 开源 | Clock network + dynamic/leakage power |
| gem5 | 开源 | 提取 workload activity factor |
| CACTI | 开源 | Memory clock power estimate |
| Yosys + ABC | 开源 | Post-synth switching activity cross-check（可选） |
| Synopsys PrimePower | 商业 | RTL-level power sign-off（可选） |
| Cadence Joules RTL | 商业 | RTL power analysis（可选） |

### QoR Metrics to Evaluate
- Area estimate：< `design_state.constraints.area.area_um2` 的 80%
- Dynamic power：< `design_state.constraints.power.power_mw` 的 80%
- Leakage：< `constraints.power.leakage_pct_max`%，默认 15%
- Clock-gating coverage：high-opportunity domain 中 ≥ `gating_coverage_pct_min`% register-bank bit，默认 60%
- 估算 confidence：register count 冻结时 HIGH，近似时 MEDIUM，按相似设计 scaling 时 LOW

### Output Required
- 分 block area breakdown
- dynamic/leakage/per-domain power breakdown
- 对 target 的 margin analysis
- `clock_power_budget`

---

## Stage: risk_assessment

### Domain Rules
1. Risk 类别：schedule、technical feasibility、IP availability、tool support、verification complexity、power closure、manufacturing yield。
2. 每项 risk 评分：Probability（1–5）× Impact（1–5）。
3. Risk score ≥15 视为 HIGH，sign-off 前必须有 mitigation plan。
4. IP risk：确认 availability、license timeline、silicon-proven 状态。
5. Tool risk：确认目标工艺节点的 EDA tool certification。
6. Verification risk：如果 TB complexity 预计 >6 个月，必须标记。
7. 每项 risk 必须有 owner。

### QoR Metrics to Evaluate
- Sign-off 时无未缓解 HIGH risk
- 每项 risk 都有 owner 和 mitigation plan
- Schedule risk 已结合团队 capacity 评估

### Output Required
- Risk register（ID、description、score、mitigation、owner）
- 管理层评审用 Top 5 risk

---

## Stage: arch_signoff

### Sign-off Checklist
- [ ] 全部 Must-Have requirement 已覆盖
- [ ] Performance model 满足 target，margin ≥10%
- [ ] Power/area < 对应 budget 的 80%
- [ ] 全部 HIGH risk 有 mitigation plan 和 owner
- [ ] Interface specification 完整并达成一致
- [ ] Memory map 已定义
- [ ] Clock domain 已识别，CDC strategy 已明确
- [ ] Reset strategy 已定义
- [ ] DFT strategy 已确认
- [ ] Verification strategy 已确认
- [ ] RTL coding guideline 已记录
- [ ] 已生成 `clock_power_budget`，每个 domain 已分类
- [ ] High-opportunity domain clock-gating coverage ≥ `gating_coverage_pct_min`%，默认 60%
- [ ] RTL handoff package 完整，包含 `clock_power_budget`

### Output Required
- Signed-off microarchitecture document
- 最终 trade-off decision record
- RTL design guideline
- Handoff package

---

## Constraint Validation
权威 schema 和 stage-entry validation 见
`plugins/meta/skills/pipeline-orchestration/SKILL.md` 的 Constraints Schema。

**进入 `spec_analysis` 时必填：**
- `constraints.clock.clk_mhz`
- `constraints.area.area_um2`
- `constraints.power.power_mw`

**可选：**
- `constraints.power.leakage_pct_max`（默认 15%）
- `constraints.power.gating_coverage_pct_min`（默认 60%）
- `constraints.power.activity_factors`（默认 `{default:0.15, high:0.40}`）

---

## Memory

### Write on stage completion
每个 stage 完成后都以 `run_id` 为键在 `memory/architecture/experiences.jsonl` 写入/覆盖一条 JSON record，使中断或单独 stage 调用也能保存数据。

`run_id = architecture_<YYYYMMDD>_<HHMMSS>`，流程开始时生成一次并复用。最终 sign-off 前保持 `signoff_achieved:false`。

### Run state
启动任何工具前第一步写 `memory/architecture/run_state.md`：

```markdown
run_id:      architecture_<YYYYMMDD>_<HHMMSS>
design_name: <design>
tool:        <primary tool>
start_time:  <ISO-8601>
last_stage:  null
```

每个 stage 成功完成后才更新 `last_stage`。文件/目录不存在时创建。

### Optional: claude-mem index
如果当前会话存在 `mcp__plugin_ecc_memory__add_observations`，在写 experiences 后把 applied fix 作为 observation 写入 `chip-design-architecture-fixes`；工具不存在则静默跳过。JSONL 是 canonical record。
