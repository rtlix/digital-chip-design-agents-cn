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

`<MEM>` 表示已经解析出的 Memory root，而不是字面量 `memory/` 目录。解析优先级为：显式 `--memory-root` → `$CHIP_DESIGN_MEMORY_ROOT` → 中央默认路径 → 仓库内 seed；可用 `python3 plugins/infrastructure/skills/memory-keeper/memory_root.py` 查看实际路径，最终以 Orchestrator 的 `## Memory` 章节为准。为保持上游 contract 可检测：`<MEM>` below is the resolved memory root。
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

### LEC Flow
1. 读取 golden：RTL 或 pre-ECO netlist。
2. 读取 revised：post-synthesis 或 post-ECO netlist。
3. 映射 compare point：匹配 sequential/combinational key point。
4. 对全部 point 做 cone-of-influence 比较。
5. 报告 EQUIVALENT / UNMATCHED / ABORTED。

工具摘要（实测细节见下方 *Tool Notes: Formality and Conformal LEC*）：
- **Formality**（(`fm_shell`, dialect `synopsys`)；通过 `wrap-fm.sh`）：读取 library，reference 使用 `read_sverilog -r` / `read_verilog -r` 并 `set_top r:/WORK/<top>`，implementation 用 `read_verilog -i` / `set_top i:/WORK/<top>`；DC 流程有 SVF 时必须 `set_svf`，随后 `match`、`verify`。真正通过的 verdict 是 `Verification SUCCEEDED`；FAILED / INCONCLUSIVE 都不是等价。
- **Conformal**（(`lec`, dialect `cadence`)；命令形态 `lec -xl -nogui -dofile lec.do`，通过 `wrap-lec.sh`）：`read library`、`read design -golden`、`read design -revised`、`set system mode lec`、`add compare point -all`、`compare`、`report verification`。任何 Non-equivalent 或 Abort point 都不能算等价。
- **Yosys**：可使用 `equiv_make/equiv_simple/equiv_induct` 或 miter + SAT。

### Tool Notes: Formality and Conformal LEC (measured)

以下规则实测于 **Formality X-2025.06** 与 **Conformal LEC 24.10-p100**，目标为 Sky130 CPU macro（约 6k compare points、10 个 SRAM black box）。Formality 运行 `fm_shell -f <lec.tcl>`；Conformal 运行 `lec -nogui -xl -dofile <lec.do>`。所有 EQUIVALENT 结论都只有在 negative control 能失败后才可信。

**Formality**
- 顺序非常重要：`set_svf <dc.svf>` → `read_db -container r -technology_library <macro.db>` → `read_sverilog -container r -libname WORK ...` → `set_top r:/WORK/<top>`，然后才读 implementation 的 `.db` / netlist 并 `set_top i:/WORK/<top>`，最后 `match` / `verify`。如果 implementation library 在 reference `set_top` 前读入，实测会出现 **FM-236** 与 unlinked cell。
- 设置 `set_app_var hdlin_unresolved_modules error`，让缺 module 直接 fail，不能静默 black-box。SRAM behavioral stub 不应与 macro `.db` 混读；两侧应由同一 macro view 一致 black-box。
- **A DC netlist needs DC's SVF.** 实测缺 SVF 时有 **143 reference registers** unmatched；DC 的 merge/constant transformation 被 SVF 解释后才能正确匹配。SVF 也不能盲信：对 SVF 所描述关系制作 RTL/netlist mutant，若错误关系仍被“解释成等价”，setup 无效。
- `report_*` 不要用 shell `>` 直接重定向，使用 `redirect -file <f> { report_... }`。
- Post-route netlist 中 antenna/port-protection diode 可能在 Formality 中成为 implementation-only black box。并行跑一个 **diode-stripped** copy，要求该 copy unmatched=0。

**Conformal**
- Genus 的 `write_do_lec` 输出可能调用需要 **Conformal_Ultra** license 的 `analyze_extended_mapping`；plain `lec` 会失败，因此使用 `lec -xl`。不要直接改 Genus 原始 dofile，而是生成带 assert/substitution 的派生副本。
- dofile 第一行必须保持 `tclmode`；在其前插 comment 可能 abort。`exit -f` 在 tclmode 无效，应先切 `vpxmode`。Driver 用 bash 更稳妥。
- 除 Genus-guided compare 外，再跑一个 **direct** compare（去掉 Genus implementation-information/verification-information claim）与一个 flat compare；三者应一致。
- Post-route diode 同样建议在副本中 strip，并从 netlist 动态统计 expected diode 数，不能 hardcode。

**Negative controls on flat netlists**
- 每次 compare 都制作至少一个 structural mutant：例如反转一个 flop D，或交换已知逻辑 cone 中某 gate 的两个输入；每个 golden 都必须至少产生一个 failing point。
- **Anchor mutants on structure, not on literal names.** Flat/MCMM/re-route/resize 会改变 hierarchical/net/cell 名；例如 `a211o_1` → `a211o_2`。Mutator 应按 cell family、drive suffix、net role 等结构 pattern 找 anchor；找不到时必须 **fail loudly**，并通过 byte-compare 确认 mutant 真的与原始 netlist 不同。

### Domain Rules
1. Golden 与 revised 使用一致的设计约束语义；对纯 LEC setup 不用 timing exception 掩盖逻辑差异。
2. Scan chain reorder 使用 scan-aware/unaware 的正确 compare 模式。
3. Black box 必须在两侧一致；列出 unread/unlinked/black-box object。
4. Unmatched point 必须 root-cause，不得无理由 waive。
5. 每次 ECO 后都跑 LEC，不只 sign-off 跑。
6. **Negative control before trusting EQUIVALENT.** 对 intentionally mutated revised netlist 运行同一脚本，必须报告 non-equivalent。若 mutant 仍被判等价，说明 top、blackbox、SVF、constant cone 或 compare setup 有问题，真实 netlist 的 PASS 不可信。
7. Unmatched/unread object 逐名列出；“某 module 被 black-box 后 EQUIVALENT”只证明 module 外部，不证明内部。

### Common LEC Failures
| Failure | Fix |
|---|---|
| Optimizer removed logic | 查 removal report；必要时 set_dont_touch |
| Golden/revised setup 不一致 | 对齐 mode / defines / blackbox / library |
| Scan chain reordering | 使用正确 scan compare mode |
| Black box mismatch | 两侧使用同一 blackbox list |
| DC netlist 大量 unmatched register | 确认正确加载 DC SVF |

### QoR Metrics to Evaluate
- All compare points：EQUIVALENT
- Unmatched：0（或明确、批准且有独立 stripped-copy 证明）
- Aborted：0
- Negative control：必须得到 non-equivalent

### Output Required
- LEC run report
- Unmatched / aborted point analysis
- Negative-control mutant + verdict
- EQUIVALENT sign-off record

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
