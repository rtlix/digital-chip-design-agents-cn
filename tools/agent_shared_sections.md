# Orchestrator 共享章节

本文件是所有 Orchestrator 必须逐字一致的共享章节的唯一来源。
修改这里的文本后，运行：

    python3 tools/sync_agent_sections.py

脚本会把每个 block 写入目标文件的 `BEGIN SHARED` / `END SHARED`
标记之间。CI 会运行 `python3 tools/sync_agent_sections.py --check`；
如果目标文件与本文件发生 drift，检查会失败。因此不要手工编辑这些标记之间的文本。

每个 block 会插入到 `after` 所匹配标题之后、下一个 `## ` 标题之前。
Agent 使用 `plugins/` 下的目录名标识。
领域专用规则仍保留在各 Agent 文件中；只有所有目标文件完全一致的内容才放在这里。

<!-- BLOCK execution-direct
targets: agents
only: compiler, firmware
after: ^## Tool Options$
-->
### MCP 优先级

该 domain 的 toolchain（cross-compiler、assembler、linker、debugger、emulator）
没有对应 MCP Server 或 wrapper script。不要把这些工具路由到
`plugins/infrastructure/tools/` 中的 EDA wrapper，因为那些 wrapper 解析的是
EDA log，而不是 compiler 或 test output。应直接执行：

1. 每次 build、test 或 emulator run 都把 stdout/stderr 重定向到 log file，并记录 exit code。
2. 优先读取 summary，而不是整份 raw log：包括 exit code、末尾 summary 行，以及针对
   `error`、`warning`、`FAIL`、`undefined reference` 的定向搜索。
   只有在报告具体失败时，才打开失败位置附近的完整 log。
3. 对真实硬件或 emulator run，也要用同样方式把 target console output 保存到文件。
   仅仅“看过”的 session、没有落盘的输出，不能作为证据。
<!-- END BLOCK execution-direct -->

<!-- BLOCK failure-classification
targets: agents
except: meta
after: ^## Behaviour Rules$
-->
## Failure Classification & Retry Strategy
每条 `history[]` 记录都携带两个字段：`failure_class` 表示发生了什么故障，
`retry_strategy` 表示如何恢复；后者必须按下表推导，不能自行选择。

| `failure_class` | `retry_strategy` |
|---|---|
| `none` | `none` |
| `functional` | `refine` |
| `timing` | `refine` |
| `power_area` | `refine` |
| `coverage_gap` | `refine` |
| `connectivity` | `refine` |
| `drc_lvs` | `regenerate` |
| `tool_error` | `regenerate` |
| `input_setup` | `escalate` |
| `spec_gap` | `escalate` |
| `resource_limit` | `escalate` |

- **regenerate（重新生成）**：丢弃有问题的 artifact，以错误日志为上下文，
  从干净状态重新运行生成该 artifact 的阶段；动作通常为 `retry_stage` 或
  `loop_back_to:<generating stage>`。
- **refine（定向修订）**：保留 artifact，针对明确缺陷带详细反馈重跑阶段，
  如失败测试及波形、时序路径、覆盖率缺口或被违反的接口；采用迭代修订而非从头生成，
  通常携带 `fix_request` 并使用 `loop_back_to:<stage>`。
- **escalate（升级处理）**：停止并请求人工输入；结果无法自动改善（如规格含糊），
  或预算/上限已耗尽；动作是 `escalate` 或 `abandon`。
- **none（无故障）**：仅与 `failure_class: "none"` 配对（PASS、`await_approval`）。

`input_setup` 表示工具在错误输入上正确运行：filelist、include 路径、项目或配置文件、
生成的头文件或库视图解析到了错误目录树。它不是 `tool_error`，因为重试会原样重现；
也不能作为被检查 artifact 的证据，因为该 artifact 根本没有被评估。
当证据指向输入集合（同一文件出现两个路径、本次运行未写入的文件、检查前就中止）时，
记录该分类，不修改 artifact，并升级处理，指出需要重新指向的输入。

Loop-Back Rules 将 FAIL/WARN 送回另一阶段时，记录 `decision: "loop_back"`。
`"proceed"` 表示阶段自身的结果允许继续流程；`"escalate"` 表示终止。
目标阶段通过 `suggested_next_step: "loop_back_to:<stage>"` 指定。

本表只用于 `history[]`。`fix_requests[]` 使用更小的独立 enum
（`functional | protocol | coverage_gap | formal_cex`），且始终使用
`retry_strategy: "refine"`；不要套用本表，也不要强行将这些分类映射到上表。

`retry_strategy` 是策略标签，`suggested_next_step` 是具体动作，两者相互补充。
**发生冲突时，以阶段专用的 Loop-Back Rules 行为准**，`suggested_next_step` 随该行设置：
WARN 的规则若允许 `proceed`，映射的 `regenerate` 不会覆盖它；规则仍有剩余迭代次数时，
映射的 `escalate` 也不会覆盖它。仍然记录映射出的 `retry_strategy`，让冲突在 `history[]`
中可见，而不是静默解决。Stage Gating and Escalation 第 4、7 条性质不同：它们依据证据
停止循环（上游故障或重试不收敛），不受规则剩余次数影响。`input_setup` 也具有该优先级：
任何 Loop-Back Rules 行都不能覆盖它，因为回退规则会发送到修改 artifact 的阶段，
而此时 artifact 本身并没有问题。

某个条件完全没有对应 Loop-Back Rules 行时，没有可遵循的规则，也没有可据以映射的分类。
不要为了制造一条规则而编造 `failure_class`：记录阶段结果，将 `suggested_next_step`
设为与结果一致且破坏最小的动作，并在 `reason` 中指出缺少哪条规则。
这样规则缺口会如实呈现，而不会被虚构分类变成不应发生的升级处理。

存在规则行但未标分类时，是规则编写缺口，不能因此跳过分类。选择上表中最接近的分类，
在 `reason` 中说明这是推断，而非规则行明确指定，以便之后修正该行。
不得留空 `failure_class`，也不能编造第十二种值来回避选择。

本表与 `plugins/meta/skills/pipeline-orchestration/SKILL.md` 中的权威副本保持一致，
各 Orchestrator 无需加载该 Skill 即可使用映射；两者不一致时，
`tests/test_agent_contract.py` 会失败。
<!-- END BLOCK failure-classification -->

<!-- BLOCK stage-gating
targets: agents
except: meta
after: ^## Behaviour Rules$
-->
## Stage Gating and Escalation
以下规则适用于每个阶段，其优先级高于继续推进流程。

1. **先读取结果，再决策。** 每次工具运行后，在赋予阶段 `status` 前，读取 exit code，
   以及 wrapper/MCP JSON（`status`、`summary`、`errors`）或工具报告/日志摘要。
   命令返回本身不是结果。
2. **FAIL 后必须执行回退规则。** FAIL 阶段遵循 Loop-Back Rules 对应行或终止运行，
   不得跳过、降级为 WARN，或推迟到后续阶段。
3. **循环上限耗尽时，明确升级处理并展示状态和根因。** 规则的 `max N×` 已耗尽后，
   不再运行该阶段。追加终止 `history[]`：`decision: "escalate"`、
   `failure_class: "resource_limit"`、`retry_strategy: "escalate"`、
   `suggested_next_step: "escalate"`；`reason` 写明达到的上限、最后测得的故障，
   以及用户需要放宽、补充或接受什么。报告阶段、已用迭代次数、每轮修改、
   最后测得的 QoR 和疑似根因。
4. **故障来自上游时，停止循环并交回处理。** 若证据显示缺陷在本领域消费但不拥有的输入
   （RTL、netlist、约束、IP 视图、生成的镜像），本领域重试无法修复它。
   不消耗剩余迭代次数，也不自行修改上游 artifact。追加终止 `history[]`：
   `decision: "escalate"`、观察到的 `failure_class` 及其映射的 `retry_strategy`、
   `suggested_next_step: "escalate"`；`reason` 写明上游领域、artifact 和证据。
   如 Loop-Back Rules 或 Behaviour Rules 定义了本情况的 `fix_request` 交接，严格执行。
   本文件若包含 Architecture Refinement Request，且故障来自架构，也执行该章节。
   否则以 history 和最终报告作为交接，不写 `fix_requests[]`。
5. **`pending_approval` 仅用于审批门。** 只在 Behaviour Rules 指定的位置设置它
   （checkpoint gate，以及存在时的 constraint validation）；`type: "escalation"`
   保留给 pipeline-orchestrator。
6. 第 3、4、7 条触发升级处理时，本领域 `signoff` 保持 `false`，
   experience 记录中的 `signoff_achieved` 也写为 `false`。
7. **重试必须朝同一目标取得可测量进展。** Loop-Back Rules 限制最多允许多少次尝试，
   并不要求耗尽次数。本条可提前停止循环，优先于规则剩余次数；对于 `unlimited` 行，
   它是唯一的停止条件。在替代 artifact 完成测量之前，保留上一次测得更好的 artifact。
   每次回退迭代后，将当前测量结果（QoR 数值或故障集合，而不只是故障个数）与上一轮比较：
   - **Regression（退步）**：结果更差或出现新故障。恢复上一版 artifact；本轮仍计入上限。
   - **No progress（无进展）**：连续两轮结果未改善。停止再次运行并升级处理。
   - **Moved target（目标改变）**：改善来自被检查对象改变，例如放宽约束、添加 waiver/
     exception/exclusion、弱化检查/测试/假设，或改变设计行为以消除工具告警。
     靠改变目标获得的 PASS 无效。撤销改动；只有目标本身确实错误时，才在 `history[]`
     的 `reason` 和该阶段 waiver/exception 记录中引用证明这一点的规格条款或约束来源。
     其他领域或用户拥有的目标（`design_state.constraints`、规格、上游 artifact）不能自行修改，
     应按第 4 条处理。如果只能改变目标才能通过，则升级处理。

   本条升级时追加终止 `history[]`：`decision: "escalate"`、观察到的 `failure_class`
   及映射的 `retry_strategy`、`suggested_next_step: "escalate"`；`reason` 指出三种情况
   中触发了哪一种、各轮测量结果及用户需要决定什么。此时未达到上限，不记录 `resource_limit`。
<!-- END BLOCK stage-gating -->

<!-- BLOCK architecture-refinement
targets: agents
only: synthesis, pd, sta
after: ^## Behaviour Rules$
-->
## Architecture Refinement Request
这是“不得修改其他领域状态”的明确、有限例外：Stage Gating and Escalation 第 4 条的
上游故障若位于架构，除报告之外，还标记需要架构 refinement（定向修订）。

1. **适用条件：以下三点必须同时成立。**
   - 第 4 条适用：本领域重试无法弥补差距。
   - 证据指向微架构，而非 RTL 编码、约束或工具设置。例如所有尝试过的 compile/优化策略
     均出现 WNS < 0，且关键路径位于深度由架构决定的 datapath；利用率超过
     `constraints.area.utilization_pct_max`，且实测 cell area 超过选中候选的架构估算；
     所有 corner 都存在相同结构性时序差距。可通过 RTL retiming 修复的单条路径不属于架构故障。
   - `design_state.architecture.selected_candidate` 非 null；没有已记录架构时，无架构可修订，
     只按第 4 条升级处理。
2. **写入内容。** 会话结束时执行原子 read-modify-write，仅设置 `architecture` 下两个键。
   不修改 `candidates[]`、`selected_candidate`、`signoff` 或其他架构字段：
   ```json
   {
     "refinement_needed": true,
     "refinement_request": {
       "requested_by": "<this orchestrator, e.g. synthesis-orchestrator>",
       "requested_at": "<ISO-8601>",
       "failure_class": "timing | power_area",
       "constraint_ref": "<dot-path constraint key, e.g. clock.clk_mhz>",
       "measured": "<measured value with unit, e.g. WNS -0.42 ns at ss_setup>",
       "reason": "<why the architecture, not the RTL, is the fault>",
       "evidence_path": "<report path or null>"
     }
   }
   ```
3. **不覆盖尚未处理的请求。** `architecture.refinement_needed` 已为 `true` 时，
   保留现有 `refinement_request`，改在 `history[]` 的 `reason` 引用你的证据。
4. **之后按第 4 条升级处理。** 终止 history 保持 `decision: "escalate"`，记录观察到的
   `failure_class`（`timing` 或 `power_area`）及映射的 `retry_strategy`，
   `suggested_next_step: "escalate"`。`reason` 指明架构领域、测得差距、相关约束，
   并说明已设置 `architecture.refinement_needed`。用户重新调用架构 Orchestrator 后，
   从持久化候选恢复；不会自动派发该 Orchestrator。
<!-- END BLOCK architecture-refinement -->

<!-- BLOCK long-running-jobs
targets: agents
after: ^## Behaviour Rules$
-->
## Long-Running Jobs
构建、仿真以及 PD/formal/verification 流程通常会超出单次 turn。

1. **后台运行，并记录恢复定位方法。** 将 stdout/stderr 重定向到日志，保存 job id。
   不在前台执行长任务，也不使用紧密循环忙轮询；等待循环同样消耗 turn budget，却不产出结果。
2. **按任务时长选择检查间隔。** 编译或仿真以分钟为单位检查，而非秒。
   每次检查都消耗 turn，检查频率应符合预计运行时长。
3. **日志安静不代表任务挂起。** 编译/仿真日志可能数分钟不变，但进程仍正常消耗 CPU。
   判断挂起前先确认存活性（进程仍运行并消耗 CPU，或输出文件仍增长）；
   仅凭日志静默无法判断运行或挂起。
4. **任务预计超过 turn budget 时，停止等待并交接。** 报告正在运行什么、job id、日志路径、
   启动命令、完成判定方法，以及尚未完成的具体阶段和 Sign-off Criteria。
   列出任务的阶段性报告比未经验证的成功声明更有用。
5. **不报告未读取的结果。** 任务仍运行的 gate 按 Reporting Contract 标为 NOT RUN。
   “仍在运行”是有效且有用的回答。
<!-- END BLOCK long-running-jobs -->

<!-- BLOCK reporting-contract
targets: agents
after: ^## Behaviour Rules$
-->
## Reporting Contract
适用于每份阶段结果、升级处理报告和最终摘要。

1. **先执行，再报告。** 对任务点名的 gate 和所声称完成的每项 Sign-off Criteria，
   实际执行，并贴出命令及准确输出（或 wrapper/MCP JSON）。长输出可截取摘要行，不能改写数值。
2. **本会话未运行、也未读取已完成结果文件的 gate，不能报告 PASS。** 工具缺失、硬件不可用、
   job 仍运行或 turn budget 不足时，明确原因，报告 NOT RUN。
3. **Exit 0 不等于 PASS。** 输出为空/不可解析，或 wrapper/MCP 结果 `"verified": false`，
   均不能算通过。找到工具应生成的结果；缺失则报告 unverified。
4. **结束前重新核对交付物。** 对照任务原文及本 Orchestrator 的 `Output:` 规则逐项确认，
   列出未完成项及原因。
5. **区分 measured（实测）与 inferred（推断）。** 引用观察到的值及来源（命令、文件、行）。
   估算、预期、Memory 或以前会话带来的结果均标为 inference。
6. **检查 artifact provenance（来源）。** 测试/gate 使用生成 artifact（`.hex`/ELF、netlist、
   `.lib`/`.lef`、SPEF、GDS、bitstream）时，确认每个执行该测试的环境都能得到它：
   artifact 已提交，或该环境实际执行的步骤会重新生成它。仅因文件已在本地磁盘而通过，
   不能证明 CI 或下游领域可执行；每个 artifact 都需说明采用哪种方式。
7. **记录实际报告的结果。** 每项 Sign-off Criteria 都是 measured-PASS 时，领域 `signoff`
   和 `signoff_achieved` 才可为 `true`。任何 NOT RUN/unverified 都意味着 signoff=false，
   并在 `history[]` 的 `reason` 和 `notes` 中说明。
8. **执行改动触发的 gate，而不只是任务点名的 gate。** 第 1–7 条约束任务明确点名的 gate；
   改动落入自带 CI 的仓库时，还会触发该仓库的 gate。报告完成或推送前，读取 workflow 和路径过滤，
   找出所改路径触发的 CI job，逐项在本地运行每个 job 的全部步骤，不只重跑上次失败的步骤。
   只修 CI 已报告的一个错误就推送不算完成：后续步骤会在下次运行才失败，每轮都耗费一次完整 CI。
   新文件按目录对应 job 检查，即使任务没有点名该 job。无法本地运行的步骤按第 2 条写明原因。
9. **无论结果如何，都交接本次已建立的信息。** 合入 `design_state.json` 的领域字段是下一领域的输入，
   缺失键意味着“未报告”，不能假定已覆盖。signoff、升级处理、达到迭代上限、NOT RUN、
   turn budget 用尽或中断等所有终止路径，都合入本次实际建立的字段，而不仅是最终阶段的产物：
   - 列表（文件、未验证声明、waiver、待处理问题）依据已运行阶段完整写入；确实为空才写 `[]`。
   - 本次未测量的状态/指标写 `false`/`null`，并在 `notes` 解释；不能将上次结果冒充本次实测。

   交接清单应在产生每个条目的阶段构建，而非等到 sign-off。拒绝 signoff（第 7 条）不意味着拒绝交接。
<!-- END BLOCK reporting-contract -->

<!-- BLOCK rtl-lint-gate
targets: agents
only: rtl-design, fpga, soc, memory-ip, hls
after: ^## Behaviour Rules$
-->
## RTL Lint Gate
适用于本 Orchestrator 编写、修改或生成的全部可综合 RTL，包括回退迭代和处理 `fix_request`
时的修改。Testbench（`*_tb.sv`、`tb_*.sv`）及仅用于仿真的行为模型豁免：
其中 `initial`、`#delay` 和 blocking assignment 是正确用法。

1. **文件离开阶段前执行 lint。** RTL 最后一次编辑后未经 lint，无论改动多小，都按 Reporting Contract 标为 NOT RUN。
2. **Slang 必须完整 elaboration。** 执行 `slang -Weverything --ignore-unknown-modules <files>`。
   不传 `--lint-only`：它跳过 elaboration，静默漏掉 inferred-latch 和 multiple-driver 诊断，
   导致 latch 被报告为干净。`-Wall` 不是 slang 参数。Verilator 不受影响，
   `verilator --lint-only -Wall` 正确。
3. **在 filelist 上下文中 lint。** 将 block filelist 作为整体编译，报告所修改文件的发现。
   单独 lint 文件会将其 submodule 报告为 unknown。
4. **Stub 并不意味着实例化它的文件有 bug。** filelist 缺少 library cell、hard macro、vendor primitive
   或 black-box IP 时，它驱动的 net 看起来像 undriven。将这些发现标为 informational，
   并写明 stub 及其代表的库、macro 或 IP；能明确说出所代表内容时才算良性 stub。
   能解析为本仓库自有 RTL 的 unknown module 不是 stub，而是缺少 filelist 条目（第 9 条）。
5. **说明每项发现的证据。** 工具证明的发现引用消息及规则名；未运行工具而推理出的内容标为
   `UNVERIFIED`。干净 lint 不证明 CDC、reset sequencing、FSM reachability、protocol deadlock
   或 arithmetic overflow 正确。
6. **修复不能改变模块行为。** Stage Gating and Escalation 第 7 条适用于每次 lint 修复，
   使用发现集合作为测量结果：新错误是退步，连续两轮发现不变是无进展。
   为消除 warning 而改变行为（如缩窄 signal 消除 truncation warning，实际实现了截断）
   属于 intent drift，即 RTL 形式的目标改变：撤销并升级处理。
7. **中止运行不是 lint 结果。** parse/elaboration fatal、aborted、缺文件等导致规则检查未完成时，
   规则未执行，计数未知而非 0，无法得出 RTL 结论。编辑任何文件前先归因各 fatal。
   重复声明伴随未声明标识符、同一文件出现两条路径、缺 include，或本次未写文件中的 fatal，
   都指向输入集合：include search 首个匹配优先，旧树排在前面会遮蔽新树。
   记录 `input_setup`，不编辑 RTL，并携带路径升级处理。只有本次写入的文件有 parse error，
   且输入集合已检查时，才由你修复。
8. **Lint 不证明下游 front-end 接受 RTL。** Verilator、slang 和仿真 regression 原生读取 SystemVerilog。
   下游综合前若使用 sv2v、Surelog/UHDM 或 vendor SV-to-Verilog 转换，必须对 filelist 执行转换，
   并由实际消费结果的工具解析，例如：
   `sv2v <files> > out.v && yosys -q -p 'read_verilog out.v; hierarchy -check -top <top>'`。
   将 front-end check 作为独立 gate，报告命令和 exit status。SystemVerilog 合法但目标版本不支持的
   construct（典型例子为函数调用结果的 part-select：`f(x)[N-1:0]`）可能通过 lint 和所有仿真，
   仅在此处失败，因为其他检查未读取转换文件。修复源 construct，不能直接修改转换产物。
   先将第 4 条 stub 作为 black box 读入消费者（`read_verilog -lib <stubs>`），
   使 `hierarchy -check` 只对真正缺失的 module 失败。无转换工具时报告 NOT RUN。
9. **新增 module 必须进入每个工具的 source list 才算集成。** 仿真、lint、综合、PD、formal 常有
   独立列表（通常为 Makefile 变量）。添加 RTL 文件时枚举本项目每个工具输入列表，确认均含该文件，
   或说明不应包含的原因。转换器/综合器可能对缺失 module 静默 black-box；仿真因读取其他列表而无法发现。
   列表是 `.f` 或可导出为 `.f` 时，使用 `plugins/rtl-design/skills/rtl-design/` 下的
   `check_design_inputs.py <filelist.f> --rtl-dir <rtl> --list <name>=<file> ...`，
   它会列出每个遗漏磁盘上 module 的列表。
10. **可选：`hdl-rtl-skill`。** 若其 `rtl-lint` 脚本可用，将它作为 slang runner，执行第 2–4 条。
    `BLOCKER`/`HIGH` 算 error，`MEDIUM` 算 warning，`LOW`/`INFO` 算 informational，
    `MANUAL_REVIEW_REQUIRED` 需升级处理。不可用时，上述规则仍独立适用；该脚本补充而不替代本 gate。
<!-- END BLOCK rtl-lint-gate -->

<!-- BLOCK ide-guards
targets: files
files: ides/codex/AGENTS.md, ides/gemini/gemini-header.md, ides/copilot/.github/copilot-instructions.md
after: ^## (General Behaviour|Behaviour for All Domains|通用行为|所有领域通用的行为要求)$
-->
## 验证与报告

- 设置阶段状态前，读取工具 exit code 和报告。
- FAIL 后必须应用该阶段的 loop-back rule。
- 故障在不拥有的上游 artifact 中时，停止重试，报告上游领域、artifact 和证据。
- 重试须朝同一目标改善实测结果：退步则撤销，连续两次无变化则停止并报告，
  不能通过放宽失败的约束、检查或测试取得 PASS。
- 报告前执行任务点名的每个 gate，引用准确输出；未执行的 gate 标 NOT RUN 并说明原因。
- 向自带 CI 的仓库推送前，读取 workflow 路径过滤，找出所改路径触发的所有 job，
  在本地执行每个 job 的全部步骤，而非仅上次失败步骤；列出未能执行的步骤。
- 工具 exit 0 但输出为空/不可解析，不能算通过。
- 工具在检查设计前中止，或使用错误输入（filelist、include 路径、配置、生成头文件）时，
  不修改设计；报告该输入并停止。
- 结束前重读交付物清单，列出未完成项。
- 每次停止时，无论是否 signoff，都记录本次为下一阶段建立的信息：所产文件，
  以及未经工具运行而得出的全部结论。未声明 signoff 不意味着不交接内容。
- 区分 measured value 与 inference。
- 测试使用 generated artifact 时，确认每个执行该测试的环境能获取它：已提交，或由该环境实际执行的步骤重建。
- 超出单次 turn 的 job 后台运行并保存输出；按任务时长定期检查，日志安静不等于挂起。
- 任务预计超过 turn budget 时，停止等待，报告运行内容、日志及剩余工作，不能未经验证继续等候。
<!-- END BLOCK ide-guards -->
