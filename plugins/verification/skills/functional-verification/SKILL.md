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

## Purpose（目的）

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

仅在**端口模式**进入：已有 testbench（cocotb 或 UVM）已经在一个 simulator 上稳定通过，现在要移植到新的 simulator（例如 Verilator-only regression 移到 VCS/Xcelium）。现有 testbench 及其检查属于输入，不在本阶段重新设计；原先能通过的 simulator 是 **reference simulator**，新的 simulator 必须与它对照。

### Domain Rules — cocotb invocation
1. cocotb 通过 `SIM` 选择 simulator：`verilator`、`icarus`、`vcs`、`xcelium`、`questa`。以已安装版本的 `cocotb-config --makefiles` 为准。参数通过 cocotb 标准变量传递：
   - `COMPILE_ARGS`：define、include dir、parameter override、timescale、访问权限
   - `EXTRA_ARGS`：compile/elaborate 额外参数
   - `SIM_ARGS`：runtime 参数，例如 `-licqueue`、coverage run flag
   - `PLUSARGS`：`+SEED=`、`+UVM_TESTNAME=`
   - `SIM_BUILD`：每个 simulator 独立 build 目录
   cocotb 2.x 将 `MODULE/TOPLEVEL` 改名为 `COCOTB_TEST_MODULES/COCOTB_TOPLEVEL`，不得假设版本。
2. 先用 `make -n SIM=<sim>` 读取 cocotb 自带 Makefile 已加参数，再添加自己的。**Never set `EXTRA_ARGS` on the `make` command line** for `SIM=xcelium`：命令行变量会覆盖 Makefile.xcelium 自己的 `EXTRA_ARGS +=`，可能丢掉 `-top`、`-xmlibdirpath`、`-licqueue`。应在共享 include 中转换到独立变量，或显式 `override undefine EXTRA_ARGS` 后再追加，并用 `make -n` 验证 cocotb 自带参数仍存在。

### Domain Rules — Translating Verilator-only idioms
3. 每个 reference flag 都必须翻译到新 simulator。关键映射如下：

| Verilator | VCS | Xcelium (`xrun`) |
|---|---|---|
| `-G<P>=<v>` | `-pvalue+<top>.<P>=<v>` | `-defparam <top>.<P>=<v>` |
| string parameter | `-pvalue+<top>.<P>=...`，注意 recipe shell 再转义 | 观测到 `BDDSTR` 对 string `-defparam` ignored；生成额外 top，以 hierarchical `defparam` 赋值 |
| `+define+X=1` / `-DX=1` | `+define+X=1` | `+define+X=1` / `-define X=1` |
| `-I<dir>` / `+incdir+<dir>` | `+incdir+<dir>` **并加** `-y <dir> +libext+.sv+.v` | 同样加 `-y <dir> +libext+.sv+.v` |
| `--timescale 1ns/1ps` | `-timescale=1ns/1ps` | `-timescale 1ns/1ps` |
| `--timescale-override` | `-override_timescale=1ns/1ps` | `-override_timescale 1ns/1ps` |
| VPI access | `-debug_access+all` / `+acc` | `-access +rwc` |
| `-Wno-*` / `-Wall` / `--lint-only` / trace/build/thread flags | drop | drop |
| `--x-assign` / `--x-initial` | drop，不能改变语义 | drop |
| coverage flags | 转成 `-cm ...` | 转成 `-coverage ...` |

   String parameter 必须在 smoke run 中读回实际值并与 reference 比较。任何 `PRM_ILLG`、`BDDSTR`、`parameter not found`、`ignored` 都是 translation FAIL。Verilator 的 `-I` 还能按文件名搜索 module，所以商业 simulator 侧需映射为 library search，更推荐直接补全 filelist。
4. **One shared make include, not per-target edits.** 全部转换放在一个共享文件（如 `sim_portability.mk`），每条规则都以 `SIM` guard；不能每 target 复制一份。
5. **Reference command line 保持 byte-identical。** 加 include 前后保存每个 target 的 `make -n SIM=<reference>`，逐文件 `cmp -s`。如果 port 主机没有 reference simulator，可把同名 stub 放在 PATH 前面，用 `make -n -i` 抓命令，并对 make 自身 `Makefile:NNN:` 行号做相同归一化。交付前仍需按 CI 真正执行的版本重跑 reference lint/regression。
6. 每个 simulator 独立 `SIM_BUILD`（如 `sim_build_vcs`、`sim_build_xcelium`）；reference 原目录保持不变。
7. Verilator-only lint/test 在商业 simulator 上标记 NOT RUN，逐项列名，从 pass floor 中扣除；**never count them as passed**。
8. Simulator 从 non-interactive shell 解析。用户 alias 不进入 make；例如 VCS 显式写 `-full64`，并记录 `command -v vcs`。

### Domain Rules — Triage
9. **LRM strictness：先分类再修改。** VCS/Xcelium 拒绝而 Verilator 接受的代码分：
   - **RTL defect**：违反 IEEE 1800，例如 use-before-declaration、multi-driver、`always_ff` target 又被别处写、implicit net。引用 LRM 条款并写 `fix_request`，禁止 testbench/define/`-nowarn` workaround。典型：LRM **9.2.2.4**、VCS `ICPD`。
   - **Testbench defect**：相同问题位于 TB/bind；修 TB，但 checking 不能变松。
   - **Tool dialect**：合法代码只是厂商选项/语法不同；在共享 include 中加入 vendor flag，并记录 message ID。
10. **Simulator semantics differences 必须 root-cause。** 跨 simulator 结果不同先 FAIL，记录 `sim_differences`。优先检查 X/初始化、scheduling race、随机 seed、4-state vs 2-state。Verilator 中未驱动/未写状态可能表现为 0，VCS/Xcelium 为 X；禁止用 `COCOTB_RESOLVE_X` 或 mask 把根因吞掉。
11. 已知无害的 VCS+cocotb GPI/VPI debug 行不能直接作为 FAIL。绝不能 grep simulation log 的 ERROR 判 verdict。

### Domain Rules — Pass/fail and scope
12. **Pass/fail 来自 `results.xml`，never from `make`'s exit code。** cocotb 1.9.2 在 VCS/Xcelium 上观测到 test fail 但 make exit 0。运行前删 stale results 或用 `--newer-than` stamp，随后用 `wrap-cocotb-results.sh`。missing/empty/unparsable/0 testcase 都 FAIL。
13. **Negative control before trusting any PASS.** 每个 simulator 先注入一个已知失败，确认 wrapper 正确报 FAIL，再移除；无法证明 pipeline 能报 FAIL，就不能信任 PASS。
14. **Staged scope.** 先 compile 全部 test module，再每模块至少一个 smoke、P0 优先；清零 unexplained difference 后才允许 full regression。
15. **Skips must match the reference.** 新 simulator 的 skipped testcase 名称集合必须与 reference 对齐；只比 count 不够，simulator-specific skip 必须有理由。
16. Smoke/full launch 前执行 `regression_signoff` 的 license/resource/disk gate。
17. 每 run 独立 results file 与 `SIM_BUILD`。使用 `COCOTB_RESULTS_FILE` 或支持时 `SIM_RESULTS_IN_BUILD`；不能隔离的部分串行，总 testcase 数与 reference 对账。
18. Hierarchy access 集中在一个 helper，处理 dotted path / flattened generate name / packed-struct slice fallback，不能每 test 自己 try/except。
19. 每次运行导出 **UTF-8** locale（如 `LANG=C.UTF-8`、`LC_ALL=C.UTF-8`），避免非 ASCII docstring 触发 `UnicodeEncodeError`。

### QoR Metrics to Evaluate
- `reference_cmdlines_identical=true`：每 target 前后 `cmp -s` exit 0
- `compile_errors_per_sim=0`
- `negative_control_detected=true` 每 simulator
- `smoke_pass_pct=100%`，或差异全部进入 `sim_differences`
- `testcase_count_delta=0`
- `skip_set_match=true`
- `unexplained_sim_differences=0`
- `lint_counted_as_compile=0`
- `param_override_warnings=0`
- `verilator_only_not_run` 逐项列名并从 pass floor 扣除，never count them as passed

### Common Issues & Fixes
| Issue | Fix |
|---|---|
| make exit 0 但 test fail | `wrap-cocotb-results.sh` 读取 `results.xml` |
| String parameter 回到默认值 | 修 make+shell quoting，并在 smoke 中读回 |
| VCS/Xcelium 找不到 signal handle | 按需要加入 `-debug_access+all` / `-access +rwc` |
| Verilator PASS、商业 simulator 出 X | 查 reset/read-before-reset，分类 RTL/TB defect |
| Xcelium 启动卡住 | `-licqueue` 等 seat；外层 `timeout` + `lmstat` |
| make 内找不到 `vcs` | alias 不存在；真实 binary + 显式 `-full64` |
| `*W,BDDSTR ... ignored` | string parameter 用 generated `defparam` top |
| `Warning-[PRM_ILLG]` | VCS `-pvalue+` string shell 转义错误 |
| Xcelium 丢 `-top/-licqueue` | 命令行覆盖了 `EXTRA_ARGS` |
| VCS/Xcelium module not found | Verilator `-I` 隐式找到了；修 filelist 或 `-y/+libext+` |
| VCS `ICPD` | `always_ff` target 又被 declaration initializer/`initial` 写 |
| testcase 少于 reference | results.xml 被 rollup/concurrent job 覆盖 |
| `UnicodeEncodeError` | 缺 UTF-8 locale |

### Output Required
- 共享 make include（`sim_portability.mk` 或等价文件）及 translation table
- `before/`、`after/` 的 `make -n` capture 与逐 target `cmp -s` 结果
- 每 simulator 的 negative-control、smoke、full-run `wrap-cocotb-results.sh` JSON
- Triage log：每条处理过的 compile message，含 RTL/TB/dialect 分类、evidence、owner
- `sim_differences`：每个跨 simulator 结果不同的 test 一条记录
- 每 simulator 相对 reference 的 skip-set comparison

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
