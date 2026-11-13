# 基础设施配置流程（Infrastructure Setup Flow）

## Stage Sequence

tool_discovery → module_discovery → tool_installation → wrapper_deployment → mcp_configuration → environment_validation
## 编排器与阶段 Skill

**插件：** `chip-design-infrastructure`
**Agent：** [`infrastructure-orchestrator.md`](../plugins/infrastructure/agents/infrastructure-orchestrator.md)
**Skill：** [`infrastructure/SKILL.md`](../plugins/infrastructure/skills/infrastructure/SKILL.md)

本文提供流程概览。具体规则以 Agent 和 Skill 为准。工具表、探测命令、Wrapper 与 MCP 配置列表及其数量均保存在这两个文件中，本文不重复，以免副本逐渐偏离原文（见 #118）。

---

## 1. 架构概览

基础设施是流水线的第 0 阶段，在任何设计领域编排器运行前准备工作站：

- 检查 `PATH` 或模块系统中可用的 EDA 工具；
- 为缺失工具生成安装脚本，但绝不执行；
- 部署 Shell Wrapper，将 10,000–50,000 行工具日志归纳为一个简洁的 JSON 对象；
- 写入 MCP 服务器配置，使领域 Agent 可以将这些 Wrapper 作为工具调用。

其他编排器依赖这些配置，但不直接读取其输出。各领域 Skill 假定相应 Wrapper 和 MCP 服务器已配置；若不存在，则退回直接执行，此时原始日志会占用上下文。

```
host ──► tool_discovery ──► module_discovery ──► tool_installation
                                                       │ (仅生成脚本)
         environment_validation ◄── mcp_configuration ◄── wrapper_deployment
                │
                ▼
     tool-manifest.json + environment.signoff
```

---

## 2. 共享状态

基础设施将状态保存在工作目录的文件中。每个文件都有明确的写入方。

| 文件 | 写入方 | 读取方 | 内容 |
|---|---|---|---|
| `tool-status.json` | `tool_discovery` 创建，`module_discovery` 原地更新 | 所有后续阶段 | **唯一**的逐工具记录：`tool`/`command`（必须是可执行命令名，而非产品名）、`status`、`version`、`path`、`role`、`dialect`、模块字段、`python_env` 与 `coverage_reporting_gaps` |
| `module-status.json` | `module_discovery` | `tool_installation`、`environment_validation` | 模块系统类型（`module_system`）与其列表是否可信（`module_listing`），两者独立 |
| `load-modules.sh` | `module_discovery`，仅在有符合条件的工具时生成 | 用户 | 加载所选版本的 `module load` 命令 |
| `install-missing-tools/install-<tool>.sh` | `tool_installation` | 用户 | 每个 `MISSING` 工具对应一个脚本；需要 project venv 时另生成 `install-python-venv.sh`；**流程绝不执行这些脚本** |
| `plugins/infrastructure/mcp/mcp-*.json` | `mcp_configuration` | 用户，复制到 `.claude/settings.json` | 使用已解析绝对路径的 MCP 配置 |
| `tool-manifest.json` | `environment_validation` | 用户、后续重新运行 | 验证**凭据**：Python 环境存活情况、Wrapper 可执行权限、MCP 文件存在性、命令方言冲突、simulator compile-and-run smoke、regression job bound、`SIM_BUILD` free space 及最终结论；引用 `tool-status.json`，不复制其内容 |
| `design_state.json` | 编排器，会话结束时 | 流水线 | `environment.{tools_validated, pdk_installed, signoff}` 和一条 `history[]` 记录 |

各数据结构定义见 Skill 中对应阶段的 **Output Required**。

---

## 3. 阶段顺序

```text
tool_discovery → module_discovery → tool_installation → wrapper_deployment → mcp_configuration → environment_validation
```

回退规则（目标阶段、迭代上限以及需要升级处理而非继续循环的失败）见 [`infrastructure-orchestrator.md`](../plugins/infrastructure/agents/infrastructure-orchestrator.md) 的 `## Loop-Back Rules`。以该文件为准，本文不重复这些规则。

---

## 4. 各阶段概述

每个阶段的详细规则位于 Skill 的 `## Stage: <name>` 下。

- **`tool_discovery`。** 探测所有开源和专有工具，并记录当前 Python 环境（`module`、`system`、`custom` 或 `venv`）。PATH 中第一个 `python3` 只算 candidate：EDA vendor tree 内的解释器标记为 `bundled`，永不选为 `PYTHON_EXEC`（参考主机的裸 `python3` 曾是 Calibre 自带 3.8.16）；选择满足 cocotb `Requires-Python` 的最新 `python3.N`，并优先 project-local venv。每个工具记录 `role` 与 `dialect`。商业工具用非交互 bash 的 `command -v` 解析，绝不依赖用户 alias，只检测/探测版本、不安装；例如 `xrun` 存在但 `imc` 缺失时记入 coverage-reporting gap。
- **`module_discovery`。** 分类模块系统，通过逐级尝试调用方式证明可以获取列表，再将仅通过模块提供的工具映射回 `tool-status.json`（`FOUND_PREFER_MODULE`、`MISSING_LOAD_MODULE`）。无法列出模块时报告 WARN；若关键路径工具仍缺失，则升级处理，因为这些工具尚未真正检查过。
- **`tool_installation`。** 根据检测到的操作系统和包管理器，为每个 `MISSING` 工具生成一个安装脚本及 TCL modulefile。Python 包通过 `python_env.exec -m pip` 安装，或由 `install-python-venv.sh` 建立 project venv；cocotb 版本从 CI 实际测试行读取，并检查 testbench 使用的是 1.x 还是 2.x API。该阶段不执行任何安装，因此只有用户运行脚本后，`MISSING` 状态才可能改变。
- **`wrapper_deployment`。** 设置全部 25 个 Wrapper 的可执行权限并执行安全 smoke。没有设计结果时预期 `WARN` + `verified:false`。除 MCP-backed wrapper 外，VCS/Xcelium compile、URG/IMC、cocotb results 和 11 个 PD/signoff wrapper 直接调用；`wrap-cocotb-results.sh` 不运行工具，只从 `results.xml` 得出 verdict，因为 cocotb `make` 可能 testcase 失败但仍 exit 0。
- **`mcp_configuration`。** 写入使用已解析路径的 MCP 配置并打印出来；不修改 `.claude/settings.json`，服务器注册由用户完成。
- **`environment_validation`。** 按 `tool_discovery` 相同方式重新检测，确认 Python 仍存活、25 个 Wrapper 可执行、MCP 文件存在，并报告同 role/不同 dialect 的共存。启用 simulator smoke 时，在 timeout 内**编译并运行** trivial module（license queue 可能等待而不是失败）；记录 regression job bound `min(cores, RAM / per-job peak, license seats)` 和 `SIM_BUILD` free space。关键路径工具（`yosys`、`verilator`、`openroad`、`sta`）缺失时直接升级。

---

## 5. 领域 Agent 如何运行工具

调用顺序由 Skill 的 **MCP Architecture — Two Tiers** 章节定义，简述如下：

1. **会话 MCP（Session MCP）：** 对支持持久 Tcl 进程的工具，在设计已加载时使用（如 ECO 循环）。
2. **批处理 MCP（Batch MCP）：** 每次调用运行一次 Wrapper，返回其 JSON。
3. **Wrapper 脚本：** 未注册 MCP 服务器时，通过 Bash 直接运行。
4. **直接执行：** 最后备选方案，原始日志会进入上下文。

完整流程工具（LibreLane/OpenLane 2、ORFS、全系统 gem5）可能运行 30 分钟至数小时，绝不通过 MCP 调用。Agent 通过 Bash 启动它们，并读取 `metrics.json` / `stats.txt`。

无论退出码如何，每个 Wrapper 每次运行都必须输出一个 JSON 对象（`status`、`verified`、`summary`、`errors`、`warnings`、`raw_log`）。**`verified: false` 不代表通过**：Agent 必须读取 `raw_log` 或工具报告后，才能确定阶段状态。数据结构定义见 `## Stage: wrapper_deployment`。

---

## 6. 添加工具

添加工具涉及多个位置，各处声明的数量由 `tests/test_agent_contract.py` 检查：

1. **发现。** 在 Skill 的开源或专有工具表中添加一行，以命令名为键，并给出 `role` 和 `dialect`；也要添加到 Agent 的 **Tool Options**。专有工具的探测命令必须经过验证，或标为 `UNVERIFIED`。还需在 `module_discovery` 的模块到工具映射表中添加以同一命令为键的行，否则 `test_critical_path_tools_are_keyed_by_command` 会失败。
2. **安装。** 若工具可安装，将其加入 Skill 的包名映射表。
3. **Wrapper（若有）。** 添加遵守 Wrapper JSON Output Schema 的 `plugins/infrastructure/tools/wrap-<tool>.sh`。更新 Skill 和 Agent 中所有 Wrapper 数量声明，否则 `test_stated_wrapper_count_matches_the_tools_directory` 会持续失败。
4. **MCP 配置（若有）。** 添加 `plugins/infrastructure/mcp/mcp-<tool>.json`，通过 `python3` 运行 `mcp-adapter.py`（批处理）或 `mcp-session-adapter.py`（会话），不要直接运行 Wrapper。在 `mcp_configuration` 中列出配置名，并更新工具服务器数量。
5. **关键路径。** 仅在下游流程缺少该工具就无法运行时，扩展关键路径集合。匹配命令键，不能使用产品名。

---

## 7. 交接

签核时，编排器在 `design_state.json` 中设置 `environment.signoff=true`；若配置了 `environment_validation` 检查点，则须先等待人工批准。

目前没有领域编排器直接读取 `environment.signoff`。Skill 的执行层级要求各领域 Agent 在退回 Wrapper 前，先检查其 MCP 服务器是否已在 `.claude/settings.json` 中启用。此检查十分必要：`mcp_configuration` 虽然写入并打印配置，但用户将配置粘贴到 `.claude/settings.json` 前，它们不会生效。

---

## 8. 编排器系统提示词

编排器的系统提示词即其 Agent 定义 [`infrastructure-orchestrator.md`](../plugins/infrastructure/agents/infrastructure-orchestrator.md)，包含阶段顺序、回退规则、阶段门控和升级处理。本文不重复这些内容。
