---
name: dft
description: >
  可测性设计（Design for Test）——包括扫描架构规划、扫描链插入（scan insertion）、ATPG 测试向量生成、
  嵌入式存储器 MBIST，以及 JTAG 边界扫描（JTAG boundary scan）。适用于规划 DFT 策略、插入 scan、
  生成测试 pattern，或验证芯片在量产制造阶段是否具备可测试性。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill：可测性设计（DFT）

## 调用方式

- **如果由用户直接调用**并给出 DFT 任务：立即启动
  `digital-chip-design-agents:dft-orchestrator` Agent，并将用户完整请求和所有可用上下文传递给它。
  不要直接执行各 stage。
- **如果由 `dft-orchestrator` 在流程中调用**：不要再次创建 Agent。
  将本文件视为只读参考，仅返回调用方所需的阶段规则、sign-off 标准或 loop-back 指南。

在已经运行的 Orchestrator 内再次启动自身会造成递归委派，必须禁止。

## 运行前上下文

在执行或建议**任何** stage 前，如果以下文件存在，应先读取：

1. `memory/dft/knowledge.md` —— 已知失败模式、有效工具参数、PDK/工具特殊行为。
   每个 stage 的决策都应吸收其中经验；若不存在则继续。
2. `memory/dft/run_state.md` —— 当前运行身份（`run_id`、`design_name`、`tool`、`last_stage`）。
   用于中断后的正确恢复；若不存在，表示新运行开始，Orchestrator 会在第一阶段前创建。

无论本 Skill 是由用户直接加载，还是由 Orchestrator 中途读取，都必须执行上述预读，以确保任何诊断前都已经查询历史修复经验。

## Purpose（目的）

指导完整 DFT 流程，从架构规划、ATPG pattern 生成、BIST 插入、JTAG 配置一直到 sign-off。
目标是保证制造后的芯片满足故障覆盖率和 DPPM 等质量指标。

---

## 支持的 EDA 工具

### 开源
- **Yosys DFT plugins**（`yosys`）—— 用于开源流程的基础 scan insertion
- **OpenROAD DFT utilities**（`openroad`）—— 在 OpenROAD/ORFS 流程中进行 scan insertion

### 商业
- **Synopsys TetraMAX ATPG**（`tmax`）—— 测试 pattern 生成、fault simulation 和压缩
- **Cadence Modus Test**（`modus`）—— ATPG、scan DRC 和 diagnosis
- **Siemens Tessent**（`tessent`）—— 完整 DFT 工具套件：scan、ATPG、MBIST、IJTAG

---

## Stage: dft_architecture

## Domain Rules（领域规则）
1. Scan 架构：ASIC 优先 full-scan，尽可能覆盖全部 sequential element
2. Scan chain 数量：经验值可取总 flip-flop 数的平方根，在 ATE 测试时间与布线之间权衡
3. Chain length 平衡：所有 chain 相对目标长度偏差控制在 ±5%
4. Compression：设计超过 1M FF 时使用 EDT/OPMISR，降低 ATE test time
5. MBIST：相同 width/depth 类别的 memory group 使用一个 controller
6. JTAG：采用 IEEE 1149.1 TAP controller；所有 IO pin 使用 boundary scan
7. At-speed test：选择 LOC（launch-on-capture）或 LOS（launch-on-shift），并与 test team 确认
8. Test mode：`scan_mode`、`mbist_mode`、`jtag_mode` 必须互斥
9. Power domain：scan 结构必须遵守 UPF power-domain 边界

### 必需的 DFT IO 信号
- `scan_en`（SE）：primary input，ATE 必须可控
- `scan_in[]`（SDI）：每条 chain 一个
- `scan_out[]`（SDO）：每条 chain 一个
- `test_clk`：独立于 functional clock，或使用其 gated 版本

## QoR Metrics（QoR 指标）
- DFT spec 完整：insertion 前已定义全部元素
- 预计 fault coverage：解析估算 ≥ 目标
- 预计 test time：不超过 ATE budget

## Output Required（必须输出）
- DFT architecture 文档
- Scan chain 规划（数量、预计长度、IO）
- Test mode 定义

---

## Stage: scan_insertion

### 领域规则
1. 将标准 FF 替换为对应 scan cell（SDFF、SDFFRQ 等）
2. Scan 排除项：memory-mapped register、MBIST controller、JTAG cell
3. 以下位置不应直接插 scan：clock-gating enable、async set/reset path（除非使用专用 care cell）
4. EDT compression：FF 数超过 100K 时插入 compressor/decompressor
5. Lockup latch：跨 clock-domain 的 chain 之间插入
6. Scan re-ordering：尽量降低 routing wirelength，优先 placement-aware reorder
7. Test point：对低覆盖率 net 增加 controllability/observability point

### Scan DRC 规则（进入 ATPG 前全部通过）
- Clock signal 不得进入 scan data path
- Scan path 中不得存在 combinational feedback loop
- Functional mode 下 scan enable 必须 glitch-free
- 所有 scan FF 的 SI/SE 连接正确

### QoR 指标
- Scan FF count：除明确排除项外，覆盖 100% sequential element
- Chain count/length：符合架构规格，偏差 ±5%
- Scan DRC：0 error

### 必须输出
- Scan-inserted netlist
- Scan chain definition file（.scandef）
- Scan DRC report

---

## Stage: atpg

### Fault Model 目标

| Fault Model | 目标覆盖率 |
|---|---|
| Stuck-at（SAF） | ≥ `design_state.constraints.dft.saf_coverage_pct`%（默认 99%） |
| Transition Delay | ≥ `design_state.constraints.dft.transition_coverage_pct`%（默认 95%） |
| Cell-Aware | ≥ `design_state.constraints.dft.cell_aware_coverage_pct`%（默认 95%） |
| Bridging | ≥ `design_state.constraints.dft.bridging_coverage_pct`%（默认 90%） |
| Path Delay | 仅关键路径 |

### 领域规则
1. 在多个 capture clock 条件下运行 ATPG；transition test 同时覆盖慢速和快速条件
2. 使用 X-bounding 提升 pattern 质量
3. Untestable fault 分类为 Redundant 或 ATPG-Untestable，并全部记录
4. EDT 设计使用 compressed pattern
5. At-speed pattern 在 sign-off 前必须通过 STA 检查 capture timing
6. 所有 pattern 必须做 good-machine simulation；允许失败数为 0

### QoR 指标
- SAF coverage：≥ `constraints.dft.saf_coverage_pct`，默认 99%
- Transition coverage：≥ `constraints.dft.transition_coverage_pct`，默认 95%
- Pattern count：尽量减少，ATE 时间直接影响测试成本
- Good-machine simulation：0 failure

### 必须输出
- Test pattern file（STIL 或 WGL）
- Fault report（各 fault model 的 coverage）
- Untestable fault 列表及分类

---

## Stage: bist_insertion

### MBIST 规则
1. 相同 width/depth 类别的 memory group 使用一个 MBIST controller
2. March algorithm：MATS+、March-C，或质量规范指定算法
3. BIST 期间 memory 必须与 functional logic 隔离
4. 所有 memory 同时运行 BIST 时验证 IR drop
5. 通过 JTAG TAP 或专用 BIST port 访问

### LBIST 规则（如需要）
1. STUMPS 架构：PRPG + MISR + scan chain
2. Alias probability 目标 < 1e-10
3. LBIST clock 与 functional clock 分离，通常使用分频时钟

### QoR 指标
- MBIST：覆盖所有 memory instance
- MBIST fault coverage：≥ `design_state.constraints.dft.mbist_coverage_pct`%（默认 99%）
- BIST power：测试期间满足 IR-drop budget
- LBIST alias probability：满足目标（如适用）

### 必须输出
- BIST-inserted netlist
- BIST controller connection report
- MBIST fault coverage report
- BIST power estimate

---

## Stage: jtag_setup

### 领域规则
1. TAP pin：TCK、TMS、TDI、TDO、TRST_N，需要专用 pad
2. Boundary scan cell：所有 digital IO pin 都必须有 BSR cell
3. 必需 instruction：BYPASS、IDCODE、SAMPLE/PRELOAD、EXTEST
4. IDCODE register：32 bit，每个 device 唯一，符合 IEEE 1149.1
5. Core 处于 reset 时 TAP 仍应可访问
6. Security：量产芯片提供基于 OTP/fuse 的 JTAG lockout 机制

### QoR 指标
- TAP DRC：全部必需 instruction 已实现
- Boundary scan chain：所有 IO 均已包含
- JTAG connectivity simulation：PASS
- IDCODE：唯一且格式正确

### 必须输出
- JTAG-inserted netlist
- BSDL file
- TAP connectivity report

---

## Stage: dft_signoff

### Sign-off Checklist
- [ ] Scan DRC：0 error
- [ ] SAF coverage：≥ `design_state.constraints.dft.saf_coverage_pct`%（默认 99%）
- [ ] Transition coverage：≥ `design_state.constraints.dft.transition_coverage_pct`%（默认 95%）
- [ ] Good-machine simulation：0 failure
- [ ] MBIST：全部 memory 被覆盖；coverage ≥ `design_state.constraints.dft.mbist_coverage_pct`%（默认 99%）
- [ ] JTAG：BSDL 已生成并验证
- [ ] DFT netlist：与 pre-DFT netlist 做 LEC，结果 EQUIVALENT

### 必须输出
- DFT sign-off report
- 最终 test pattern files
- BSDL file
- DFT netlist（提供给 PD）

---

## Constraint Validation

权威 schema 和 stage-entry 校验规则见
`plugins/meta/skills/pipeline-orchestration/SKILL.md` 的 Constraints Schema。

**DFT 没有必填 constraint key**，本域所有约束都有 schema 默认值。

**可选 constraint：**
- `constraints.dft.saf_coverage_pct`（默认 99）—— stuck-at fault coverage 目标
- `constraints.dft.transition_coverage_pct`（默认 95）—— transition-delay coverage 目标
- `constraints.dft.cell_aware_coverage_pct`（默认 95）—— cell-aware fault coverage 目标
- `constraints.dft.bridging_coverage_pct`（默认 90）—— bridging fault coverage 目标
- `constraints.dft.mbist_coverage_pct`（默认 99）—— MBIST memory fault coverage 目标
- `constraints.dft.chain_balance_pct`（默认 5）—— chain length 最大偏差百分比

用这些值评估 QoR 时，应在 history 中设置对应 `constraint_ref`，例如
`"dft.saf_coverage_pct"`。

---

## Memory

### Stage 完成后写入

每个 stage 完成后，无论当前是否运行完整 Orchestrator，都在
`memory/dft/experiences.jsonl` 中以 `run_id` 为键写入或覆盖一条 JSON 记录。
即使流程被中断或只调用单独 stage，也能持久保存结果。

`run_id` 使用 `dft_<YYYYMMDD>_<HHMMSS>`，在流程开始时只生成一次，后续 stage 复用。
每条 JSON record 都必须包含顶层 `"run_id"` 字段且与该键一致；如果缺失，写入前必须拒绝或重新生成。
最终 sign-off 完成前，`signoff_achieved` 必须为 false。

### Run state

启动任何工具前，第一件事写入 `memory/dft/run_state.md`：

```markdown
run_id:      dft_<YYYYMMDD>_<HHMMSS>
design_name: <design>
tool:        <primary tool>
start_time:  <ISO-8601>
last_stage:  null
```

仅在某个 stage 成功完成后，才把 `last_stage` 更新为该 stage 名。
该文件用于 wakeup-loop 和恢复会话，不依赖模型内存。
文件或父目录不存在时创建。

### 可选：claude-mem index

如果当前会话存在 `mcp__plugin_ecc_memory__add_observations`，在写入
`experiences.jsonl` 后，将每个 applied fix 作为 observation 写入实体
`chip-design-dft-fixes`。工具不存在则静默跳过；JSONL 是权威记录。
