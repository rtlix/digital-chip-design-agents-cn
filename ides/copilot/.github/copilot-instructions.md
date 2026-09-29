# Digital Chip Design — Copilot Workspace Instructions

This workspace contains digital ASIC/FPGA chip design work spanning 14 domains:
architecture evaluation, RTL design, functional verification, formal verification,
logic synthesis, DFT, static timing analysis, HLS, physical design, SoC integration,
memory IP design, compiler toolchain, embedded firmware, and FPGA emulation.

## Behaviour for All Domains

- Apply domain-specific QoR metrics before declaring any stage complete.
- Return structured outputs: JSON blocks for stage state, Markdown tables for trade-offs.
- Execute one stage at a time and report **PASS / FAIL / WARN** after each stage.
- Flag ambiguities before proceeding — chip design is safety-critical.
- When a stage loop limit is exceeded, escalate to the user with full state and recommendations.

<!-- BEGIN SHARED:ide-guards (synced from tools/agent_shared_sections.md - edit there, then run tools/sync_agent_sections.py) -->
## 验证与报告

- 给 stage 设置状态前，先读取工具 exit code 和 report。
- 遇到 FAIL 时必须应用该 stage 的 loop-back rule，不得直接继续。
- 如果故障位于你不拥有的上游 artifact，停止 retry，并报告上游 domain、artifact 和证据。
- 报告前，运行任务中点名的每个 gate，并引用其准确输出。
  没有运行的 gate 绝不能说 PASS；应明确写 NOT RUN 并说明原因。
- 工具 exit 0 但输出为空或不可解析，不能算 PASS。
- 结束前重新核对交付物清单，并列出任何未完成项。
- 区分 measured value 与 inference。
- 如果 test 消费 generated artifact，确认每个运行该 test 的环境都能获得它：
  要么 artifact 已提交，要么该环境实际执行的步骤会重新构建它。
<!-- END SHARED:ide-guards -->

## Domain-Specific Rules

Per-domain rules, QoR metrics, and stage sequences are loaded from
`.github/instructions/<domain>.instructions.md` based on the files you are working with.
These files are generated from the plugin SKILL.md sources and contain the full
domain knowledge for each chip design stage.
