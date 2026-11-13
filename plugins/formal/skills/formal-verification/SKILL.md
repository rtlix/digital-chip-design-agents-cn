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

`<MEM>` below is the resolved memory root（以下 `<MEM>` 表示已经解析出的 Memory 根目录），never the literal `memory/` directory。解析优先级为显式 `--memory-root` → `$CHIP_DESIGN_MEMORY_ROOT` → 中央默认路径 → 仓库 seed；可运行 `python3 plugins/infrastructure/skills/memory-keeper/memory_root.py` 查看实际路径。
任何 stage 前，如存在则读取：
1. `<MEM>/formal/knowledge.md` —— 已知 failure pattern、有效 tool flag、PDK/tool quirks。
2. `<MEM>/formal/run_state.md` —— 当前 `run_id/design_name/tool/last_stage`，用于中断恢复。

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
- **Cadence JasperGold** (`jg`，命令方言 `cadence`） — 业界常用的 FPV、CDC 和 DFT 形式验证
- **Synopsys VC Formal** (`vcf`，命令方言 `synopsys`） — 属性检查与等价验证
- **Siemens Questa Formal** (`qformal`，命令方言 `siemens`） — FPV 与覆盖率收敛

---

## Stage: property_planning

### Domain Rules
1. 每个规格特性至少对应一个属性或覆盖点
2. 所有属性均包含描述性名称和失败消息
3. 活性属性始终使用 `##[1:BOUND]` 限定范围
4. 优先使用 `$past()`、`$rose()`、`$fell()`，避免手写延迟逻辑
5. 使用 `disable iff` 实现复位门控
6. 将 RTL 交接内容作为输入：`design_state.rtl.unverified[]` 中的每项（RTL 流程未运行工具便作出的结论）都必须对应属性、覆盖点，或书面说明为何无法通过形式验证处理以及由谁检查。若 `rtl.unverified` 缺失，表示 RTL 流程未报告；在属性计划中注明，并自行从 RTL 推导以下目标。不能将“缺失”解读为“无需证明”。
7. 除默认参数外，还要在边界参数值上证明：一次证明只对一种参数配置成立。对 `WIDTH=1`、`DEPTH=1` 和 `2`、`N=1` 以及模块支持的非 2 次幂值重新运行。RTL 中带保护条件的 `initial`/`$fatal` 参数断言位于 `synthesis translate_off` 内，形式验证前端可能看不到，因此需要在环境中重申合法参数范围。

### Property Targets Lint Cannot Prove
lint 通过不能证明以下事项。只要相应结构存在，就必须检查：

| 结构 | 属性 |
|-----------|-----------|
| Ready/valid 接口 | 仅在 `valid && ready` 时传输；接受前不得撤回 `valid`；`valid && !ready` 时载荷稳定；复位时 `valid` 和 `ready` 为低 |
| FSM | 每个状态可达（cover）；每个状态有退出路径（有界活性）；从任何非法编码都能进入合法状态——使用 `unique case` 而无 `default` 的 FSM 必须检查，此断言是唯一的恢复检查 |
| 仲裁器 | grant 为独热或全零；持续请求者在 N 次授权内获得授权；仅在授权实际被消费后轮转 |
| FIFO | 满时禁止写、空时禁止读；退出复位时 `empty` 为 1、`full` 为 0；占用量不超过深度 |
| 算术 | 每个 `+`、`-`、`*` 及累加器不超出结果位宽；仅当规格明确允许时回绕 |
| 复位 | 退出复位后的首个周期，每个控制触发器具有指定值 |
| 死锁 | 不存在等待环；每个请求/应答及每次 credit 返回均满足有界活性 |

### QoR Metrics to Evaluate
- 每项规格特性对应属性或覆盖点
- 每个 `rtl.unverified[]` 项对应属性、覆盖点或明确理由
- 覆盖点证明关键状态可达

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

### Result Classifications
| Result | Meaning | Action |
|--------|---------|--------|
| PROVEN | 对所有可达状态成立 | 记录并继续 |
| CEX | 发现反例 | 在 cex_analysis 分析，将 RTL 缺陷交 RTL 流程，或修复假设 |
| VACUOUS | 前件从不触发 | 修复假设或属性 |
| INCONCLUSIVE | 界限太小或状态空间太大 | 增大界限或抽象 |
| UNREACHABLE | 覆盖点始终不可达 | 验证或豁免 |

### Strategies for Inconclusive
1. 增大 BMC 界限（k-induction）
2. 应用抽象（数据抽象、计数器抽象）
3. 分解：证明子属性，再组合为主属性
4. 若无法处理，将属性记为 `UNVERIFIED`，记录达到的界限及理由。有界证明不等于 PROVEN，假定正确也不算结果；二者均不得计入 PROVEN 总数，P0 属性保持 `UNVERIFIED` 会阻止签核。

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
1. 每个 CEX 都要判断是真实 DUT 缺陷，还是假设/环境缺陷
2. 真实 DUT 缺陷：不得在本流程修改 RTL。向 `design_state.fix_requests[]` 写入 `fix_request`（`failure_class=formal_cex`、CEX 轨迹路径、失败属性）并停止。RTL 流程按自身 lint 规则修复，再对结果重新运行 FPV。计为 RTL 缺陷，而非形式验证缺陷。
3. 假设缺陷：收紧假设，然后重新检查空洞证明（vacuity）
4. 约束不足导致的假 CEX：添加假设前明确记录
5. 未确定根因前绝不豁免 CEX
6. 不得通过缩小环境来消除 CEX。添加或收紧假设前，确认所排除行为在规格或上游模块合约中非法；排除合法激励只会掩盖缺陷。也不得通过弱化或删除失败属性来取得通过结果。
7. 说明如何定位缺陷：CEX 轨迹显示故障信号及周期时，将 `suspected_rtl.basis` 设为 `traced`；由现象推断位置时设为 `hypothesis`。

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


### Tool Notes: Formality and Conformal LEC (measured)

以下是 Sky130 CPU macro 上的实测经验：**Formality X-2025.06** 与 **Conformal LEC 24.10-p100**。Conformal 推荐调用为 `lec -nogui -xl -dofile <lec.do>`；所有真实 EQUIVALENT 结果必须先通过结构性 negative control。

**Formality：**
- 读取顺序很重要：先 reference library/RTL 和 `set_top`，再 implementation library/netlist；顺序错误可出现 **FM-236** 与 unlinked cell。
- 设置 `set_app_var hdlin_unresolved_modules error`，防止缺失模块被静默 black-box。
- **A DC netlist needs DC's SVF**。在实测中，没有 SVF 时有 **143 reference registers** 无法匹配；SVF 需在 DC 中 `set_svf <file>` 并由 Formality 消费。
- `report_*` 输出使用 `redirect -file <f> { report_... }`，而不是 shell 重定向。
- Post-route diode 可能作为无功能 black box；同时运行一个 **diode-stripped** copy，要求该副本 unmatched=0。

**Conformal：**
- Genus 的自动 dofile 可能依赖 **Conformal_Ultra** license；因此使用 `-xl`。
- 首行必须保持 `tclmode`；需要退出时可切 `vpxmode`。
- 除 guided compare 外，再运行一个 **direct** compare，避免 implementation-information/SVF-like hint 掩盖问题。

**Negative controls on flat netlists：**
- **Negative control before trusting EQUIVALENT**：在 revised netlist 上故意反相一个 flop D 或交换一个逻辑门输入，要求 Formality/Conformal 都报告不等价。
- **Anchor mutants on structure, not on literal names**：优化/重布线会改名甚至 resize，例如 `a211o_1` → `a211o_2`；mutator 应按 cell family/net role 查找，并在找不到 anchor 时 **fail loudly**。
- Formality 的成功 verdict 是 `Verification SUCCEEDED`；FAILED/INCONCLUSIVE 都不能当作等价。

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
- [ ] 无 空洞证明（vacuous proof）
- [ ] 所有 CEX 已解决或有批准的 disposition
- [ ] LEC unmatched/non-equivalent point 为 0
- [ ] 所有 INCONCLUSIVE：记录理由并标为 UNVERIFIED，不能标 PROVEN
- [ ] 每个 rtl.unverified[] 条目：已证明、已覆盖或附理由说明处理方式
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
每个 stage 完成后，按 `run_id` 在 `<MEM>/formal/experiences.jsonl` 写入/覆盖记录。
`run_id = formal_<YYYYMMDD>_<HHMMSS>`，流程开始时生成一次并复用。
最终 sign-off 前保持 `signoff_achieved:false`。

### Run state
任何工具运行前第一步写 `<MEM>/formal/run_state.md`，每 stage 成功后更新 `last_stage`。

### Optional: claude-mem index
如果 `mcp__plugin_ecc_memory__add_observations` 可用，把 applied fix 写入
`chip-design-formal-fixes`；否则静默跳过，JSONL 为 canonical record。
