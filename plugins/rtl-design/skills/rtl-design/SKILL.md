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

1. `<MEM>/rtl-design/knowledge.md` —— 已知失败模式、有效工具参数、PDK/工具特殊行为。每个 stage 的决策都应吸收其中经验。
2. `<MEM>/rtl-design/run_state.md` —— 当前运行身份（`run_id`、`design_name`、`tool`、`last_stage`），用于中断后恢复。若不存在，表示新运行开始，Orchestrator 会在第一阶段前创建。

无论本 Skill 是由用户直接加载还是由 Orchestrator 中途调用，都必须执行上述预读，确保诊断前已查询历史修复经验。

## Purpose（目的）

指导 RTL 从模块层次规划一路推进到 lint clean、CDC clean 和 synthesis-ready。
强制执行业界常用的 SystemVerilog 编码规范，并产出可交付仿真/综合的 RTL package。

---

## 支持的 EDA 工具

### 开源
- **Verilator**（`verilator --lint-only`）—— 快速 lint 和仿真
- **Slang** (`slang`) — 现代、符合标准的 SV 解析与 elaboration 工具；lint 使用 `slang -Weverything --ignore-unknown-modules`（完整 elaboration，见 lint_check 规则 6）
- **Surelog**（`surelog`）—— SystemVerilog preprocess/front-end，可配合 Yosys
- **sv2v** (`sv2v`) — SystemVerilog 到 Verilog 转换器；前端检查（lint_check 规则 15）用实际消费工具解析其输出
- **Icarus Verilog**（`iverilog`）—— 适合快速 sanity check 的 Verilog/SV 仿真器

### 商业
- **Synopsys SpyGlass** (`spyglass`，命令方言 `synopsys`） — lint、CDC、RDC 与时钟域分析
- **Cadence JasperGold CDC** (`jg`，命令方言 `cadence`） — 形式化 CDC 验证
- **Siemens Questa CDC** (`vsim`，命令方言 `siemens`） — CDC 分析与签核

---

## Stage: module_planning

## Domain Rules（领域规则）
1. 自顶向下拆分：从 top-level module 开始，逐级拆到 leaf cell
2. 每个 module 只承担一种明确职责
3. 编码前先定义全部 port（direction、width、type）
4. 为每个 module 标出全部 clock domain，并显式标记 CDC crossing
5. 标出全部 reset domain，并注明 synchronous / asynchronous
6. width/depth 尽量参数化
7. 顶层集成 module 只做 wiring，不放功能逻辑
8. datapath 和 control 尽量拆分为独立子模块

## Output Required（必须输出）
- Module hierarchy tree
- 每个 module 的 descriptor（name、purpose、clock domain、ports、sub-modules）
- Interface/port list 文档

---

## Stage: rtl_coding

适用范围：本阶段规则仅约束可综合 RTL。测试平台（`*_tb.sv`、`tb_*.sv`、`tb/` 下文件）、仅用于 bind 的断言文件、仅用于仿真的行为模型不在此范围；其中 `initial`、`#delay` 和阻塞赋值是正确用法，相应编码规则由 functional-verification Skill 定义。

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
- 端口方向：允许 `_i` / `_o` 后缀，但不强制

优先级：这些约定是本套件新 RTL 的项目标准。修改已有文件时遵循该文件现有约定；单个模块风格不同更不利。将差异记为信息说明，而非 lint 问题。

### 综合安全规则
1. RTL 中禁止 delay（#），仅可用于仿真代码
2. ASIC RTL 逻辑禁止 `initial`。唯一例外是 elaboration 阶段的参数断言：非法参数时使用 `initial` + `$fatal`，并包裹在 `// synthesis translate_off` / `// synthesis translate_on` 内，确保不会综合为逻辑。参数化模块必须拒绝无法实现的值（如 Gray 编码 FIFO 的非 2 次幂深度），不能生成错误逻辑。

3. 禁止 `casex`；`casez` 仅在有书面理由时使用；禁止 `full_case` / `parallel_case` pragma。无关位解码写为显式 `case` 项。

4. fanout 超过 `design_state.constraints.timing.fanout_max`（默认 32）时标记出来，供 buffering intent 评审
5. 禁止 combinational loop
6. 各 pipeline stage 的寄存器使用 `_q` 后缀清晰标识
7. FSM 的 case 策略：每个 FSM 选择一种并在注释中注明：
   - **默认：** 普通 `case` 加 `default`，进入恢复或错误状态。芯片中非法状态可能由 SEU 或启动时 X 产生，FSM 不能卡死。
   - **替代：** 无 `default` 的 `unique case`，配合覆盖非法状态恢复的并发断言，保留仿真/形式验证中的唯一性检查。
   - 绝不同时使用 `unique case` 和 `default`：前者断言非法状态不可能出现，后者却用于非法状态发生时恢复（slang：`-Wcase-redundant-default`）。

### CDC 规则
1. 所有 single-bit CDC crossing 使用 2-FF synchronizer
2. Multi-bit CDC data path 使用 async FIFO
3. Async FIFO crossing 使用 Gray-coded pointer
4. 同步逻辑中不得直接采样异步数据

### Domain Rules — Scan Readiness
阻碍扫描的 RTL 在此修复成本最低，DFT 流程只能在插入后报告。
1. 禁止 RTL 生成时钟（`assign gclk = clk & en;`），其后触发器在扫描模式下不可达。使用触发器使能，或带测试使能输入的库时钟门控单元（Power Intent 规则 5）。
2. 每个异步置位/复位都必须在测试模式下可由主输入控制。内部逻辑产生的复位在扫描移位时无法保持无效，须用 `scan_mode` 旁路到顶层复位。
3. 禁止由组合逻辑产生异步置位/复位。
4. 禁止片上三态总线，争用无法测试；使用 mux。
5. 有意设计的锁存器（lockup latch、时钟门控单元内部结构）必须实例化库单元，并按实例名在 `lint_waivers.csv` 豁免，不能从 RTL 推断。

### Domain Rules — Power Intent (Clock Gating)
对每个时钟域应用以下规则。从架构交接包读取 `clock_power_budget`。**对于编排的 Architecture → RTL 流程，该表是必需的交接合约；缺失时按交接违规处理，中止并明确要求用户通知上游补全交接包。** 对非编排流程或本地仅 RTL 运行，可回退到 Verilator 仿真切换次数估计来分类时钟域。

1. **高门控机会时钟域**（架构 α < `design_state.constraints.power.activity_factors.default`，默认 0.15；或 Verilator 切换率低于该阈值）：在最外层时钟使能边界插入 ICG 单元（`CLKGATETST_X*` 或工艺等效单元）。不能依赖综合推断时钟门控，必须在 RTL 显式插入 ICG。

2. **中等门控机会时钟域**（`activity_factors.default` ≤ α < `activity_factors.high`，默认 0.15–0.40）：对宽于 32 位的寄存器文件或数据路径，在子模块级插入 ICG。

3. **常开时钟域**（α ≥ `activity_factors.high`，默认 0.40；或架构交接明确为常开）：无需 ICG；在时钟端口声明处添加 `/* always-on: <reason> */` 注释。

4. ICG 使能必须寄存，以保证 setup 时序安全；组合使能属于 lint 错误。

5. 仅使用库批准的 ICG 单元（带 scan-enable 覆盖以支持测试的 `CLKGATETST_*`）；不能使用行为描述 `if (enable) clk_gated = clk`。

6. 插入 ICG 后测量 `clock_gating_coverage`：
   `coverage = (register bits behind an ICG) / (total register bits in domain) × 100%`
   即门控后寄存器位数除以该域总寄存器位数乘以 100%，并在 `rtl_signoff` 输出中报告。

### Power Intent 支持工具

| Tool | 类型 | 用途 |
|------|------|-----|
| Verilator | 开源 | Toggle coverage → activity factor，用于 gating 分类 |
| SpyGlass (Synopsys) | 商业工具，命令方言 `synopsys` | RTL power lint, missing ICG detection |
| VC Static (Synopsys) | 商业工具，命令方言 `synopsys` | Power-intent rule checking |
| Questa PowerPro (Siemens) | 商业工具，命令方言 `siemens` | Formal power analysis |

### 必须输出
- 每个 module 的 RTL 源文件（.sv）
- 每个 module 的 SVA assertion 文件
- 对不明显逻辑增加 inline comment
- 未经验证声明：审查中每个未运行工具的 CDC、复位、FSM、协议、算术或参数结论，现在就追加到未经验证声明列表（见 rtl_signoff），不能等签核时才写
- 每个 domain 的 `clock_gating_coverage`，附加到 sign-off 记录

---

## Stage: design_input_check

lint 工具只能报告提供给它的文件。本阶段在将任何 lint 消息解读为 RTL 结论前，先确认工具读取的是预期文件。本阶段不修改任何内容，仅输出报告与 PASS/FAIL。

### Domain Rules
1. 解析并打印工具将读取的 filelist **绝对路径**，以及选择该列表的项目/配置文件绝对路径。存在多个候选（受管理项目文件与用户覆盖目录、两个同名 filelist）时，说明工具使用哪个及原因。陈旧覆盖目录会静默绕过受管理项目文件及其设置的全部变量。

2. 将每个 include 目录按搜索顺序解析为绝对路径。include 搜索采用首个匹配：两个目录存在同名但内容不同的文件时，属于 **ERROR** 而非警告，工具会静默使用第一个并忽略第二个。指出文件名、所有包含它的目录以及最终获选目录。

3. 标出解析到声明的设计根目录之外的 include 目录和源文件，以及 include 集合可达的同级树，如 `X` 与 `X_v2`、`X_old`、`X_bak`，或包含同名文件的平行版本目录。

4. 生成输入（寄存器映射头文件、IP 配置头文件）的 include 路径上只能有一个生成版本的输出树，且其时间必须晚于生成器源码。

5. filelist 中每条路径均须存在。缺失 include 目录属于 ERROR，因为工具会继续查找后续包含该文件的目录。

6. 输入为 `.f` filelist 时，运行本 Skill 目录中的 `check_design_inputs.py` 并报告 JSON：
   `python3 check_design_inputs.py <filelist.f> --root <design root> [--env NAME=VALUE] [--generated OUT_DIR=SOURCE]`。
   脚本应用规则 2、3、5，对每个 `--generated` 对执行规则 4 的时间检查，并配合 `--rtl-dir` 和 `--list` 应用规则 8。规则 1，以及由厂商项目文件而非 `.f` 驱动的流程，按上述规则手工检查。

7. FAIL 时不得修改设计文件。修复位于输入集合中，通常只涉及 filelist 一行；在两个树之间作选择应由所有者决定。报告 `failure_class: "input_setup"`、`suggested_next_step: "escalate"`、文件、两个绝对路径及需修改的行。绝不回退到 `rtl_coding`，唯一例外为规则 8 中注册本次新增模块。

8. 注册：磁盘上每个模块必须对每个工具可见。仿真、lint、综合、PD、形式验证常使用独立源列表，往往存于 Makefile 变量。模块缺少于某列表时，转换器/综合器（sv2v、yosys）可能无错误地将其黑盒化，而读取另一列表的仿真回归无法发现。枚举项目中每个工具输入列表，将 Makefile 变量导出为文件
   （`make -s --eval='print-%:;@echo $($*)' print-<VAR> > <var>.f`），再运行
   `python3 check_design_inputs.py <filelist.f> --rtl-dir <rtl dir> --list <name>=<file> ... [--exempt <list>:<module>]`。
   每个 `module_not_in_list` 都是 ERROR，须指出列表和文件。豁免必须有明确理由（如 PD 列表不包含仅仿真的模型）。这是唯一不升级处理的 `design_input_check` 失败：本次新增的模块必须由本次运行加入列表，只编辑列表，不改 RTL。已有模块缺失，或无法编辑列表时，按规则 7 判为 `input_setup`。

### QoR Metrics to Evaluate
- 磁盘上存在、但不在某工具源文件列表且未豁免的模块数：必须为 0
- 两个目录中同名但内容不同的 include 文件数：必须为 0
- 缺失的 filelist、include 目录、源文件数：必须为 0
- 每个生成器在 include 路径上的生成输出树：恰好 1 个
- 同级版本树、设计根目录外路径、内容相同的重复头文件：逐项审查，记录理由后才能继续

### Output Required
- 设计输入报告：filelist 和配置的绝对路径、有序的绝对 include 目录，以及每项发现所涉及的路径
- 注册报告：检查过的每个源文件列表、各列表缺少的模块，以及每项豁免和理由
- 阶段状态：PASS，或 FAIL 且 `failure_class: "input_setup"`

---

## Stage: lint_check

### 领域规则
1. ERROR 级（必须修复）：锁存器、不完整敏感列表、未驱动输出、多驱动信号、X 传播来源。

2. WARNING 级（需要审查）：未使用端口、赋值截断、未使用参数、带符号/无符号混用。

3. 所有豁免必须包含信号名、规则 ID、理由和批准人。

4. ERROR 级豁免必须由架构负责人批准。

5. 所有豁免记录在 `lint_waivers.csv`。

6. slang 必须执行完整 elaboration：`slang -Weverything --ignore-unknown-modules <files>`。绝不能加 `--lint-only`，它跳过 elaboration，静默省略推断锁存器和多驱动诊断（均属 ERROR），使锁存器被误报为干净。`-Wall` 不是 slang 选项；Verilator 不受影响，`verilator --lint-only -Wall` 正确。

7. 在 filelist 上下文中 lint：将模块 filelist 作为一个整体编译，再报告本次写入或修改文件的发现。单独 lint 文件会把子模块视为未知，跨文件位宽也未检查。

8. filelist 中缺少的模块（库单元、硬宏、黑盒 IP）为 stub。仅由 stub 驱动网络上的未驱动或未使用发现不属于 ERROR，记录为信息并注明 stub 模块及其代表的库、宏或 IP。只有能指出其所代表对象时，stub 才可视为无害；本仓库中有自有 RTL 定义的未知模块属于缺失列表条目（`design_input_check` 规则 8），而非 stub。

9. 每项发现都注明证据。工具证明的发现引用工具消息和规则名；未运行工具的推理标为 `UNVERIFIED`。lint 通过不能证明 CDC、复位顺序、FSM 可达性、协议死锁或算术溢出。

10. 修复不得改变模块功能。每次修复后比较发现集合，而非数量：新增 ERROR 是回归，须回滚；连续两次发现完全相同表示无进展，应升级而非耗尽迭代；通过改变行为消除警告（如缩窄信号以消除截断警告，实际实现了截断）属于意图偏移，须回滚并升级。

11. 工具自行报告严重级别时，映射到上方级别以保持豁免有效：`BLOCKER` / `HIGH` → ERROR，`MEDIUM` → WARNING，`LOW` / `INFO` → 信息。

12. 规则检查未完成的运行实际执行了**零条**规则。解析/elaboration 致命错误、工具报告规则检查中止或跳过、文件缺失，都表示 ERROR/WARNING 数量未知；记为 `null`，不能写 `0`。结果不构成 RTL 证据，绝不能分类为 `functional`。

13. 编辑前对中止运行的每个 fatal 归因。以下属于输入集合失败（`input_setup`，升级，不改 RTL）：同次出现重复声明和未声明标识符 fatal（include 路径上混入两代生成头文件）；消息指出同一文件的两条路径；include/源文件不存在；fatal 位于本次未写入的文件。删除“重复”端口或补声明“未声明”信号只会压下消息并破坏正确 RTL。仅当解析错误局限于本次写入/修改的文件，且当前输入集合 `design_input_check` 通过时，才以格式错误输出（`tool_error`）回退到 `rtl_coding`，只修复语法。

14. 先按根因分类，再按严重级别：a）配置/输入失败，按规则 13；b）库模型噪声，如行为宏模型、标准单元 `specify` 块、厂商原语内的发现，注明模型并一次性豁免；c）RTL 本身发现，才适用规则 1–2 的级别。流程 Wrapper 退出非零不等于 lint 失败，它可能根据日志文字门控，在 lint 工具报 0 错误时仍判失败。读取工具自身错误数。

15. 前端检查：lint 不能证明下游前端接受该 RTL。Verilator、slang 和仿真器原生读取 SystemVerilog；综合前转换 RTL（sv2v、Surelog/UHDM、厂商 SV 到 Verilog 步骤）的流程生成的文件不会被这些工具读取。只要任一下游存在转换，必须对 filelist 执行转换，再由实际消费工具解析输出：
    `sv2v <files> > out.v && yosys -q -p 'read_verilog out.v; hierarchy -check -top <top>'`
    （先用 `read_verilog -lib <stubs>` 读取规则 8 的 stub）。作为独立门控报告命令与退出状态。SystemVerilog 合法而 Verilog-2005（IEEE 1364）非法的结构，如函数返回值直接部分选择 `f(x)[N-1:0]`，会通过 lint 和全部回归，仅在此失败；应先将结果赋给命名信号再选择。修复源结构，绝不修改转换后文件。转换工具不可用时，门控报告 NOT RUN。

### QoR 指标
- 规则检查已完成：必须为 true，中止运行没有可用 ERROR 数量
- 下游转换 RTL 时的前端检查：退出 0 且无解析错误
- ERROR count：进入下一阶段前必须为 0
- WARNING count：全部评审，waive 时提供理由
- 所有 RTL 文件均已检查，而不仅仅是 top-level

### 必须输出
- Lint report（按 file/rule）
- 未经验证声明：本阶段将规则 9 下每个 UNVERIFIED 发现追加到声明列表
- Waiver file
- Clean lint summary
- 前端检查：转换/解析命令及退出状态，或 NOT RUN 及原因

---

## Stage: cdc_rdc_analysis

### CDC 规则
1. 每个 CDC crossing 使用批准的 synchronizer primitive
2. Single-bit control：至少 2-FF synchronizer
3. Multi-bit data：async FIFO 或 handshake protocol
4. Pulse crossing：pulse stretcher + synchronizer
5. 未豁免 CDC violation 必须为 0
6. CDC 工具不可用时，阶段为 NOT RUN，不能为 PASS。通过推理分析的每个跨域都是 `UNVERIFIED` 的 `cdc`（或 `reset`）声明，在本阶段逐项追加到未经验证声明列表，注明所依赖同步器，供下游形式验证及功能验证逐项检查。

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
- 每个未通过工具运行闭环的跨域都产生未经验证声明（规则 6）
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
8. 使用下游实际使用的前端。PD 或综合读取 sv2v 输出时，对 sv2v 输出运行 synth_check，不能改用接受实际流程所拒绝结构的原生 SystemVerilog 前端（Surelog、slang 插件）。

9. 解析或 elaboration 错误不是 QoR 结果，应在 `rtl_coding` 修复源结构（`lint_check` 规则 15）。有自有 RTL 定义的黑盒/未定义模块属于缺失源列表条目（`design_input_check` 规则 8）；没有自有 RTL 则缺少库或宏视图，以 `input_setup` 升级处理。

### QoR 指标
- 前端解析与 hierarchy -check：无错误、无未定义模块
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
- [ ] 代码审查完成；未通过工具运行闭环的 CDC、复位、协议结论均记录为 UNVERIFIED
- [ ] File list 与 compile order 已记录
- [ ] 每个模块在每个工具源列表中（仿真、lint、综合、PD、形式验证），或附理由豁免
- [ ] 转换后 RTL 在各下游前端解析通过，或门控报告 NOT RUN
- [ ] 所有 high/moderate gating opportunity domain 已插入 ICG
- [ ] Always-on domain 已使用 `/* always-on: <reason> */` 注释
- [ ] High-opportunity domain 的 `clock_gating_coverage` ≥ `design_state.constraints.power.gating_coverage_pct_min`%（默认 60%），并写入 sign-off record

### 必须输出
- RTL file package（全部 .sv）
- File list（filelist.f）
- Compile order 文档
- Assertion library（.sva）
- RTL sign-off record
- 未经验证声明列表：代码审查、lint、CDC 的每个 UNVERIFIED 结论逐项写为 `{module, category, claim}`；category 为 cdc、reset、fsm、protocol、arithmetic、parameter 之一。每个使用无 default 的 unique case 的 FSM 都须有 fsm 条目，注明恢复断言。该列表交给验证与形式验证，遗漏的声明就不会有下游检查。空列表必须明确写为空，不能省略。rtl_coding、lint_check、cdc_rdc_analysis 作出结论时逐步建立，本阶段补全。每条终止路径均交接，包括未到本阶段或未签核的运行；未签核仍须交接全部已作出的声明。

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
在 `<MEM>/rtl-design/experiences.jsonl` 中写入或覆盖一条 JSON 记录。
这样即使流程中断或单独调用 stage，也能持久化结果。

`run_id` 使用 `rtl-design_<YYYYMMDD>_<HHMMSS>`，流程开始时只生成一次，后续 stage 复用。
最终 sign-off 完成前，`signoff_achieved` 必须保持 false。

### Run state

在启动任何工具之前，第一件事写入 `<MEM>/rtl-design/run_state.md`：

```markdown
run_id:      rtl-design_<YYYYMMDD>_<HHMMSS>
design_name: <design>
tool:        <primary tool>
start_time:  <ISO-8601>
last_stage:  null
```
仅阶段成功完成后，将 last_stage 更新为该阶段名。该文件让唤醒循环提示词和恢复会话无需依赖内存即可识别正确运行。文件及父目录不存在时创建。

### Optional: claude-mem index
本会话若提供 `mcp__plugin_ecc_memory__add_observations`，在写入 `experiences.jsonl` 后，将每项已应用修复作为 observation 写入实体 `chip-design-rtl-design-fixes`。工具不存在时静默跳过；JSONL 为权威记录。

### Optional: hdl-rtl-skill
本会话若提供 `hdl-rtl-skill` 的 Skill（`rtl-style-guide`、`rtl-golden-templates`、`rtl-anti-patterns`、`rtl-review-signoff`、`rtl-workflow`），将其与本 Skill 配合使用：在 `lint_check` 用 `rtl-lint` 脚本运行 slang（应用规则 6–8，按规则 11 映射严重级别）；在 `rtl_coding` 为 FIFO、同步器、仲裁器、FSM、ready/valid 流水级使用标准模板；审查时参考反模式目录。本文件规则是其风格指南遵循的项目标准，若时钟/复位命名、`_i`/`_o` 等存在差异，以本文件为准。工具不存在时静默跳过；上述所有规则仍独立有效。

## CDC/RDC Fail-Capable Check 补充规则

### Prove the crossing rules ran
1. 对 CDC/RDC 检查必须提供一个已知违规的 negative-control crossing，证明 checker 真的执行了 crossing rule。
2. **If the control is not flagged, the stage is NOT RUN**，不能因为 report 看起来 clean 就判 PASS。
3. 报告里必须写：**Negative control flagged (rule 7): must be true**。
4. 如果脚本 request a licence feature other than the product names the licence server lists，导致高级 checker 没启动，整个 CDC/RDC stage 只能是 NOT RUN。
5. **A module the tool black-boxed got zero rules**：first-party RTL 被 black-box 时，该模块没有被检查；必须列入未验证项。
6. 特别检查带 `string`-typed or `real` parameter 的模块，SpyGlass 等工具可能因为 front-end 限制而 black-box。
7. **Never edit the RTL to satisfy the lint tool**：如果问题来自工具解析/配置/输入集，应修 tool setup 或升级为 input_setup，不得为了让工具安静而修改正确 RTL。
