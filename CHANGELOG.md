# 变更记录

## [Unreleased] — feat/reporting-contract 分支

### 新增

- **全部 16 个 Orchestrator**：新增 `## Reporting Contract` 章节（issues #75、#78），内容统一从 `tools/agent_shared_sections.md` 同步。过去 sign-off 判据只是声明式属性，没有规则要求这些判据必须经过实际观测，而不是由 Agent 自行声称。新契约要求：运行任务中点名的每个 gate 并引用其准确输出；本次会话没有实际运行的 gate 绝不能报告为通过（应报告 NOT RUN 并说明原因）；exit code 为 0 但输出为空或无法解析不能算 PASS；结束前重新核对交付物清单；明确区分 measured value 与 inference；对测试依赖的所有 generated artifact，在每个实际运行环境中验证其来源；只有全部判据都是 measured-PASS 时，才能把 `signoff` / `signoff_achieved` 设置为 true。
- **Codex、Gemini、Copilot header**：在 `## Verification and Reporting` 中加入上述契约的 5 条精简规则。
- **Wrapper JSON 的 `verified` 字段**：当 `status` 基于工具输出中成功解析出的结果，或明确失败证据时为 `true`；当工具 exit 0 但没有可识别结果，或工具根本没有运行时为 `false`。Infrastructure Skill 的 wrapper schema 已补充说明。
- **测试**：`tests/test_wrappers.py` 通过 bash 使用 fake tool 运行每个真实 wrapper（Windows 默认跳过，除非 `RUN_WRAPPER_TESTS=1`）；`tests/test_mcp_adapter.py` 覆盖 adapter 对 wrapper 输出的解释逻辑。

### 变更

- **行为变化——8 个 EDA wrapper 不再在缺乏证据时报告 `PASS`。** 过去状态只根据 exit code 和 ERROR/WARNING 行计算，因此工具 exit 0 且输出中没有 wrapper 认识的内容时也会被判为 `PASS`。现在 wrapper 必须从输出中解析出有效结果，否则返回 `WARN`、`verified:false`，并在第一条 warning 中明确说明。证据仍使用 wrapper 已有的字段，不新增 log marker。安静运行，例如 `yosys -q` 或仅执行 `--version` 的 smoke test，过去返回 PASS，现在返回 WARN。exit code 本身仍原样透传。
  - `wrap-verilator-sim.sh`：只有出现 `TEST PASSED` 才能判定 `PASS`。exit 0 时即使出现 ERROR 行也只给 `WARN` 而不是 `FAIL`，因为仿真日志中可能出现诸如 “Error count: 0”。
  - `wrap-klayout.sh`：若 report 可解析且没有 category，视为 clean run；如果既没有 report，也无法从 log 中解析 count，则 `drc_total` 为 `null`，不再伪装成 `0`。
- **行为变化——`mcp-adapter.py`**：过去 exit 0 时，空 wrapper 输出会被判 PASS，非 JSON 输出判 WARN，无合法 `status` 的 JSON 也会继续透传。现在这三类情况全部返回 `FAIL` 且 `verified:false`，因为 wrapper contract 要求每次运行都必须输出 JSON。合法 wrapper JSON 仍保持原样透传。只有 `status == "FAIL"` 时 `isError` 才为 true。
- **`mcp-session-adapter.py`**：`query_drc` 在无法解析 count 时返回 `drc_total:null`，不再返回 0。

## [Unreleased] — feat/shared-orchestrator-guards 分支

### 新增

- **共享 Orchestrator 章节，从单一源同步**（issue #77）。`tools/agent_shared_sections.md` 保存所有 Orchestrator 必须逐字一致的共享规则；`tools/sync_agent_sections.py` 将内容写入每个目标文件的 `BEGIN SHARED` / `END SHARED` 标记之间。`--check` 用于检测 drift 并在 CI 中运行；`--list` 显示每个共享 block 应写入哪些文件。脚本会保留原文件换行风格，因此 CRLF 工作区和 LF CI 环境可以得到一致结果。对应测试位于 `tests/test_sync_agent_sections.py`。
- **15 个 Orchestrator**：新增 `## Stage Gating and Escalation`。规则包括：给 stage 设置状态前必须先读取工具真实结果；遇到 FAIL 必须应用 loop-back，不能直接越过；loop cap 用尽后必须停止并携带状态/根因升级；如果故障来自上游 artifact，则停止本域循环并交回。过去这些 guard 只零散存在于 `pd`、`rtl-design`、`memory-ip`、`architecture`、`infrastructure` 的一两个规则中，另外十个 domain Orchestrator 对达到最大迭代次数完全没有统一规则。由于 `pipeline-orchestrator` 本身负责 dispatch，并拥有 `pending_approval` 的 `escalation` 类型，因此不包含该共享段。
- **`compiler` 和 `firmware` Orchestrator**：新增 `### MCP Preference`。这些 toolchain 没有 MCP Server 或 wrapper，因此规则要求使用直接执行并把输出保存到 log 文件，而不是 EDA domain 常用的 MCP → wrapper → direct 三级路径。
- **Codex、Gemini、Copilot header**：增加精简版 `## Verification and Reporting`。Copilot/Codex 安装只接收 Skill，不会安装 Agent 文件。
- **`.gitattributes`**：加入 `* text=auto` 和 `*.sh text eol=lf`，保证 Windows checkout 后 shell script 仍可正常运行。

### 变更

- **统一 `pending_approval` 所有权。** Pipeline Skill 一度规定 domain Orchestrator 只能设置 `type:"checkpoint"`，但又要求 constraint validation 使用 `type:"constraint_gap"`；同时 15 个 Orchestrator 里还有一句话暗示任何 escalation 都可设置 `pending_approval`。现在 domain Orchestrator 只在两个 gate 使用它：checkpoint 和 constraint validation。loop cap 耗尽或上游 fault 的 escalation 只写 terminal `history[]`，其 `reason` 必须包含 `failure_class` 和用户需要补充的内容。`type:"escalation"` 仍由 `pipeline-orchestrator` 独占。Schema 不变。
- `pd`、`architecture`、`infrastructure`、`rtl-design`、`memory-ip` 中已有的一次性 guard 保留原 rule number，现在改为引用共享章节。
- **`validate.yml`**：Agent 必须包含 `## Behaviour Rules`，作为共享区块插入锚点；新增步骤运行 `tools/sync_agent_sections.py --check`。
- **`CONTRIBUTING.md`**：补充同步步骤；修正 “Adding a New Skill” 和本地校验示例中的错误路径（过去误写成不存在的根目录 `skills/`）；修正数量约束，Skill 数可以大于 Agent 数。
- 修正 `CONTRIBUTING.md`、`docs/MASTER_INDEX.md`、`memory/README.md`、`FUTURE_WORK.md` 中过时的数量统计。

## [Unreleased] — fix/signoff-achieved-template 分支

### 修复

- **13 个 Orchestrator**：`experiences.jsonl` 模板原来写死 `"signoff_achieved": true`，但外围规则又要求 escalation/abandonment 时也写该记录（issue #74）。`distill.py` 使用 `is True` 统计 sign-off，因此默认 true 会把失败 run 错记成成功。模板现统一默认 false，与 `pd` 和 `infrastructure` 保持一致，并在模板下直接说明什么时候才允许改为 true（`soc` 过去没有该说明）。使用 literal `false`，而不是 `"<true|false>"` 字符串，因为字符串永远不会满足 `is True`。`memory/README.md` 的 canonical schema 也同步修正。
- **8 个 Orchestrator**（`dft`、`firmware`、`fpga`、`memory-ip`、`rtl-design`、`sta`、`synthesis`、`verification`）：过去写着 “append one JSON line”，同时模板又没有 `run_id`，与 `memory/README.md` 及各自 Skill 自相矛盾。现在统一按 `run_id` upsert。`fpga` Skill 曾有一套独立 append-only schema（`stage`、`outcomes`、`metrics`、`tools`），`distill.py` 无法从中读取 metrics，现在改为引用共享 record schema。README 也不再称该文件为 append-only。
- **6 个 Orchestrator**（`architecture`、`dft`、`firmware`、`formal`、`fpga`、`hls`）：history 中 `decision` enum 漏了 checkpoint gate 实际会写入的 `await_approval`，现已补齐。

### 新增

- **`tests/test_agent_contract.py`**：对 Agent/Skill Markdown 进行静态检查——禁止硬编码 `"signoff_achieved": true`、禁止 append-only 表述、每个 experience 模板都必须包含 `run_id`，以及任何会写 `await_approval` 的 Agent，其 `decision` enum 都必须列出该值。

## [1.8.0] — Memory IP Design domain

### 新增

- **`chip-design-memory-ip`——第 16 个插件、第 14 个设计 domain。** 负责嵌入式 Memory IP（SRAM / register file / ROM）设计。过去 pipeline 把 memory 当作外部黑盒：PD 负责放置、synthesis 对其 `dont_touch`、DFT 负责测试、SoC 验证 view、FPGA 用 BRAM 替换，但没有任何 domain 真正“产出” memory。该 domain 补上了这个缺口。
  - **`plugins/memory-ip/skills/memory-ip-design/SKILL.md`**：7 个 stage：`memory_requirements → macro_selection → array_architecture → redundancy_repair → view_generation → integration_prep → memory_signoff`。覆盖 bandwidth/ECC sizing、column-mux/banking 权衡、slow-corner access time 选择、write/read assist 与 Vmin、SECDED check-bit sizing/scrubbing、基于 defect density 的 spare row/column 分配、soft/hard repair 与 efuse map，以及 view QA（`.lib/.lef/.v` pin 一致性、timing arc 完整性、corner coverage、LEF obstruction）。
  - **`plugins/memory-ip/agents/memory-ip-orchestrator.md`**：定义 stage sequence、7 条 loop-back、sign-off 判据以及明确 domain 边界：不能插入 MBIST 或声称 MBIST coverage（属于 `chip-design-dft`），不能做 floorplan（属于 `chip-design-pd`），不能 timing sign-off（属于 `chip-design-sta`），不能分配 memory map（属于 `chip-design-soc`）。
  - **`design_state.json` handoff**：新增 `memory_ip` block，包含 `instances`、`views`、`repair`（scheme、spare count、repair-register width、efuse map）、`placement_constraints`、`ecc`、`power_modes`。DFT 消费 `instances + repair`；PD 消费 `placement_constraints`；STA 消费 `views.lib`；verification 消费 `views.verilog`。
  - **`constraints.memory_ip`**：`vmin_margin_mv`（50）、`repair_yield_pct_min`（99）、`ecc_required`（false）、`max_aspect_ratio`（4.0）、`retention_required`（true）。这里仅只读使用 `constraints.dft.mbist_coverage_pct`。
  - 新增 `memory/memory-ip/knowledge.md` seed 与 `docs/Memory_IP_Design_Flow.md`。
  - `key_metrics`：`memory_instances`、`total_memory_area_um2`、`worst_access_time_ns`、`view_qa_errors`、`projected_repair_yield_pct`。

### 变更

- 全仓数量更新为 **16 plugins / 17 skills / 16 agents / 14 design domains**，涉及 `marketplace.json`、`package.json`、`README.md`、`CLAUDE.md`、`docs/PIPELINE.md`、`docs/MASTER_INDEX.md`、`docs/INSTALL.md`、Codex/Gemini/Copilot IDE header，以及 `.github/workflows/release.yml`。
- **Manifest version 与 release tag 重新对齐。** `package.json` 和 `.claude-plugin/marketplace.json` 曾停在 1.3.0，而 tag 已前进到 v1.7.0；PR #71 又将其改为 1.4.0，既不符合当前 tag，也会产生 v1.7.0 之后再发 v1.4.0 的倒退。两处现统一为 1.8.0，作为该 MINOR 变更（新增 Orchestrator domain）的下一版本，符合 `CONTRIBUTING.md` 约定。发布时 `release.yml` 的 `npm-publish` job 会按 tag 重写版本号，因此仓内值只是信息性字段，但至少不能与计划发布 tag 矛盾。
- `validate.yml` 的 count assert 由 15 → 16（agents/marketplace 和 `applyto-map.json`）；`tests/test_distill.py` 的 domain count 由 14 → 15。
- `distill.py`、`tools/qor_trends.py`、`memory/README.md`、`memory-keeper/SKILL.md` 注册新 domain；`projected_repair_yield_pct` 加入 `HIGHER_IS_BETTER`。
- 安装器更新：`install.sh`、`install.ps1`（plugin list、dir map、`enabledPlugins`、OpenCode mode map、completion message）以及 `bin/install.mjs`（`OPENCODE_MODE_DISPLAY`）。

## [Unreleased] — feat/semantic-experience-search 分支

### 新增

- **Experience 的 semantic / keyword search**（FUTURE_WORK item 2）：Orchestrator 可以根据自然语言 query 的相关性查找历史修复，例如“之前 sky130 上 WNS 问题怎么解决”，不必每次读取完整 `experiences.jsonl`。
  - **`tools/experience_search.py`**：核心库 + 独立 CLI。默认 backend 是纯 stdlib 的 **TF-IDF + cosine**，对自由文本字段（`issues_encountered`、`fixes_applied`、`notes`）进行排名；复用共享 `resolve_memory_root`、`load_records`、`filter_by_design/pdk/tool`，因此它看到的内容与 Orchestrator 实际写入一致。结果包含 `score`、`matched_terms`、`backend`、`fell_back/fallback_reason`。CLI exit code 遵循仓库约定：0=有结果、1=无匹配、2=错误/非法 memory root。
  - **可选 embedding backend，默认休眠**：`get_embedding_backend()` 在部署环境没有接入 embedding library 时返回 None，因此仓库继续保持 stdlib-only。只有 backend 可用且该 domain 记录数 ≥ `--min-records`（默认 50）时才启用，否则透明回退 keyword。Embedding 缓存在 stdlib `sqlite3` index（`<domain>/.experience_index.sqlite3`）中，按 record content hash 索引，并支持增量 `--reindex`。
  - **`plugins/infrastructure/tools/mcp-memory.py`**：独立 MCP stdio server（protocol `2024-11-05`，脚手架与 `mcp-adapter.py` 相同），暴露 `query_experiences` 工具；**`plugins/infrastructure/mcp/mcp-memory.json`**：配置模板，server name 为 `chip-design-memory`。
  - **测试**：`tests/test_experience_search.py` 覆盖 tokenizer、TF-IDF ranking、filter pre-narrowing、threshold/backend selection、sqlite cache 增量更新与 stale-hash 清理、CLI exit code；`tests/test_mcp_memory.py` 覆盖 JSON-RPC `initialize` / `tools/list` / `tools/call` smoke test 和错误码。
- **全部 15 个 Orchestrator**：在 session-start Memory block 新增可选 “semantic experience lookup” 说明；若 `query_experiences` MCP 可用则调用，否则继续只使用 `knowledge.md`。该查询只是增强，不替代 `knowledge.md`。Router（`pipeline-orchestrator`）会查询目标 producer domain；`infrastructure-orchestrator` 使用 opt-in 逻辑。
- **`memory/README.md`**：增加 “Semantic / Keyword Experience Search” 章节，说明 CLI、MCP Server/config、threshold/fallback 行为、sqlite cache + `--reindex`，以及可选 Orchestrator read path。
- **`FUTURE_WORK.md`**：item 2 标记已实现（分阶段），并说明为何放弃 sqlite-vec/Chroma/托管方案，选择 stdlib-only keyword 默认实现加可插拔 embedding hook。

## [Unreleased] — feat/agent-auto-detect 分支

### 新增

- **自动检测已安装的 AI coding Agent**：安装器不带 `--ide` 时，会检测 5 类支持的 Agent（Claude Code、OpenAI Codex、OpenCode、Gemini、GitHub Copilot），打印检测结果和每个目标的写入位置，确认后安装。如果对应 CLI 在 `PATH` 中，或者其配置目录存在（`~/.claude`、`~/.codex`、`~/.config/opencode`、`~/.gemini`），就视为已安装；Copilot 为 project-scoped，通过 `gh` / `copilot` CLI 检测。新增 `bin/detect.mjs` 作为检测规则的单一来源。
- 增加 `--yes` / `-y`（sh、mjs）和 `-Yes`（ps1），可跳过确认；在非交互 shell（CI、pipe）中也会自动继续。

### 变更

- **`bin/install.mjs` 现在原生使用 Node 安装全部 5 个 target**，不再依赖 Python。过去仅存在于 `install.sh` Python block 中的 Copilot/Gemini/OpenCode/Codex generator 已移植到 Node，生成结果在除绝对路径和 “Generated by” 注释外与原实现 byte-identical。Gemini/OpenCode 会嵌入 runtime file reference，因此使用 `npx` 时，相关 payload 会复制到持久路径 `~/.digital-chip-design-agents/payload/`，避免 npm 临时 package 目录回收后引用失效。显式 `--ide`（包括 `all`）跳过自动检测并保持原行为。
- **`install.sh` / `install.ps1`** 也增加同样的自动检测模式，当未指定 `--ide` / `-IDE` 时默认启用。它们仍需要 `python3`，因为 Claude 安装逻辑用 Python 读取 plugin version 并 merge `settings.json`；完全无 Python 的路径是 npm 安装器。
- **`README.md`**：补充自动检测、`--yes`，并明确 npm 路径现在支持全部 target。

## [Unreleased] — feat/structured-failure-handling 分支

### 新增

- **`failure_class → retry_strategy` 映射**（FUTURE_WORK item 10）：每个 failure 都映射为恢复策略 `regenerate | refine | escalate`，使 retry 行为由结构化字段决定，而不是解析 prose。权威映射定义在 `plugins/meta/skills/pipeline-orchestration/SKILL.md` 的 `### Failure Classification & Retry Strategy`，继续复用已有 10-value `failure_class` enum，不引入新 taxonomy。早期草案中的 4 类（`invalid_rtl | verification_failure | interface_mismatch | incomplete_spec`）被记录为 alias。
  - **`regenerate`**：丢弃错误 artifact，从干净状态重新运行生成 stage（`drc_lvs`、`connectivity`、`tool_error`）。
  - **`refine`**：保留 artifact，针对已识别的具体 defect 携带详细反馈重新运行（`functional`、`timing`、`power_area`、`coverage_gap`）。
  - **`escalate`**：停止并请求人工输入（`spec_gap`、`resource_limit`）；`none` 表示无需 retry。
- **`retry_strategy` history 字段（`format_version "1.5"`）**：每个 `history[]` entry 都带有由 `failure_class` 确定的 `retry_strategy`。pipeline-orchestrator 决策表增加该列，并把它作为粗粒度 pre-filter；原有 `confidence` / `suggested_next_step` 优先级仍保留，`resource_limit` 和 low confidence 始终升级。
- **可执行 escalation guidance**：当策略为 `escalate` 或达到最大迭代上限时，`pending_approval.reason` 必须包含 `failure_class` 以及用户需要提供什么才能解锁流程。
- **更新示例 fixture**：`design_state.checkpoint.json` 和 `design_state.fix_request.json` 升级到 `"1.5"`，所有 history entry 增加 `retry_strategy`；checkpoint fixture 还增加一个 `timing/refine` 的 `synth_check` loop-back 示例，用于覆盖非 none 路径。

### 变更

- **`format_version "1.5"`**：新增能力层，覆盖 `retry_strategy` 和程序化 retry branching。全部 14 个写 history 的 Orchestrator（13 个 domain + infrastructure）首次写入时升级到 1.5；包括原本从 1.3 起步的 compiler/firmware/infrastructure。旧版本继续可读，缺失 `retry_strategy` 时可从 `failure_class` 推导。
- **全部 14 个 Orchestrator + `pipeline-orchestrator.md`**：Stage Agent Output Format 与 `history[]` schema 增加 `retry_strategy`（现在 10 字段）；per-stage trace 行为规则要求正确填写该值；format_version upgrade 同步更新。
- **CI（`validate.yml`）**：`VALID_FORMAT_VERSIONS` 加入 1.5；新增 `VALID_RETRY_STRATEGY`、`RETRY_STRATEGY_MAP` 和 `check_retry_strategy`，验证 1.5 history entry 中 `retry_strategy` 是否同时与合法值及对应 `failure_class` 映射一致；两份 fixture 都会检查。
- **`memory/README.md`**：在 history 字段说明中增加 `retry_strategy`，并补充 format_version 1.4 / 1.5 层级。

## [Unreleased] — feat/infrastructure-memory 分支

### 新增

- **Infrastructure Orchestrator Memory**（FUTURE_WORK item 4）：在 `memory/infrastructure/` 下以 opt-in、environment-keyed 方式持久记录 tool version 和 setup 配置，继续使用 `knowledge.md + experiences.jsonl` 两级 Memory。
  - **Opt-in，默认关闭**：只有 `design_state.pipeline_config.track_infrastructure == true` 或调用时带 `--track-memory`，infrastructure-orchestrator 才读写 `memory/infrastructure/`。未设置时完全不做 I/O，保持过去 memory-free 行为。这符合原来暂缓的理由：infra state 强依赖具体环境，而 lockfile 仍是版本的主要 source of truth。
  - **Environment-keyed record**：每条 experience 携带环境 fingerprint（`host`、`os`、`os_version`、`arch`）以及 `environment_validation` 阶段采集的 `key_metrics.tool_versions`。价值在于跨 session 定位重复 version mismatch。Record 按环境区分，而不是设计，`design_name` 通常为 null。
  - **初始化 `memory/infrastructure/knowledge.md`**：Tier-2 summary 预置环境不匹配失败模式，例如 Verilator <5.0 不支持 `--timing`、OpenROAD nightly 与 release ABI drift、module-unload 后 python3 fallback，以及常用 flag/install note 和工具 quirks。
  - **完整接入 memory-keeper**：`infrastructure` 已注册到 `distill.py` 的 `VALID_DOMAINS`、`METRIC_FIELDS`（`tools_detected`、`tools_missing`、`wrappers_deployed`、`mcp_servers_configured`）以及 memory-keeper Skill Domains 表，可通过 `/chip-design-infrastructure:memory-keeper --domain infrastructure` 将环境经验蒸馏到 `knowledge.md`。

### 变更

- **`memory/README.md`**：Directory Layout 新增 `infrastructure/`；Domain key_metrics 表增加 infrastructure 行；新增 “Infrastructure memory (opt-in, environment-keyed)” 章节，说明激活条件和按环境分键的 record。
- **`infrastructure-orchestrator.md`**：新增 Behaviour Rule 8 和 “Infrastructure Memory” 章节，定义 activation gate、session-start read、`environment_validation` 后 upsert，以及 environment-keyed schema。

## [Unreleased] — feat/central-constraint-handling 分支

### 新增

- **从 `design_state.constraints` 动态加载 constraint**（FUTURE_WORK item 8）：`design_state.constraints` 现在是设计约束的唯一可信来源，包括 clock target、area/power budget、WNS/TNS、utilization、IR-drop、leakage、coverage、fault coverage、HLS II/latency 和 FPGA resource limit。11 个 constraint-bearing domain Skill 都改为引用具体 key，而不是硬编码 literal；原 literal 只作为 backward-compatible 默认值保留。
- **完整 `constraints` schema（`format_version "1.4"`）**：权威 schema 统一定义于 `plugins/meta/skills/pipeline-orchestration/SKILL.md` 的 `### Constraints Schema`，分类包括 `clock`、`pvt_corners[]`、`timing`、`area`、`power`、`coverage`、`dft`、`hls`、`fpga`。所有非 null 默认值都与过去 Skill 中的 literal 一致。
- **Stage-entry constraint validation**：每个需要 constraint 的 Orchestrator 在第一个消费约束的 stage 读取 `design_state.constraints`；若其 required subset 中某 key 缺失或为 null，则原子设置 `pending_approval.type="constraint_gap"` 并停止。Optional constraint 缺失时采用 schema default，同时写 WARN history。Required subset：`clock.clk_mhz`（architecture、rtl-design、synthesis、sta、pd、soc、fpga）；`area.area_um2 + power.power_mw`（architecture、synthesis、pd）；`pvt_corners` 至少一项 V/T 非 null（sta、pd）；HLS 至少 `hls.target_ii` / `hls.target_latency_cycles` 之一非 null。
- **`pending_approval.type:"constraint_gap"`**：扩展现有 pending_approval，用于 constraint 缺失；pipeline-orchestrator 会输出类型专属提示，让用户补齐 constraint 并清空 pending_approval 后继续。
- **`constraint_ref` tagging**：`history[]` entry 会标出 QoR 判断使用的 dot-path key，例如 `timing.wns_ns_target`、`power.power_mw`、`clock.clk_mhz`，使每次 stage decision 都能追溯到对应 constraint。
- **更新 `design_state.checkpoint.json` 示例**：升级到 format_version 1.4，为 `example_dsp_core` 加入完整 constraints（500 MHz、28nm），并在 `perf_modelling`、`power_area_estimation`、`module_planning`、`synth_check` history 中使用真实 dot-path `constraint_ref`。

### 变更

- **`format_version "1.4"`**：新增 constraint object、stage-entry validation 和 `pending_approval.type:"constraint_gap"`。全部 15 个 Orchestrator 首次写入时升级到 1.4；旧版仍兼容：没有 constraints 时使用 optional default，缺失 pending_approval.type 时视为 escalation。
- **Architecture Orchestrator**：constraints stub 从扁平 `{clk_mhz, area_um2, power_mw}` 扩展为完整 nested schema；新增 Behaviour Rule 8（`spec_analysis` 阶段填充 constraint）和 Rule 9（required key 仍为 null 时 hard-fail）。
- **全部 11 个 domain Skill**：QoR Metric 和使用约束的 Domain Rule 改为引用 `design_state.constraints.<key>`，并保留旧 literal 作为 documented default；每个文件新增 `## Constraint Validation`，列出 required/optional key。
- **`formal`、`dft` Orchestrator**：Design State Read 增加 `constraints`。
- **CI**：无需新增 schema-validation 逻辑，修改对象均已由现有 Markdown/JSON 检查覆盖。

---

## [Unreleased] — feat/approval-gates-traceability 分支

### 新增

- **Approval checkpoint**（FUTURE_WORK item 11A）：任何 Orchestrator 的 sign-off 边界都可配置主动 human-in-the-loop gate，由 `design_state.json` 中 `pipeline_config.checkpoints[]` 控制。默认建议位置为 `arch_signoff`、`rtl_signoff` 和 PD tape-out 的 `signoff`。触发 checkpoint 时，Orchestrator 设置 `pending_approval {type:"checkpoint", stage, agent}` 并停止，不完成 sign-off；用户把 stage 加入 `approved_checkpoints[]` 后重新调用即可恢复。`checkpoints:[]` 表示完全自动，保持 backward compatible。
- **Per-stage execution trace**（FUTURE_WORK item 11B）：全部 15 个 Orchestrator 现在每完成一个 stage（PASS/FAIL/WARN）就向 `history[]` 写一条记录，而不只是每次 run 结束时写一条 terminal record。这样无需重放完整 Agent 对话也可审计过程。Entry shape 当时仍为 9 字段。
- **`format_version "1.3"`**：覆盖 checkpoint + per-stage trace 的能力层。全部 Orchestrator 首次写入时升级到 1.3，旧文件仍可读。
- **`design_state.checkpoint.json` fixture**：新增 golden example，展示 `pending_approval.type:"checkpoint"` 的 pause、`approved_checkpoints[]` 和 architecture → RTL 的 per-stage history。

### 变更

- **`pending_approval` schema 扩展**：增加 `type`（`checkpoint | escalation`）、`stage`、`agent`。Backward compatible：旧 reader 对缺失 type 可按 escalation 处理。
- **所有权规则更新**：domain Orchestrator 现在可以在自己 sign-off stage 设置 `type:"checkpoint"`；`type:"escalation"` 仍只由 pipeline-orchestrator 设置。
- **`pipeline_config` 扩展**：新增 `checkpoints` 数组，默认 `[]`。
- **新增 `approved_checkpoints[]`**：top-level 字段，每项 `{"stage","approved_at","approved_by"}`，由用户或执行显式批准指令的 Orchestrator 写入。
- **全部 15 个 Orchestrator 更新**：Design State Read 提取 `pipeline_config` 和 `approved_checkpoints`；Write 升级 `format_version` 到 1.3；增加 per-stage trace + checkpoint gate 两条 Behaviour Rule。
- **CI 扩展**：`VALID_FORMAT_VERSIONS` 增加 1.3；新增 inline Python 检查 `pipeline_config.checkpoints`、`approved_checkpoints`、`pending_approval.type`；两份 fixture 每个 PR 都验证。
- **`memory/README.md`**：补充 1.3 层级、checkpoints、approved_checkpoints 和扩展的 pending_approval 文档。

---

## [Unreleased] — feat/rtl-verify-feedback-loop 分支

### 新增

- **Verification↔RTL 闭环反馈**（FUTURE_WORK item 6）：当发现 DUT bug 或 formal CEX 时，verification/formal Orchestrator 不再只输出 prose 并暂停，而是向 `design_state.json` 写结构化 `fix_request`。新增 `chip-design-meta` 插件中的 `pipeline-orchestrator` 会检测 open fix_request，dispatch RTL Orchestrator 修复，然后重新运行原始 verification/formal，最多跨域迭代 3 次，仍不收敛则通过 `pending_approval` 升级。
- **`fix_request` schema**（format_version 1.1）：`design_state.json` 新增 top-level `fix_requests[]` 和 `cross_domain_iteration_count`。前者保存 id、failure_class、suspected_rtl、waveform_path、status lifecycle 等结构化 bug handoff；后者由 pipeline-orchestrator 强制限制迭代次数。完全 backward-compatible，旧 reader 对缺失 key 按 null/0 处理。
- **`chip-design-meta` plugin**：Marketplace 第 15 个插件，包含 pipeline-orchestrator Agent、pipeline-orchestration Skill（存放权威 fix_request schema 与 dispatch pattern），以及 `memory/meta/` 持久化 Memory。
- **Formal Orchestrator fix_request 支持**：`formal-orchestrator.md` 在 property CEX 时写 `failure_class=formal_cex` 的 fix_request，包含 CEX trace path，与 verification 使用相同协议。V1 中两者都路由到 RTL Orchestrator 修复。

### 变更

- **Plugin count**：14 → 15；`validate.yml` CI assert 和 `ides/copilot/applyto-map.json` domain count 同步更新。
- **`verification-orchestrator.md`**：`directed_tests DUT bug found` loop-back 和 Behaviour Rule 4 改为写结构化 fix_request，并以 `decision=escalate` 退出；Design State Read 支持 re-invocation context。
- **`rtl-design-orchestrator.md`**：Design State Read 支持检测并 claim open fix_request；Behaviour Rule 6 定义关闭协议。
- **`functional-verification/SKILL.md`**：Domain Rule 7 从 “暂停并等待确认” 改为 “写 fix_request 并结束，由 pipeline-orchestrator dispatch”。
- **`memory/README.md`**：补充 fix_requests、cross_domain_iteration_count 和 format_version 1.1。
- **Divergence detection 限定当前 session**：pipeline-orchestrator 仅把与当前 `pipeline_session_id` 相同且 status=fixed 的历史请求用于 recurrence 判断，避免 refactor 后未来 session 再出现同类 bug 时误报 divergence。
- **Sign-off 后归档**：pipeline-orchestrator success branch 将当前 session 已解决的 fix_request 移到 `design_state.archive_fix_requests[]`，并重置 session state，避免长项目中数组无限增长。
- **迭代上限可配置**：`pipeline_config.max_cross_domain_iterations` 取代写死的 3，缺失时默认 3，可按 design 调整，无需改 Agent 文件。
- **LEC unmatched-points 闭环推迟到 V2**：`formal-orchestrator.md` 的 `lec_run: unmatched points` 在 V1 中不进入 fix_request，因为正确 consumer 应是 `synthesis-orchestrator`，而不是 RTL。已记录到 Pipeline Skill 的 V2 extension point。
- **删除多余 per-entry `iteration_count`**（S1）：每次 re-failure 实际会新建一条 request，所以该字段几乎总为 0 或 1。统一使用 top-level `cross_domain_iteration_count`。已从 meta Skill、两个 producer schema、RTL Behaviour Rule/Write step、fixture、CI required fields 中删除。
- **初始化 `memory/meta/experiences.jsonl`**（S7）：加入两条示例，一条 converged（MAC unit 单轮修复），一条 escalated（AXI DMA 3 轮仍失败）。
- **Marketplace version 和 README 对齐**：metadata.version → 1.3.0；README header 更新为 “15 plugins · 16 skill files”；Available Plugins 增加 `chip-design-meta`。

---

## [Unreleased] — agent-scope-review 分支

### 新增

- 所有 13 个 domain `SKILL.md` 增加 **`## Pre-run Context`**：无论从哪个入口调用，都先读取 `knowledge.md` 与 `run_state.md`，不再只在 Orchestrator session start 读取。
- **Run-state tracking**：13 个 domain Skill 和 PD Orchestrator 在任何工具调用前第一步写 `memory/<domain>/run_state.md`；每个 stage 后更新 `last_stage`，供 wakeup-loop prompt 正确恢复。
- **Per-stage experience write**：PD Orchestrator 与全部 domain Skill 现在每个 stage 后就 upsert `experiences.jsonl`，不再只在 session end 写；即使中断，partial run 也能保存。
- **可选 claude-mem integration**：13 个 domain Skill 与 memory-keeper Skill 在 `mcp__plugin_ecc_memory__add_observations` 可用时把 applied fix 写为 observation；工具缺失时静默跳过，JSONL 仍是 canonical record。
- **Architecture Skill 增加 clock-gating opportunity 分析**（`power_area_estimation`）：按 activity factor α 分类每个 clock domain，生成 `clock_power_budget` handoff 表（domain → frequency、α、estimated clock power、gating class），并加入 QoR gate：可 gating domain 中至少 70% register bit 需要被覆盖。
- **RTL Design Skill 增加 power intent / ICG insertion 规则**（`rtl_coding`）：RTL Agent 读取 architecture handoff 中的 `clock_power_budget`，对 high/moderate gating domain 插入 ICG，并要求 `clock_gating_coverage ≥ 60%`。
- **Architecture → RTL handoff contract** 在 `docs/MASTER_INDEX.md` 中增加 `clock_power_budget` artifact。
- `memory/README.md` 补充 run_state、per-stage write、`run_id` schema 和可选 claude-mem index pattern。
- `docs/Architecture_Evaluation_Flow.md`、`docs/RTL_Design_Flow.md` 同步新增 clock-gating/ICG 内容。
- OpenROAD MCP config（`mcp-openroad.json`）注释明确标出安装时需要替换的两个 placeholder。

---

## [1.2.0] — 2026-04-14

### 新增

- 支持多个 IDE：GitHub Copilot、Google Gemini Code Assist、OpenCode
- `ides/copilot/`：Copilot workspace instruction 和按 domain 的 file-glob map（`applyto-map.json`）
- `ides/gemini/`：生成 `GEMINI.md` 时注入的 preamble header
- `ides/opencode/`：包含全部 13 个 chip-design mode 的基础 OpenCode config template
- `install.sh --ide <copilot|gemini|opencode|all>`：把 IDE 专用配置部署到目标项目
- Windows PowerShell 等效参数：`install.ps1 -IDE <copilot|gemini|opencode|all>`
- CI/CD 扩展：每个 PR 都 lint IDE config file

### 变更

- Agent 和 Skill 增加明确的 EDA tool 使用说明
- 删除 AgentShield CI step，因为仓库中没有 `.claude` 目录

---

## [1.1.1] — 2026-04-13

### 新增

- AgentShield CI check：每个 PR 验证 Claude Agent 文件

### 修复

- 修复 CodeRabbit review 后发现的 AgentShield integration 问题

---

## [1.1.0] — 2026-04-13

### 新增

- 全平台安装脚本：`install.sh`（macOS / Linux / Git Bash）和 `install.ps1`（Windows PowerShell）
- 在 `marketplace.json` 中设置 `strict:true`，强制精确 plugin path

### 变更

- **不兼容目录重构**：13 个 Agent/Skill 从共享扁平目录拆分为每个 plugin 独立目录：`plugins/<domain>/agents/`、`plugins/<domain>/skills/`，消除多个 plugin 并发加载时的文件系统竞争问题
- 每个 plugin 增加独立 `.claude-plugin/plugin.json`
- CI/CD 适配新目录结构
- README 更新，删除过去关于 racing issue 的限制说明

### 修复

- Agent 与 Skill invocation chain 增加递归保护
- Agent 执行前会读取 Skill；Skill 收到完整流程任务时先启动对应 Orchestrator

---

## [1.0.3] — 2026-04-12

### 修复

- Marketplace recursive-directory bug：加强 schema 检查，强制 path 类型正确，避免 Marketplace registry 递归解析到子目录

---

## [1.0.2] — 2026-04-12

### 修复

- 修复 Validate CI 和 `plugin.json` 格式问题（v1.0.1 的 follow-up）

---

## [1.0.1] — 2026-04-12

### 修复

- 初始 setup 中的 Validate CI pipeline failure
- CI linter 报告的 `plugin.json` 格式错误
- CodeRabbit 报告的少量 environment file 修正
- 删除 repo root 中遗留的 `.claude` settings file

---

## [1.0.0] — 2026-04-12 — 首次发布

### 新增

- 13 个 Claude Code Marketplace plugin，覆盖完整数字芯片设计 pipeline
- 13 个带 YAML frontmatter、分阶段 domain rule、QoR metric 和 fix guidance 的 Skill
- 13 个带 stage sequence、loop-back rule 和 sign-off criteria 的 Orchestrator Agent Markdown
- `.claude-plugin/plugin.json`：Claude Code plugin manifest
- `.claude-plugin/marketplace.json`：全部 13 个 plugin 的 Marketplace registry
- GitHub Actions CI validation workflow：验证每个 PR
- 自动 release workflow：生成 tar.gz archive

### v1.0.0 覆盖领域

Architecture Evaluation · RTL Design（SystemVerilog）· Functional Verification（UVM）·
Formal Verification（FPV/LEC）· Logic Synthesis · Design for Test（DFT）·
Static Timing Analysis（STA）· High-Level Synthesis（HLS）· Physical Design ·
SoC IP Integration · Compiler Toolchain（LLVM）· Embedded Firmware · FPGA Emulation
