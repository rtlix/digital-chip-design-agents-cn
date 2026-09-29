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

<!-- BLOCK stage-gating
targets: agents
except: meta
after: ^## Behaviour Rules$
-->
## Stage Gate 与升级

这些规则适用于每个 stage，并且优先级高于“继续推进流程”。

1. **先读取结果，再做判断。** 每次工具运行后，都必须读取它真正生成的结果：
   exit code 加 wrapper/MCP JSON（`status`、`summary`、`errors`），或者工具自己的
   report/log summary，然后才能给 stage 设置 `status`。命令返回本身不等于已经得到有效结果。
2. **FAIL 不能直接越过。** Stage 返回 FAIL 时，必须按 Loop-Back Rules 对应项处理，
   或结束本次运行。不得跳过、降级为 WARN，或推迟到后续 stage。
3. **循环上限耗尽时必须明确升级，并展示状态与根因。**
   某条 loop-back 已使用完 `max N×` 后，不要再次运行该 stage。
   追加 terminal `history[]`，设置
   `decision:"escalate"`、`failure_class:"resource_limit"`、
   `retry_strategy:"escalate"`、`suggested_next_step:"escalate"`，
   并在 `reason` 中说明达到的上限、最后一次 measured failure，
   以及用户必须放宽、补充或接受什么。
   最终报告要列出 stage、已使用的迭代次数、每轮改变了什么、最后测得的 QoR，以及疑似根因。
4. **如果故障属于上游，停止本域循环并交回。**
   如果证据表明缺陷位于本 domain 只消费但不拥有的输入
   （RTL、netlist、constraint、IP view、generated image），
   在本域继续 retry 无法修复。不要浪费剩余 loop，也不要自行 patch 上游 artifact。
   追加 terminal `history[]`，设置 `decision:"escalate"`，
   使用观测到的 `failure_class` 及其映射出的 `retry_strategy`，
   `suggested_next_step:"escalate"`，
   并在 `reason` 中写明上游 domain、artifact 和证据。
   如果 Loop-Back Rules 或 Behaviour Rules 为这种情况定义了 `fix_request` hand-off，
   则严格执行；否则 history entry 与最终报告就是 hand-off，不要写入 `fix_requests[]`。
5. **`pending_approval` 只用于 gate。**
   只有 Behaviour Rules 明确要求的地方才设置它
   （checkpoint gate，以及适用时的 constraint validation）。
   `type:"escalation"` 仅由 pipeline-orchestrator 使用。
6. 上述两类 escalation 终止时，本 domain 的 `signoff` 必须保持 `false`，
   experience record 中 `signoff_achieved` 也必须为 `false`。
<!-- END BLOCK stage-gating -->

<!-- BLOCK reporting-contract
targets: agents
after: ^## Behaviour Rules$
-->
## 报告契约

适用于你生成的每一份报告：stage result、escalation 以及最终 summary。

1. **先运行，再报告。**
   对任务中点名的每个 gate，以及你声称通过的每项 Sign-off Criteria，
   都必须在本次会话真实运行，或读取已经完成的 result file，
   并给出命令及其准确输出（或 wrapper/MCP JSON）。
   长输出可以裁剪到 summary 行，但数值绝不能改写。
2. **本次会话没有运行、也没有读取完整结果的 gate，绝不能报告为 PASS。**
   如果因为工具缺失、硬件不可用、job 仍在运行或 turn budget 不足而无法确认，
   必须明确说明原因，并把该 gate 报告为 NOT RUN，而不是 PASS。
3. **Exit 0 不代表 PASS。**
   工具 exit 0 但输出为空或无法解析，或者 wrapper/MCP 返回
   `"verified": false`，都不能算通过。
   必须找到该工具本应生成的结果；如果结果不存在，则把 gate 报告为 unverified。
4. **结束前立即重新核对交付物清单。**
   回到任务原文以及当前 Orchestrator 的 `Output:` 规则，
   逐项确认是否完成。任何未完成项都必须列出并解释原因。
5. **区分 measured 与 inferred。**
   引用你真正观察到的数值及来源（命令、文件、行号）。
   其他内容——估算、预期、从 Memory 或前一 session 带来的结果——必须标记为 inference。
6. **检查 artifact provenance。**
   如果 test 或 gate 使用 generated artifact
   （`.hex`、ELF、netlist、`.lib/.lef` view、SPEF、GDS、bitstream），
   必须在每个真正会运行该 test 的环境里确认 artifact 的来源，而不只是检查你当前环境。
   要么 artifact 已提交，要么那个环境实际执行的步骤会重新生成它。
   仅因为本地磁盘已有文件而通过，不能证明 CI 或下游 domain 能运行。
   每个此类 artifact 都要说明采用了哪一种保证方式。
7. **记录你实际报告的结果。**
   只有每项 Sign-off Criteria 都是 measured-PASS 时，
   domain 的 `signoff` 和 `signoff_achieved` 才能设为 `true`。
   任一判据为 NOT RUN 或 unverified，都意味着 signoff=false；
   必须在 `history[]` 的 `reason` 和 `notes` 中指出。
<!-- END BLOCK reporting-contract -->

<!-- BLOCK ide-guards
targets: files
files: ides/codex/AGENTS.md, ides/gemini/gemini-header.md, ides/copilot/.github/copilot-instructions.md
after: ^## (General Behaviour|Behaviour for All Domains|通用行为|所有领域通用的行为要求)$
-->
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
<!-- END BLOCK ide-guards -->
