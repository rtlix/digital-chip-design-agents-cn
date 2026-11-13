# 功能验证流程 — 完整架构设计
## Orchestrator + Stage Agents + Skills（UVM）

> **目的**：基于 UVM 的 AI 驱动功能验证流程。覆盖 testbench architecture、test planning、stimulus generation、coverage closure、assertion-based verification 和 regression sign-off；在 port mode 下，还支持把已有 testbench 移植到 VCS/Xcelium/Questa，并以 report-only 模式审查 coverage hole 而不自动做 closure。

---

## 1. 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│             VERIFICATION ORCHESTRATOR                        │
│  输入：RTL、Microarch doc、verification plan                  │
│  输出：Coverage closed、regression passing 的 RTL sign-off     │
└────────────────────────┬─────────────────────────────────────┘
                         │
     ┌───────────────────┼───────────────────────┐
     ▼                   ▼                       ▼
  TB Architecture    Test Planning           Regression
  Agent              Agent                   Agent
     │                   │                       │
  SKILL              SKILL                   SKILL
```

---

## 2. 共享状态对象

```json
{
  "run_id": "verif_001",
  "design_name": "my_block",
  "mode": "full | port | report_only_coverage",
  "inputs": {
    "rtl_filelist":    "path/to/filelist.f",
    "dut_spec":        "path/to/spec.md",
    "microarch_doc":   "path/to/microarch.md",
    "interface_list":  ["AXI4", "APB", "custom_if"]
  },
  "stages": {
    "simulator_portability": { "status": "pending", "output": {} },
    "tb_architecture":     { "status": "pending", "output": {} },
    "test_planning":       { "status": "pending", "output": {} },
    "uvm_tb_build":        { "status": "pending", "output": {} },
    "directed_tests":      { "status": "pending", "output": {} },
    "constrained_random":  { "status": "pending", "output": {} },
    "coverage_analysis":   { "status": "pending", "output": {} },
    "formal_assist":       { "status": "pending", "output": {} },
    "regression_signoff":  { "status": "pending", "output": {} }
  },
  "coverage": {
    "functional":  0.0,
    "code_line":   0.0,
    "code_branch": 0.0,
    "code_toggle": 0.0,
    "assertion":   0.0
  },
  "bugs_found": [],
  "flow_status": "not_started"
}
```

---

## 3. Stage Sequence

```text
tb_architecture → test_planning → uvm_tb_build → directed_tests → constrained_random → coverage_analysis → formal_assist → regression_signoff
```

Port mode — 已经在 reference simulator 上通过的 testbench 移植到新 simulator 时，跳过重新设计/编写 testbench 的阶段：

```text
simulator_portability → coverage_analysis → regression_signoff
```

`simulator_portability` 把 reference simulator 的 flag 翻译进一个 `SIM`-gated make include，并用 `make -n` + `cmp -s` 证明 reference command line byte-identical；每个 simulator 使用独立 `SIM_BUILD`；每个新 compile error 都分类为 RTL defect、testbench defect 或 tool dialect；每个 simulator 先跑 negative control；最终 verdict 只来自 `results.xml` 和 `wrap-cocotb-results.sh`，**never from `make`'s exit code**。`coverage_analysis` 可运行 report-only mode，只生成排序后的 coverage-hole list，不自动写新 test。长 regression 后台分 shard，并把状态写入 `run_state.md`，恢复 session 时继续未完成 shard。
回退规则（目标阶段、迭代上限以及需要升级处理而非继续循环的失败）见 [`verification-orchestrator.md`](../plugins/verification/agents/verification-orchestrator.md) 的 `## Loop-Back Rules`。以该文件为准，本文不重复这些规则。

---

## 4. Skill 文件说明

下面保留最初设计草图；当前权威规则（包括 `simulator_portability`、VCS `-cm/urg`、Xcelium `-coverage/imc`、Verilator `--coverage-*/verilator_coverage` 以及 regression license/resource 规则）以 [functional-verification/SKILL.md](../plugins/verification/skills/functional-verification/SKILL.md) 为准。

### 4.1 `sv-verif-tb-arch/SKILL.md`

```markdown
# Skill: Verification — UVM Testbench Architecture

## Purpose
在写代码前先设计完整 UVM testbench structure。

## Domain Rules
1. 遵循 UVM 1.2 / IEEE 1800.2
2. 每个 DUT interface 一个 UVM agent
3. Active agent 包含 driver/monitor/sequencer；passive 只 monitor
4. Scoreboard 对比 DUT output 与 reference model
5. Reference model 在 SV/C++ 中实现功能预测
6. Coverage collector 与 scoreboard 分离
7. Virtual sequencer 协调多 agent scenario
8. 所有 TB parameter 通过 uvm_config_db 配置

## UVM TB Hierarchy Template
```
uvm_test
  └─ uvm_env
       ├─ agent_A (active)
       │    ├─ driver_A
       │    ├─ monitor_A
       │    └─ sequencer_A
       ├─ agent_B (passive)
       │    └─ monitor_B
       ├─ scoreboard
       ├─ coverage_collector
       └─ virtual_sequencer
```

## QoR Metrics
- 所有 DUT interface 都有 agent
- Reference model 足以检查全部 output
- TB compile error = 0

## Output Required
- TB architecture diagram
- UVM component list/hierarchy
- Interface→agent mapping table
```

---

### 4.2 `sv-verif-test-plan/SKILL.md`

```markdown
# Skill: Verification — Test Planning

## Purpose
生成完整 V-plan，把每条 spec requirement 映射到 test 或 property。

## Domain Rules
1. 每条 functional requirement 至少一个 test
2. 每个 interface 有 protocol compliance test
3. Error/exception 用 explicit test，不只依赖 random
4. Corner case：boundary/max/min/overflow/underflow
5. Concurrency：多线程 stimulus 压测 pipeline
6. Back-pressure：验证 flow-control 场景
7. Reset：operation 中 reset、transaction 中 reset
8. Coverage model 在写 test 前定义 covergroup

## V-Plan Template
```json
{
  "feature_id": "F001",
  "feature_desc": "AXI write burst handling",
  "tests": ["direct_single_write", "burst_len_256", "narrow_transfer"],
  "assertions": ["axi_valid_stable", "axi_handshake"],
  "covergroups": ["burst_len_cg", "burst_type_cg"],
  "priority": "P0"
}
```

## QoR Metrics
- 100% spec feature 被映射
- P0 test 在 random 前必须通过
- Test count 与 schedule 匹配

## Output Required
- V-plan
- Covergroup definition
- Assertion list
```

---

### 4.3 `sv-verif-uvm-build/SKILL.md`

```markdown
# Skill: Verification — UVM Testbench Implementation

## Purpose
按 UVM methodology 实现完整 testbench。

## Domain Rules — Sequences
1. Base sequence 产生最小合法 transaction
2. Extended sequence 对应 V-plan scenario
3. 所有 sequence 注册到 library
4. 不硬编码 stimulus value，使用 random field + constraint

## Domain Rules — Drivers
1. 严格按 protocol cycle 驱动
2. 正确处理 ready/valid back-pressure
3. Driver 内可放 protocol assertion，尽早捕获非法 stimulus

## Domain Rules — Monitors
1. Passive，绝不驱动 signal
2. 捕获完整 transaction，不是单 signal
3. 通过 analysis port 送 scoreboard/coverage

## Domain Rules — Scoreboard
1. DUT output 到达前生成 expected result
2. Mismatch 报告 stimulus/expected/actual 全上下文
3. 统计 total/pass/fail/untriggered

## Domain Rules — Assertions
1. Protocol assertion 放 interface
2. Functional assertion 放 checker/bind module
3. Assertion 命名清晰并带 failure message

## QoR Metrics
- TB compile：0 error、0 warning
- Basic sanity test 在 known-good RTL 上 PASS
- 所有 component 在 simulation log 中连接并 active

## Output Required
- UVM source
- Bind-based SVA
- Compile script
```

---

### 4.4 `sv-verif-coverage/SKILL.md`

```markdown
# Skill: Verification — Coverage Analysis and Closure

## Purpose
分析 coverage 并高效驱动 closure。

## Coverage Types and Targets
| 类型 | Target | Priority |
|---|---:|---|
| Functional (V-plan) | 100% | P0 |
| Code Line | ≥95% | P1 |
| Code Branch | ≥90% | P1 |
| Code Toggle | ≥85% | P2 |
| FSM State | 100% | P0 |
| FSM Transition | ≥95% | P0 |
| Assertion | 100% triggered | P1 |

## Coverage Closure Strategy
1. 多 seed 后找 uncovered bin
2. 对 hard-to-hit bin 写 targeted directed test
3. 调 constraint bias 到 uncovered area
4. 使用 coverage-driven test selection
5. Unreachable bin 必须有 dead-code/static-analysis evidence 才能 waive

## QoR Metrics
- Functional coverage 100%，无未批准 miss
- Code coverage 达到 target
- 跟踪 regression 的 closure rate

## Output Required
- Merged coverage report
- Uncovered bin + closure plan
- Waiver file
```

---

### 4.5 `sv-verif-formal/SKILL.md`

```markdown
# Skill: Verification — Formal Verification Assist

## Purpose
用 formal property verification 关闭 simulation 难以触达的 coverage gap，并证明 bug 不存在。

## Use Cases for Formal
1. Protocol compliance
2. Deadlock freedom
3. Liveness
4. One-hot FSM
5. Coverage closure
6. Reset verification

## Domain Rules
1. Property 使用 SVA concurrent assertion
2. 按 feature 分文件组织
3. 用 assumption 建模合法环境
4. 防止 over-constraining，必须做 vacuity check
5. Deep pipeline 的 BMC bound 至少为 pipeline depth + margin

## QoR Metrics
- Property 全部 PROVEN 或合理 UNREACHABLE
- 无 空洞证明（vacuous proof）
- Formal 相对 simulation baseline 关闭了额外 coverage

## Output Required
- SVA property file
- Formal report
- CEX waveform description
```

---

### 4.6 `sv-verif-regression/SKILL.md`

```markdown
# Skill: Verification — Regression Sign-off

## Purpose
定义并管理 RTL sign-off 前的 regression suite。

## Regression Tiers
| Tier | Trigger | Duration | 内容 |
|---|---|---:|---|
| Smoke | 每次 RTL commit | <30min | P0 directed test |
| Nightly | 每晚 | <8h | 全 directed + 100 random seeds |
| Weekly | 每周 | <48h | Full suite + 1000 random seeds |
| Signoff | Tape-out gate | Unlimited | Full suite + 10000 seeds |

## Pass Criteria
- Simulation failure = 0
- UVM FATAL / ERROR = 0
- Coverage target 全满足
- Formal property 全 proven
- P0/P1 bug 全关闭；P2/P3 有 disposition

## Bug Tracking Template
```json
{
  "bug_id": "BUG_001",
  "description": "...",
  "severity": "P0|P1|P2|P3",
  "status": "open|fixed|waived",
  "rtl_fix_commit": "abc123",
  "test_that_found": "test_burst_overflow"
}
```

## Output Required
- Regression pass/fail report
- Final merged coverage
- Open bug list
- Sign-off checklist
```

---

## 5. Orchestrator System Prompt

编排器的系统提示词即其 Agent 定义 [`verification-orchestrator.md`](../plugins/verification/agents/verification-orchestrator.md)，包含阶段顺序、回退规则、阶段门控和升级处理。本文不重复这些内容。
