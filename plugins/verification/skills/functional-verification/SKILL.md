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

1. `memory/verification/knowledge.md` —— 已知失败模式、有效工具参数、PDK/工具特殊行为。每个阶段的决策都应吸收其中经验；若不存在则继续执行。
2. `memory/verification/run_state.md` —— 当前运行身份（`run_id`、`design_name`、`tool`、`last_stage`）。用于中断后的正确恢复；如果不存在，表示开始新运行，Orchestrator 会在第一阶段前创建。

无论本 Skill 是由用户直接加载，还是由 Orchestrator 在中途调用，都必须执行上述预读，以确保任何诊断前都已查询历史修复经验。

## 目的

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
- **Synopsys VCS**（`vcs`）—— 主流 SystemVerilog/UVM 仿真器
- **Cadence Xcelium**（`xrun`）—— 支持多语言及覆盖率引擎的仿真器
- **Siemens Questa**（`vsim` / `vlog` / `vcom`）—— 支持 UVM 的混合语言仿真器

---

## Stage: tb_architecture

### 领域规则
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

### 要评估的 QoR 指标
- DUT 所有接口都有对应 Agent
- Reference model 足以检查所有 DUT 输出
- TB 编译错误数：0

### 必须输出
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

### 领域规则——Driver
1. 按协议规范进行 cycle-accurate 信号驱动
2. 正确处理 back-pressure，并检查 ready/valid
3. Driver 中增加协议 assertion，尽早捕获非法 stimulus

### 领域规则——Scoreboard
1. DUT 输出到达前，由 reference model 预测 expected output
2. mismatch 报告必须包含完整上下文（stimulus、expected、actual）
3. 跟踪 total checks、pass、fail、untriggered

### 领域规则——SVA Assertion
1. 协议 assertion：放在 interface bind 中，不修改 DUT
2. 功能 assertion：放在 checker 或 bind module 中
3. 所有 assertion 都应有清晰名称和明确的失败消息

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
6. 出现任何 scoreboard mismatch 时，继续之前必须先判断是 DUT bug 还是 testbench bug
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
- 不允许 vacuous proof
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
在 `memory/verification/experiences.jsonl` 中写入或覆盖一条 JSON 记录。
这样即使流程被中断或只单独调用某阶段，信息也能持久化。

`run_id` 使用 `verification_<YYYYMMDD>_<HHMMSS>`，在流程开始时只生成一次，后续阶段复用。
最终 sign-off 阶段完成前，`signoff_achieved` 必须保持为 `false`。

### Run state（第一阶段前写入，每阶段后更新）

在启动任何工具之前，第一件事就是写入 `memory/verification/run_state.md`：

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
