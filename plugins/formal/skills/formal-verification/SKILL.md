---
name: formal-verification
description: >
  形式属性验证（FPV）和逻辑等价性检查（LEC）。适用于穷尽式证明设计属性、
  检查 RTL 与 gate-level netlist 等价性、形式化验证 CDC，或关闭仿真难以高效覆盖的验证缺口。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill: Formal Verification (FPV + LEC)（形式验证）

## Invocation
用户提出 formal verification 任务时，**不要直接执行 stage**；立即启动
`digital-chip-design-agents:formal-orchestrator` 并传入完整请求和上下文。
仅当 Orchestrator 中途读取本 Skill 获取某 stage 的指导，或用户只问针对性参考问题时，
才直接使用本文件规则。

## Pre-run Context
任何 stage 前，如存在则读取：
1. `memory/formal/knowledge.md` —— 已知 failure pattern、有效 tool flag、PDK/tool quirks。
2. `memory/formal/run_state.md` —— 当前 `run_id/design_name/tool/last_stage`，用于中断恢复。

## Purpose
利用形式方法穷尽证明设计属性与等价性，补充 simulation-based verification，
用于 correctness proof、protocol compliance、CDC/formal closure 和 RTL↔netlist equivalence。

---

## Supported EDA Tools

### Open-Source
- **SymbiYosys**（`sby`）—— formal orchestration
- **Yosys**（`yosys`）—— elaboration/netlist/formal front-end
- **Boolector / Z3** —— SMT solver
- **ABC** —— logic synthesis/verification
- **Tabby CAD Suite** —— commercial-supported YosysHQ formal stack

### Proprietary
- **Cadence JasperGold**（`jg`）
- **Synopsys VC Formal**（`vcf`）
- **Siemens Questa Formal**（`qformal`）

---

## Stage: property_planning

### Domain Rules
1. 每个 P0 requirement 至少对应一条 property。
2. Property 分类：safety、liveness、protocol、data-integrity、control/FSM。
3. Property 名称应可追溯到 spec feature。
4. Assumption 只约束环境合法行为，不能约束掉 DUT bug。
5. 对 liveness property 使用 bounded proof 或明确 fairness assumption。
6. 同时规划 cover property，确认重要状态确实 reachable。
7. Property 必须与 simulation assertion/coverage 尽量复用。

### QoR Metrics to Evaluate
- P0 requirement property coverage：100%
- 每条 property 都有 owner/priority/expected proof mode
- 环境 assumption 已审查，不得过度约束 DUT

### Output Required
- Property plan
- SVA property/assumption/cover 列表
- Requirement → property traceability table

---

## Stage: environment_setup

### Domain Rules
1. 明确 clock/reset，并对 reset deassertion 建模。
2. Protocol input 用合法 transaction assumption 约束。
3. 不得直接 assume DUT output。
4. 对 unconstrained input 做 X/范围检查。
5. Formal harness 与 DUT 分离，优先 bind/checker。
6. 每次修改 assumption 后都运行 vacuity check。
7. 对多 clock domain 明确 ratio/relationship；真正 asynchronous 时不要伪造同步关系。

### QoR Metrics to Evaluate
- 0 obvious over-constraint
- 所有 primary input 均有明确环境语义
- Vacuity check clean

### Output Required
- Formal harness
- Assumption file
- Clock/reset/environment constraint
- Vacuity report

---

## Stage: fpv_run

### Domain Rules
1. P0 property 优先运行并 closure。
2. 区分 PROVEN、FAILED/CEX、UNKNOWN/INCONCLUSIVE。
3. UNKNOWN 时逐步增加 bound/engine，而不是直接声称 PASS。
4. CEX 必须保存 trace/waveform 和 failing property。
5. 发现 RTL bug 时创建结构化 `fix_request`，交给 Meta pipeline，不在 formal 域自行改 RTL。
6. 每轮 proof 记录 engine、bound、runtime、memory 与结果。

### QoR Metrics to Evaluate
- P0 unproven：0 才可 sign-off
- Vacuous proof：0
- CEX 均已分类为 DUT bug / environment issue / property issue
- UNKNOWN 均有明确后续处理

### Output Required
- Property result table
- CEX trace
- Proof log/engine summary
- Open issue list

---

## Stage: cex_analysis

### Domain Rules
1. 从最早 divergence cycle 开始分析。
2. 区分 assumption violation、property bug 与 RTL bug。
3. 记录最小触发 sequence、相关 signal 和疑似 RTL module/file。
4. DUT bug 使用 `fix_request` schema 写入 `design_state.json`。
5. Property/environment bug 在本域修复后重新 proof，不得错误路由到 RTL。
6. 保留原始 CEX 作为 regression/formal re-check 证据。

### QoR Metrics to Evaluate
- 每个 CEX 均完成 root-cause classification
- DUT CEX 有完整 fix_request context
- 无未分析 P0 CEX

### Output Required
- CEX root-cause report
- 最小 witness 描述
- 必要时的 fix_request

---

## Stage: lec_run

### Domain Rules
1. 明确 reference / implementation 版本与 provenance。
2. 正确处理 blackbox、memory macro、DFT/test logic 和 constant mapping。
3. 对 rename/optimization 使用结构化 compare point mapping。
4. Unmatched point 必须分类，不得直接 waive。
5. Synthesis 引入的不等价应路由给 synthesis domain；V1 不通过 RTL fix_request 处理。
6. Sign-off LEC 必须使用最终交付 netlist 与对应 RTL。

### QoR Metrics to Evaluate
- Unmatched compare point：0
- Non-equivalent point：0
- Waiver 全部有 justification
- Reference/implementation provenance 已确认

### Output Required
- LEC setup
- Equivalence report
- Unmatched/non-equivalent point list
- Waiver list

---

## Stage: formal_signoff

### Sign-off Checklist
- [ ] P0 property 全部 PROVEN
- [ ] 无 vacuous proof
- [ ] 所有 CEX 已解决或有批准的 disposition
- [ ] LEC unmatched/non-equivalent point 为 0
- [ ] Assumption 已审查
- [ ] Formal artifact 与最终 RTL/netlist 版本匹配

### Output Required
- Formal sign-off report
- Property summary
- LEC report
- Open/waived issue list

---

## Constraint Validation
权威 schema 见 `plugins/meta/skills/pipeline-orchestration/SKILL.md`。
Formal domain 没有必填 design constraint；缺失 optional constraint 时使用 schema default 并在 history reason 中注明。

---

## Memory

### Write on stage completion
每个 stage 完成后，按 `run_id` 在 `memory/formal/experiences.jsonl` 写入/覆盖记录。
`run_id = formal_<YYYYMMDD>_<HHMMSS>`，流程开始时生成一次并复用。
最终 sign-off 前保持 `signoff_achieved:false`。

### Run state
任何工具运行前第一步写 `memory/formal/run_state.md`，每 stage 成功后更新 `last_stage`。

### Optional: claude-mem index
如果 `mcp__plugin_ecc_memory__add_observations` 可用，把 applied fix 写入
`chip-design-formal-fixes`；否则静默跳过，JSONL 为 canonical record。
