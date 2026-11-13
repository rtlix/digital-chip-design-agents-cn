# 数字芯片设计 — Copilot 工作区说明

本工作区涵盖 14 个领域的数字 ASIC/FPGA 芯片设计工作：
架构评估、RTL 设计、功能验证、形式验证、逻辑综合、DFT、静态时序分析、
HLS、物理设计、SoC 集成、存储器 IP 设计、编译器工具链、嵌入式固件和 FPGA 原型验证（FPGA emulation）。

## 所有领域通用的行为要求

- 声明任一阶段完成前，先应用该领域的 QoR 指标。
- 按结构化格式输出：阶段状态用 JSON 块，权衡分析用 Markdown 表格。
- 每次只执行一个阶段，并在每个阶段后报告 **PASS / FAIL / WARN**。
- 继续之前先指出含糊之处，因为芯片设计属于安全关键领域。
- 超过阶段循环上限时，连同完整状态和建议一并升级给用户处理。

<!-- BEGIN SHARED:ide-guards (synced from tools/agent_shared_sections.md - edit there, then run tools/sync_agent_sections.py) -->
## 验证与报告

- 设置阶段状态前，读取工具 exit code 和报告。
- FAIL 后必须应用该阶段的 loop-back rule。
- 故障在不拥有的上游 artifact 中时，停止重试，报告上游领域、artifact 和证据。
- 重试须朝同一目标改善实测结果：退步则撤销，连续两次无变化则停止并报告，
  不能通过放宽失败的约束、检查或测试取得 PASS。
- 报告前执行任务点名的每个 gate，引用准确输出；未执行的 gate 标 NOT RUN 并说明原因。
- 向自带 CI 的仓库推送前，读取 **workflow path filters**，找出所改路径触发的所有 job，
  在本地执行每个 job 的全部步骤，**not only the step that last failed**；列出未能执行的步骤。
- 工具 exit 0 但输出为空/不可解析，不能算通过。
- 工具在检查设计前中止，或使用错误输入（filelist、include 路径、配置、生成头文件）时，
  不修改设计；报告该输入并停止。
- 结束前重读交付物清单，列出未完成项。
- **Whenever you stop, with or without signoff**（每次停止时，无论是否 signoff），都记录本次为下一阶段建立的信息：所产文件，
  以及未经工具运行而得出的全部结论。未声明 signoff 不意味着不交接内容。
- 区分 measured value 与 inference。
- 测试使用 generated artifact 时，确认每个执行该测试的环境能获取它：已提交，或由该环境实际执行的步骤重建。
- 超出单次 turn 的 job 后台运行并保存输出；按任务时长定期检查，日志安静不等于挂起。
- 任务预计超过 turn budget 时，停止等待，报告运行内容、日志及剩余工作，不能未经验证继续等候。
<!-- END SHARED:ide-guards -->

## 各领域专属规则

系统会根据你正在处理的文件，从
`.github/instructions/<domain>.instructions.md` 加载对应领域的规则、QoR 指标和阶段顺序。
这些文件由插件的 SKILL.md 源文件生成，包含芯片设计各阶段的完整领域知识。
