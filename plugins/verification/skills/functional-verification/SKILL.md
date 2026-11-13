---
name: functional-verification
description: >
  基于 UVM 的功能验证——包括 testbench 架构、测试规划、定向与约束随机激励、
  功能/代码覆盖率收敛、形式验证辅助以及 regression sign-off。适用于构建 UVM
  testbench、编写测试、分析覆盖率或管理验证回归。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill：功能验证（UVM）

## 调用方式

当本 Skill 被加载且用户给出验证任务时，**不要直接执行各阶段**。应立即启动
`digital-chip-design-agents:verification-orchestrator` Agent，并将用户的完整请求及所有可用上下文传递给它。
Orchestrator 负责强制执行下文定义的阶段顺序、loop-back 规则和 sign-off 判据。

只有在 Orchestrator 执行过程中为某个具体阶段读取本 Skill，或者用户只是询问某个针对性的参考问题、而不是要求执行完整流程时，才直接使用本文件中的领域规则。

## 运行前上下文

在执行或建议**任何**阶段之前，如果以下文件存在，应先读取：

1. `<MEM>/verification/knowledge.md` —— 已知失败模式、有效工具参数、PDK/工具特殊行为。每个阶段的决策都应吸收其中经验；若不存在则继续执行。
2. `<MEM>/verification/run_state.md` —— 当前运行身份（`run_id`、`design_name`、`tool`、`last_stage`）。用于中断后的正确恢复；如果不存在，表示开始新运行，Orchestrator 会在第一阶段前创建。

无论本 Skill 是由用户直接加载，还是由 Orchestrator 在中途调用，都必须执行上述预读，以确保任何诊断前都已查询历史修复经验。

## Purpose
Also guides **port mode**（现有 testbench 的跨 simulator 移植）以及 coverage report-only review。（目的）

指导完整的 UVM 功能验证流程，从 testbench 架构一直到覆盖率收敛后的 regression sign-off。
最终产出带有覆盖率记录、且回归干净的已验证 RTL 包。

---

## 支持的 EDA 工具

### 开源工具
- **Verilator**（`verilator`）—— 高速周期精确仿真器；可通过 verilator+UVM 使用 UVM
- **Icarus Verilog**（`iverilog`）—— 事件驱动仿真器，适合快速 testbench 检查
- **cocotb** —— Python 协同仿真框架（`pip install cocotb`）
- **PyUVM** —— 面向 cocotb 环境的 Python UVM 实现
- **UVVM** —— VHDL 验证方法学库

### 商业工具
- **Synopsys VCS** (`vcs`，命令方言 `synopsys`） — industry-standard SV/UVM simulator
- **Cadence Xcelium** (`xrun`，命令方言 `cadence`） — multi-language simulator with coverage engine
- **Siemens Questa** (`vsim` / `vlog` / `vcom`，命令方言 `siemens`） — mixed-language simulation with UVM support

---

## Stage: simulator_portability

仅在 **port mode** 进入：已有 testbench 在 reference simulator 上通过，现在要移植到 VCS、Xcelium、Questa 等新 simulator。此阶段不重新设计 testbench，而是证明同一 testbench、同一检查语义在不同 simulator 上可复现。

### Domain Rules — cocotb invocation
1. cocotb 通过 `SIM=verilator|icarus|vcs|xcelium|questa` 选择 simulator。参数通过 `COMPILE_ARGS`、`EXTRA_ARGS`、`SIM_ARGS`、`PLUSARGS`、`SIM_BUILD` 传递，不直接修改 cocotb 自带 makefile。
2. **Never set `EXTRA_ARGS` on the `make` command line**：这会覆盖 cocotb simulator makefile 自己追加的 `-top`、`-xmlibdirpath`、`-licqueue` 等参数。需要扩展时放到独立变量或共享 include。
3. 参考 simulator 的 `make -n` 在修改前后保存到 before/after 文件，使用 `cmp -s` 证明 byte-identical；reference command line 改变即 FAIL。
4. Verilator 参数翻译：
   - `-G<P>=<v>` → VCS `-pvalue+<top>.<P>=<v>`
   - `-G<P>=<v>` → Xcelium `-defparam <top>.<P>=<v>`
   - Verilator 的 `-I <dir>` 既可作为 include search，也可能让 module-by-name 被找到；VCS/Xcelium 还需要 `-y <dir> +libext+.sv+.v` 或修正 filelist。
   - `--timescale`、define、incdir、VPI access 必须翻译为目标 simulator 方言；`-Wno-*`、`--trace`、`--x-assign`、`--x-initial` 不直接照搬。
5. String parameter 必须特别验证：Xcelium 对 `*W,BDDSTR ... ignored` 一类 warning 视为 FAIL；必要时生成带 hierarchical defparam 的 top。VCS 的 `-pvalue+` 字符串要正确 shell escaping。
6. **LRM strictness**：参考 simulator 接受而 VCS/Xcelium 拒绝的代码，先按 LRM 分类。典型 `always_ff` 多驱动/初始化冲突参考 IEEE 1800-2023 **9.2.2.4**。如果是 RTL defect，创建 `fix_request`；不能通过放宽 testbench 或加 suppress flag 掩盖。
7. Verilator-only 的 lint/elaboration guard、`*_neg` 等目标在目标商业 simulator 上属于 NOT RUN，必须按名称列出并从 pass floor 中扣除，**never count them as passed**。
8. 可用 `make -n -i` 配合 stub binary 比对 command parity；即使 reference simulator 本机不存在，也能验证 make translation。
9. 每次运行使用独立 `COCOTB_RESULTS_FILE`（或安装版本支持时的 `SIM_RESULTS_IN_BUILD`）以及独立 `SIM_BUILD`，防止并发覆盖 `results.xml`、`ucli.key`、`xrun.log`。
10. 所有 cocotb run 环境必须是 **UTF-8**（例如 `LANG=C.UTF-8`、`LC_ALL=C.UTF-8`）。
11. Pass/fail 从 `results.xml` 读取，**never from `make`'s exit code**。使用 `wrap-cocotb-results.sh`；missing/empty/unparseable `results.xml` 都是 FAIL。
12. **Negative control before trusting any PASS.** 每个 simulator 都注入一个已知失败检查，确认 wrapper 能报告 FAIL，再删除 control 并恢复正常计数。
13. **Skips must match the reference.** 比较 testcase 名称集合而非只比较数量；目标 simulator 独有 skip 必须说明 simulator-specific 原因。
14. 先 compile 全部 test module，再运行 smoke subset，消除所有未解释差异后才允许 full regression。
15. 4-state vs 2-state、X-propagation、scheduler race、random seed、VPI hierarchy 差异必须 root-cause；不得用 X mask/resolve 让测试“变绿”。

### QoR Metrics to Evaluate
- `reference_cmdlines_identical=true`
- 每个 simulator `compile_errors_per_sim=0`
- `negative_control_detected=true`
- smoke pass 100%，或所有差异均已分类
- testcase name/count 与 reference 一致
- skip set match
- unexplained simulator difference = 0
- parameter override warning = 0

### Common Issues & Fixes
| Issue | Fix |
|---|---|
| make exit 0 但 testcase fail | 从 `results.xml` 读取并使用 `wrap-cocotb-results.sh` |
| `*W,BDDSTR ... ignored` | 使用 generated defparam top，不能假设 `-defparam` 字符串可靠 |
| VCS `Warning-[PRM_ILLG]` | 修正 `-pvalue+` 的字符串 quoting |
| Xcelium 丢 `-top/-licqueue` | 不要在 make command line 覆盖 `EXTRA_ARGS` |
| Verilator 能找到 module、VCS/Xcelium 找不到 | 修 filelist，或增加 `-y <dir> +libext+.sv+.v` |
| VCS `ICPD` | 依据 9.2.2.4 判断 RTL 多驱动/初始化 defect |
| testcase 少于 reference | 检查 `results.xml` 被 rollup/concurrent job 覆盖 |
| cocotb `UnicodeEncodeError` | 设置 UTF-8 locale |

### Output Required
- 共享 simulator translation include（如 `sim_portability.mk`）
- reference before/after `make -n` 与 `cmp -s` 结果
- 每个 simulator 的 negative-control/smoke/full-run wrapper JSON
- compile-message triage log（RTL/TB/dialect）
- `sim_differences`
- skip-set comparison

---
## Stage: tb_architecture

## Domain Rules（领域规则）
1. 遵循 UVM 1.2 / IEEE 1800.2
2. DUT 每个接口对应一个 UVM agent（driver、monitor、sequencer）
3. Active agent：负责驱动激励；Passive agent：只负责监视
4. Scoreboard：将 DUT 输出与 reference model 输出比较
5. Reference model：DUT 的功能模型，可使用 SystemVerilog 或通过 DPI 调用 C++
6. Coverage collector：必须与 scoreboard 分离
7. Virtual sequencer：用于协调多 Agent 场景
8. 所有 TB 参数通过 `uvm_config_db` 配置，组件内部不得硬编码

### UVM 层次模板
```
uvm_test
  └─ uvm_env
       ├─ agent_A (active)   driver + monitor + sequencer
       ├─ agent_B (passive)  monitor only
       ├─ scoreboard
       ├─ coverage_collector
       └─ virtual_sequencer
```

## QoR Metrics（QoR 指标）
- DUT 所有接口都有对应 Agent
- Reference model 足以检查所有 DUT 输出
- TB 编译错误数：0

## Output Required（必须输出）
- TB 架构图
- UVM 组件列表与层次结构
- Interface-to-agent 映射表

---

## Stage: test_planning

### 领域规则
1. 每项功能需求 → 至少一个 directed test
2. 每个接口 → 至少一个协议一致性测试
3. Error/exception 场景必须有明确 directed test，不能完全依赖随机
4. Corner case：边界值、最大/最小值、overflow、underflow
5. 并发：使用多线程激励进行 pipeline stress
6. Back-pressure：必须测试 flow-control 条件
7. Reset：包括运行中的 reset、active transaction 期间的 reset
8. 在编写测试前先定义 covergroup
9. 为定向测试难以覆盖的边界情况逐一建立 V-plan 条目：
   - 同时事件：load 与 increment、空时读写、flush 与 enable、设置与清除
   - 退出复位后的首周期
   - 持续背压（`ready` 多周期为低）与无间隙最大速率输入
   - 每个计数器在最大值附近的边界、回绕与饱和
   - 多时钟模块两端极限时钟比

10. 测试边界参数值，而非仅默认配置：`WIDTH=1`、`DEPTH=1` 和 `2`、`N=1` 及非 2 次幂值。对于 RTL 应拒绝的值，测试其确实拒绝 elaboration。

11. 使用 RTL 交接输入：`design_state.rtl.unverified[]` 每项（RTL 未运行工具便作出的声明）对应测试，或标为分配给形式验证。`cdc`、`reset` 无法由功能仿真闭环，应记录为需要 CDC/RDC 工具运行，不能记为已覆盖。

### V-Plan 条目模板（每项功能）
```
feature_id:   F001
description:  AXI write burst handling
tests:        [direct_single_write, burst_len_256, narrow_transfer]
assertions:   [axi_valid_stable, axi_handshake_check]
covergroups:  [burst_len_cg, burst_type_cg]
priority:     P0
```

### 要评估的 QoR 指标
- Requirement coverage：100% spec feature 都已建立映射
- P0 测试：进入随机测试前必须全部通过
- 预计测试数量：相对于项目周期合理

### 必须输出
- V-plan 文档
- Covergroup 定义
- Assertion 列表及预期行为

---

## Stage: uvm_tb_build

### 领域规则——Sequence
1. Base sequence：生成最小合法 transaction
2. Extended sequence：覆盖 V-plan 中的具体场景
3. Sequence library：注册全部 sequence，用于随机选择
4. 不得硬编码数值，应使用随机字段与 constraint

### Domain Rules — Testbench Coding
测试平台不受 RTL 综合规则约束，initial、#delay、阻塞赋值在此均正确；但仍须在每个仿真器中以相同方式完成 SystemVerilog elaboration。
1. 每个测试平台、interface、bind 文件顶部写 `` `default_nettype none ``，末尾恢复 `` `default_nettype wire ``，避免影响后续编译库代码。DUT 连接拼写错误必须报错，不能形成隐式一位网络。

2. DUT 实例使用命名端口连接与命名参数覆盖（`#(.WIDTH(8))`），禁止位置连接，避免端口列表改变时静默误接。

3. 每个参数和常量显式定型（`int unsigned`、`logic [W-1:0]`）。无类型参数及对裸字面量的尺寸转换（`WIDTH'(1)`）是有符号的，在 scoreboard 比较最高位为 1 的值时会导致假通过或假不匹配。

4. 期望值与实际值使用相同位宽、相同符号性，以 `!==` 比较，使 DUT 输出 X/Z 形成不匹配，不能静默通过。

5. 注释说明原因：对 DUT 的每项假设、每项豁免、每个有意非法的激励都要说明理由。

### 领域规则——Driver
1. 按协议规范进行 cycle-accurate 信号驱动
2. 按 ready/valid 合约处理背压。源端无需等待 `ready` 就应拉高 `valid`，随后保持 `valid` 与载荷稳定，直到该拍被接受。接收端 `ready` 可以依赖 `valid`。先等待 ready 才拉高 valid 的驱动器会与等待 valid 的 DUT 死锁，并掩盖仅在背压下暴露的 DUT 缺陷。

3. Driver 中增加协议 assertion，尽早捕获非法 stimulus

### 领域规则——Scoreboard
1. DUT 输出到达前，由 reference model 预测 expected output
2. mismatch 报告必须包含完整上下文（stimulus、expected、actual）
3. 跟踪 total checks、pass、fail、untriggered

### 领域规则——SVA Assertion
1. 协议 assertion：放在 interface bind 中，不修改 DUT
2. 功能 assertion：放在 checker 或 bind module 中
3. 所有 assertion 都应有清晰名称和明确的失败消息
4. 每个 ready/valid 接口都以断言表达合约：仅 `valid && ready` 时传输；接受前不得撤回 `valid`；`valid && !ready` 时载荷稳定；复位时 `valid`、`ready` 无效且不能为 X。

### 要评估的 QoR 指标
- TB compile：0 error、0 warning
- Sanity test：在 known-good RTL 上通过
- 仿真日志中所有组件均正常激活

### 必须输出
- UVM component 源文件
- SVA assertion 文件（基于 bind）
- 编译脚本

---

## Stage: directed_tests

### 领域规则
1. V-plan 每个条目至少实现一个 directed test；测试必须可复现
2. 每个测试只验证其目标功能要求，不写“大而全”测试
3. Error/exception 路径必须有显式 stimulus 触发
4. Corner case：边界值、最大/最小、overflow、underflow 应分别测试
5. 每个接口至少包含一次 active transaction 期间 reset 的测试
6. 所有 P0 测试通过后，才能进入 constrained-random 阶段
7. 如果 directed test 发现 DUT bug：按 verification-orchestrator 的 Design State schema 向 `design_state.fix_requests[]` 写入 `fix_request`，并以 `decision=escalate` 结束当前运行。RTL 的重新调用由 pipeline-orchestrator（`chip-design-meta`）负责，本域不得自行循环修 RTL，也不要等待用户确认后再处理。
8. 提交前分类为 DUT 缺陷或测试平台缺陷，并指出机制而非只报位置；现象不一定是缺陷本身。仅在波形中将不匹配追踪到该信号时设置 `suspected_rtl.basis=traced`，否则为 `hypothesis`。从现象开始：
   | 现象 | 优先检查的机制 |
   |---|---|
   | 间歇出现，发生率随时钟比变化 | 跨时钟域 |
   | 启动时失败，稳定运行后正常 | 复位释放与复位值 |
   | 一直挂起直到复位 | 无出口的 FSM 状态、协议等待环 |
   | 仅大值错误 | 位宽截断、算术溢出 |
   | 仅负值错误 | 有符号/无符号混用 |
   | 仅持续负载下失败 | 仲裁公平性、撤回 valid、载荷不稳定 |
   | RTL 仿真通过、门级仿真失败 | 时钟块阻塞赋值、不完整敏感列表、X 乐观传播 |
   | 长时间运行逐渐退化 | credit 或 token 泄漏 |

9. 不能弱化检查使失败测试通过：不得放宽 scoreboard 比较、禁用/豁免断言，或约束激励绕开失败情况，除非激励按规格确属非法。修改测试平台后，其他所有测试的检查都必须至少与原先一样严格。

### 要评估的 QoR 指标
- 所有 V-plan feature 至少被一个 directed test 覆盖
- P0 directed tests：100% 通过
- 本阶段 UVM FATAL / ERROR：0

### 必须输出
- Directed test 源文件（每项 feature 一个 UVM sequence）
- Directed test pass/fail 报告
- Bug report（如果发现 DUT bug）

---

## Stage: constrained_random

### 领域规则
1. Constraint block 应在协议合法范围内随机化所有 stimulus 字段
2. 根据前次运行发现的 uncovered bin，对约束进行加权偏置
3. 评估覆盖率前至少使用 10 个不同 seed
4. 全程启用 scoreboard，每个 transaction 都与 reference model 对比
5. 出现任何 UVM FATAL 时立即停止，不跨 seed 累积错误
6. 任何 scoreboard 不匹配，都必须按 `directed_tests` 规则 8 的现象表分类为 DUT 或测试平台缺陷后才能继续。

7. 持续运行直到覆盖率目标达到，或 seed budget 耗尽

### 要评估的 QoR 指标
- Functional coverage 随 seed 持续向 100% 收敛
- 不允许存在持续未解决的 scoreboard mismatch
- Regression pass rate：100%

### 必须输出
- 当前全部 seed 合并后的 coverage report
- Uncovered bin 列表及针对性关闭计划
- Seed log（seed、pass/fail、coverage）

---

## Stage: coverage_analysis

### 覆盖率目标

| 类型 | 目标 | 优先级 |
|------|------|----------|
| Functional (V-plan) | `design_state.constraints.coverage.functional_pct`%（默认 100%） | P0 |
| Code Line | ≥ `design_state.constraints.coverage.line_pct`%（默认 95%） | P1 |
| Code Branch | ≥ `design_state.constraints.coverage.branch_pct`%（默认 90%） | P1 |
| Code Toggle | ≥ `design_state.constraints.coverage.toggle_pct`%（默认 85%） | P2 |
| FSM State | `design_state.constraints.coverage.fsm_state_pct`%（默认 100%） | P0 |
| FSM Transition | ≥ `design_state.constraints.coverage.fsm_transition_pct`%（默认 95%） | P0 |
| Assertion triggered | `design_state.constraints.coverage.assertion_pct`%（默认 100%） | P1 |

### 收敛策略
1. N 个 random seed 后识别 uncovered bin
2. 为难以命中的 bin 编写针对性 directed test
3. 调整 constraint，提高对 uncovered area 的命中概率
4. 对无法到达的 bin（例如 dead code）提供理由并申请 waiver

### 要评估的 QoR 指标
- Functional coverage：100%，不得存在未豁免缺口
- Code coverage：满足上表目标
- Waiver file：所有条目均经 verification lead 批准

### 必须输出
- 合并 coverage report
- Uncovered bin 列表及 closure plan
- Waiver file

---

### Report-only mode
当用户只要求 review/audit/list coverage hole 时，设置 `coverage_mode: report_only`。此模式不自动写 test/constraint/waiver，**the two `coverage_analysis` loop-backs** 不触发；coverage 低于 target 只记 WARN(`coverage_gap`)，不得 sign-off。

## Stage: formal_assist

### Formal 使用场景
1. 协议一致性：证明 handshake 永不违反
2. Deadlock freedom：证明不存在 valid=1 而 ready 永不出现的状态
3. Liveness：每个 request 最终都能得到 response
4. One-hot FSM：证明 state encoding 不会出现 0 bit 或多 bit 同时有效
5. Coverage closure：触达仿真难以命中的 bin

### 领域规则
1. Property 使用 concurrent SVA
2. 按 feature 分组到独立 .sva 文件
3. 使用 assumption 约束环境，且 assumption 必须符合合法 stimulus
4. 执行 vacuity check：禁用 assumption 后 property 不应仍成立
5. Liveness property 必须使用有界形式（`##[1:BOUND]`）

### 要评估的 QoR 指标
- 所有 property 为 PROVEN 或明确 UNREACHABLE
- 不允许 空洞证明（vacuous proof）
- 相比仿真 baseline，应关闭额外 coverage bin

### 必须输出
- SVA property 文件
- Formal run report（逐 property：proven/failed/vacuous）
- 失败时的 CEX waveform 描述

---

## Stage: regression_signoff

### Regression 分层

| 层级 | 触发 | 时长 | 内容 |
|------|------|------|------|
| Smoke | 每次 RTL commit | < 30 min | P0 directed tests |
| Nightly | 每晚 | < 8 hr | 全部 directed + 100 random seeds |
| Weekly | 每周 gate | < 48 hr | 全套测试 + 1000 seeds |
| Sign-off | Tape-out gate | 不限 | 全套测试 + 10,000 seeds |

### 通过标准
- 仿真失败数为 0（已批准 waiver 的已知 bug 除外）
- UVM FATAL / UVM ERROR 数为 0
- 满足全部覆盖率目标（见 `coverage_analysis`，由 `design_state.constraints.coverage.*` 控制）
- Formal：全部 P0 property proven
- 所有 P0/P1 bug 已关闭

### 必须输出
- Regression pass/fail report
- 最终合并 coverage report
- Open bug list
- Sign-off checklist

---

## Constraint Validation

权威 schema 和阶段入口校验规则见
`plugins/meta/skills/pipeline-orchestration/SKILL.md` 的 Constraints Schema。

**功能验证没有必填约束键**——本域所有约束均有 schema 默认值。

**可选约束（缺失时使用默认值）：**
- `constraints.coverage.functional_pct`（默认 100）——功能/V-plan 覆盖率目标
- `constraints.coverage.line_pct`（默认 95）——代码行覆盖率目标
- `constraints.coverage.branch_pct`（默认 90）——分支覆盖率目标
- `constraints.coverage.toggle_pct`（默认 85）——翻转覆盖率目标
- `constraints.coverage.fsm_state_pct`（默认 100）——FSM state 覆盖率目标
- `constraints.coverage.fsm_transition_pct`（默认 95）——FSM transition 覆盖率目标
- `constraints.coverage.assertion_pct`（默认 100）——assertion 触发覆盖率目标

根据这些数值评估 QoR 时，应在 history 条目中设置 `constraint_ref`，例如 `"coverage.functional_pct"`。

---

## Memory

### 每阶段完成后写入

每个阶段完成后，无论当前是否处于完整 Orchestrator 会话，都应以 `run_id` 为键，
在 `<MEM>/verification/experiences.jsonl` 中写入或覆盖一条 JSON 记录。
这样即使流程被中断或只单独调用某阶段，信息也能持久化。

`run_id` 使用 `verification_<YYYYMMDD>_<HHMMSS>`，在流程开始时只生成一次，后续阶段复用。
最终 sign-off 阶段完成前，`signoff_achieved` 必须保持为 `false`。

### Run state（第一阶段前写入，每阶段后更新）

在启动任何工具之前，第一件事就是写入 `<MEM>/verification/run_state.md`：

```markdown
run_id:      verification_<YYYYMMDD>_<HHMMSS>
design_name: <design>
tool:        <primary tool>
start_time:  <ISO-8601>
last_stage:  <first stage name>
```

每个阶段完成后更新 `last_stage`。该文件用于 wakeup-loop 和恢复会话，不依赖模型内存。
如果文件或父目录不存在，应创建。

### 可选：claude-mem index

如果当前会话存在 `mcp__plugin_ecc_memory__add_observations`，在写入
`experiences.jsonl` 后，将每项已应用 fix 作为 observation 写入
`chip-design-verification-fixes`。如果工具不存在则静默跳过；JSONL 才是权威记录。
