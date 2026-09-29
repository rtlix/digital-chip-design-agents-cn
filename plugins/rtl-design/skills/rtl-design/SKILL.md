---
name: rtl-design
description: >
  SystemVerilog RTL 设计——模块规划、编码规范约束、lint 检查、CDC/RDC 分析以及综合就绪性验证。
  适用于 ASIC/FPGA RTL 的编写、审查、调试，以及检查已有 RTL 包是否具备综合条件。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill：RTL 设计（SystemVerilog）

## 调用方式

当本 Skill 被加载且用户提出 RTL 设计任务时，**不要直接执行各阶段**。
应立即启动 `digital-chip-design-agents:rtl-design-orchestrator` Agent，
并将用户完整请求及所有可用上下文传给它。
Orchestrator 负责下文定义的 stage 顺序、loop-back 规则和 sign-off 判据。

只有在 Orchestrator 流程中为某阶段读取本 Skill，或用户只是询问某个针对性参考问题而不是要求执行完整流程时，才直接使用本文件中的领域规则。

## 运行前上下文

在执行或建议**任何** stage 前，如果以下文件存在，应先读取：

1. `memory/rtl-design/knowledge.md` —— 已知失败模式、有效工具参数、PDK/工具特殊行为。每个 stage 的决策都应吸收其中经验。
2. `memory/rtl-design/run_state.md` —— 当前运行身份（`run_id`、`design_name`、`tool`、`last_stage`），用于中断后恢复。若不存在，表示新运行开始，Orchestrator 会在第一阶段前创建。

无论本 Skill 是由用户直接加载还是由 Orchestrator 中途调用，都必须执行上述预读，确保诊断前已查询历史修复经验。

## 目的

指导 RTL 从模块层次规划一路推进到 lint clean、CDC clean 和 synthesis-ready。
强制执行业界常用的 SystemVerilog 编码规范，并产出可交付仿真/综合的 RTL package。

---

## 支持的 EDA 工具

### 开源
- **Verilator**（`verilator --lint-only`）—— 快速 lint 和仿真
- **Slang**（`slang`）—— 现代、标准兼容的 SystemVerilog parser/elaborator
- **Surelog**（`surelog`）—— SystemVerilog preprocess/front-end，可配合 Yosys
- **sv2v**（`sv2v`）—— SystemVerilog 转 Verilog
- **Icarus Verilog**（`iverilog`）—— 适合快速 sanity check 的 Verilog/SV 仿真器

### 商业
- **Synopsys SpyGlass**（`spyglass`）—— lint、CDC、RDC、clock-domain 分析
- **Cadence JasperGold CDC**（`jg`）—— formal CDC 验证
- **Siemens Questa CDC**（`vsim`）—— CDC 分析与 sign-off

---

## Stage: module_planning

### 领域规则
1. 自顶向下拆分：从 top-level module 开始，逐级拆到 leaf cell
2. 每个 module 只承担一种明确职责
3. 编码前先定义全部 port（direction、width、type）
4. 为每个 module 标出全部 clock domain，并显式标记 CDC crossing
5. 标出全部 reset domain，并注明 synchronous / asynchronous
6. width/depth 尽量参数化
7. 顶层集成 module 只做 wiring，不放功能逻辑
8. datapath 和 control 尽量拆分为独立子模块

### 必须输出
- Module hierarchy tree
- 每个 module 的 descriptor（name、purpose、clock domain、ports、sub-modules）
- Interface/port list 文档

---

## Stage: rtl_coding

### 领域规则——通用
1. 优先使用 `logic`，不再依赖 wire/reg 区分
2. 所有 port 必须显式写明 type 和 direction
3. 每个文件顶部使用 `default_nettype none`
4. 禁止 latch：所有 `always_comb` 必须覆盖完整 case 和 assignment
5. `always_ff` 中禁止 blocking assignment（=）
6. `always_comb` 中禁止 non-blocking assignment（<=）
7. 每个寄存器或相关寄存器组使用独立 always block
8. 所有 register 都应显式 reset；ASIC 场景优先 synchronous reset

### 命名约定
- Clock：`clk_[domain]`
- Reset：`rst_n_[domain]`（低有效）或 `rst_[domain]`
- Active-low：后缀 `_n`
- Registered：后缀 `_q`
- Next-state：后缀 `_d`
- Parameter：`UPPER_SNAKE_CASE`
- Module/Signal：`lower_snake_case`

### 综合安全规则
1. RTL 中禁止 delay（#），仅可用于仿真代码
2. ASIC RTL 中禁止 initial block
3. 使用 `unique case` 和显式 don't-care，避免 `casez/casex`
4. fanout 超过 `design_state.constraints.timing.fanout_max`（默认 32）时标记出来，供 buffering intent 评审
5. 禁止 combinational loop
6. 各 pipeline stage 的寄存器使用 `_q` 后缀清晰标识

### CDC 规则
1. 所有 single-bit CDC crossing 使用 2-FF synchronizer
2. Multi-bit CDC data path 使用 async FIFO
3. Async FIFO crossing 使用 Gray-coded pointer
4. 同步逻辑中不得直接采样异步数据

### Power Intent（Clock Gating）

每个 clock domain 都应用以下规则。优先读取 architecture hand-off 中的 `clock_power_budget`。
对于 orchestrated Architecture → RTL 运行，`clock_power_budget` 是必需 handoff contract；缺失时视为上游交付违例，应中止并明确提示用户检查 architecture packaging。
对本地 RTL-only 运行，可使用 Verilator toggle-count 估算作为 fallback。

1. **High gating opportunity**：α < `design_state.constraints.power.activity_factors.default`（默认 0.15），或 Verilator toggle rate 低于该阈值。应在最外层 clock-enable 边界显式插入 ICG（`CLKGATETST_X*` 或工艺等价单元），不能完全依赖综合工具自动推断 clock gate。
2. **Moderate gating opportunity**：`activity_factors.default` ≤ α < `activity_factors.high`（默认 0.15–0.40）。对宽度 >32 bit 的 register file/datapath，在 sub-block 级插入 ICG。
3. **Always-on domain**：α ≥ `activity_factors.high`（默认 0.40），或 architecture hand-off 明确标为 always-on。无需 ICG，但在 clock port 声明处增加 `/* always-on: <reason> */`。
4. ICG enable 必须注册，满足 setup timing；combinational enable 视为 lint error。
5. 只使用库批准的 ICG cell（如 `CLKGATETST_*`，带 scan-enable override）；禁止行为级 `if (enable) clk_gated = clk` 写法。
6. 插入 ICG 后测量 `clock_gating_coverage`：
   `coverage = (register bits behind an ICG) / (total register bits in domain) × 100%`
   并在 `rtl_signoff` 输出中报告。

### Power Intent 支持工具

| Tool | 类型 | 用途 |
|------|------|-----|
| Verilator | 开源 | Toggle coverage → activity factor，用于 gating 分类 |
| SpyGlass (Synopsys) | 商业 | RTL power lint、缺失 ICG 检测 |
| VC Static (Synopsys) | 商业 | Power-intent rule checking |
| Questa PowerPro (Siemens) | 商业 | Formal power analysis |

### 必须输出
- 每个 module 的 RTL 源文件（.sv）
- 每个 module 的 SVA assertion 文件
- 对不明显逻辑增加 inline comment
- 每个 domain 的 `clock_gating_coverage`，附加到 sign-off 记录

---

## Stage: lint_check

### 领域规则
1. ERROR（必须修复）：latch、incomplete sensitivity、undriven output、multi-driven signal、X-propagation source
2. WARNING（必须评审）：unused port、truncated assignment、bit-width mismatch、constant condition
3. 所有 waiver 必须包含 signal name、rule ID、justification、approver
4. 未经 architect 批准，不允许 ERROR-level waiver
5. 所有 waiver 记录在 `lint_waivers.csv`

### QoR 指标
- ERROR count：进入下一阶段前必须为 0
- WARNING count：全部评审，waive 时提供理由
- 所有 RTL 文件均已检查，而不仅仅是 top-level

### 必须输出
- Lint report（按 file/rule）
- Waiver file
- Clean lint summary

---

## Stage: cdc_rdc_analysis

### CDC 规则
1. 每个 CDC crossing 使用批准的 synchronizer primitive
2. Single-bit control：至少 2-FF synchronizer
3. Multi-bit data：async FIFO 或 handshake protocol
4. Pulse crossing：pulse stretcher + synchronizer
5. 未豁免 CDC violation 必须为 0

### RDC 规则
1. 所有 reset domain 必须在 constraint 中显式定义
2. Reset de-assertion 必须同步到 receiving clock domain
3. Reset source 之间不得有 combinational logic
4. Retention register 必须有正确 UPF annotation

### QoR 指标
- CDC violations（unwaived）：0
- RDC violations（unwaived）：0
- 所有 clock domain 都已在工具 constraint 中验证

### 必须输出
- CDC/RDC report
- Synchronizer instance list
- Waiver file

---

## Stage: synth_check

### 领域规则
1. 在目标频率和 typical corner 下运行综合
2. 检查 unmapped cell
3. 找出 critical path；若 WNS < −0.5 ns，报告给 architect
4. 面积与 microarch 估算比较，<120% 视为可接受
5. 检查 multi-driven net 和 unresolved X
6. 标记需要 buffering strategy 的 high-fanout net
7. 验证所有 clock definition 都能正确综合

### QoR 指标
- 目标频率下 WNS：> −0.5 ns 在本阶段可接受；最终 sign-off 目标由 `design_state.constraints.timing.wns_ns_target` 决定，默认 0
- Area：< microarch estimate 的 120%
- Unmapped cell：0
- Multi-driven net：0

### 必须输出
- Synthesis area report
- Timing report（critical path）
- 必要时给出 RTL 修复建议

---

## Stage: rtl_signoff

### Sign-off Checklist
- [ ] planning 中的全部 module 已实现
- [ ] Lint：0 error，全部 warning 已评审
- [ ] CDC：0 unwaived violation
- [ ] RDC：0 unwaived violation
- [ ] Synthesis check：WNS 在可接受范围内
- [ ] 集成时所有 port 均已连接
- [ ] 关键 property 已有 SVA assertion
- [ ] Code review 已完成
- [ ] File list 与 compile order 已记录
- [ ] 所有 high/moderate gating opportunity domain 已插入 ICG
- [ ] Always-on domain 已使用 `/* always-on: <reason> */` 注释
- [ ] High-opportunity domain 的 `clock_gating_coverage` ≥ `design_state.constraints.power.gating_coverage_pct_min`%（默认 60%），并写入 sign-off record

### 必须输出
- RTL file package（全部 .sv）
- File list（filelist.f）
- Compile order 文档
- Assertion library（.sva）
- RTL sign-off record

---

## Constraint Validation

权威 schema 和 stage-entry validation 规则见
`plugins/meta/skills/pipeline-orchestration/SKILL.md` 的 Constraints Schema。

**进入 `module_planning` 时必填，缺失直接 hard-fail：**
- `constraints.clock.clk_mhz` —— synth_check 的目标频率

**可选约束（缺失时采用默认值）：**
- `constraints.timing.fanout_max`（默认 32）—— high-fanout threshold
- `constraints.timing.wns_ns_target`（默认 0）—— WNS sign-off target
- `constraints.power.gating_coverage_pct_min`（默认 60%）—— ICG coverage target
- `constraints.power.activity_factors`（默认 `{default: 0.15, high: 0.40}`）—— domain 分类

---

## Memory

### 每个 stage 完成后写入

每个 stage 完成后，无论当前是否处于完整 Orchestrator 会话，都以 `run_id` 为键，
在 `memory/rtl-design/experiences.jsonl` 中写入或覆盖一条 JSON 记录。
这样即使流程中断或单独调用 stage，也能持久化结果。

`run_id` 使用 `rtl-design_<YYYYMMDD>_<HHMMSS>`，流程开始时只生成一次，后续 stage 复用。
最终 sign-off 完成前，`signoff_achieved` 必须保持 false。

### Run state

在启动任何工具之前，第一件事写入 `memory/rtl-design/run_state.md`：

```markdown
run_id:      rtl-design_<YYYYMMDD>_<HHMMSS>
design_name: <design>
tool:        <primary tool>
start_time:  <ISO-8601>
last_stage:  null
```

只有某 stage 成功完成后，才把 `last_stage` 更新为该 stage 名。
该文件用于 wakeup-loop 与恢复会话，不依赖模型内存。

### 可选：claude-mem index

如果当前会话提供 `mcp__plugin_ecc_memory__add_observations`，在写入
`experiences.jsonl` 后，将每项已应用 fix 作为 observation 写入
`chip-design-rtl-design-fixes`。若工具不存在则静默跳过；JSONL 是权威记录。
