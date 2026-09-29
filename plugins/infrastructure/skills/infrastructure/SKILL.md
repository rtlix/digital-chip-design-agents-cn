---
name: infrastructure
description: >
  数字芯片设计环境的 EDA 工具检测、wrapper 部署和 MCP 配置。
  适用于配置新工作站、在领域流程开始前验证工具可用性，
  或为缺失工具生成带 TCL modulefile 的独立安装脚本。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill: Infrastructure Setup（基础设施配置）

## Invocation
- **用户直接提出环境配置任务**：立即启动
  `digital-chip-design-agents:infrastructure-orchestrator`，传入完整请求与上下文，不直接执行 stage。
- **由 infrastructure-orchestrator 中途调用**：不要再次启动 Agent；本文件作为只读规则库，
  返回所需 stage rule、sign-off criteria 或 loop-back guidance。

在活跃 Orchestrator 内再次启动自身会造成递归委派，必须禁止。

## Purpose
检测开源/商业 EDA 工具，为缺失工具生成安装脚本，部署输出过滤 wrapper，
把原始 10,000–50,000 行日志压缩为结构化 JSON，配置 MCP server template，
并在任何下游 domain Orchestrator 开始前验证完整环境。

---

## Supported EDA Tools

### Open-Source
- **Verilator** (`verilator`) — RTL 仿真/lint
- **Slang** (`slang`) — SystemVerilog compiler/language server
- **Surelog** (`surelog`) — SystemVerilog preprocess/parser
- **sv2v** (`sv2v`) — SystemVerilog→Verilog
- **Icarus Verilog** (`iverilog`) — Verilog simulator
- **Yosys** (`yosys`) — 开源综合
- **ABC** (`abc`) — logic synthesis/verification
- **OpenROAD** (`openroad`) — RTL-to-GDS
- **LibreLane / OpenLane2** (`openlane`) — 开源 ASIC flow
- **KLayout** (`klayout`) — GDS/OASIS viewer + DRC
- **OpenSTA** (`sta`) — gate-level STA
- **SymbiYosys** (`sby`) — formal verification
- **gem5** (`gem5`) — full-system microarchitecture simulation
- **Bambu HLS** (`bambu-hls`) — C/C++ HLS
- **nextpnr** (`nextpnr`) — FPGA P&R
- **openFPGALoader** (`openFPGALoader`) — FPGA programming
- **cocotb** — Python RTL co-sim
- **LLVM** (`llvm-config`)
- **GCC** (`gcc`)
- **OpenOCD** (`openocd`)
- **xschem** (`xschem`)
- **GTKWave** (`gtkwave`)
- **uv** (`uv`) — Python package/project manager，cocotb 安装使用

### Proprietary（只检测，绝不自动安装）
- Synopsys VCS (`vcs`)
- Cadence Xcelium (`xrun`, alt: `xmsim`)
- Synopsys Design Compiler (`dc_shell`, alt: `dc_shell-t`)
- Cadence Innovus (`innovus`)
- Mentor QuestaSim (`vsim`, alt: `questa`, `questasim`)
- Synopsys PrimeTime (`pt_shell`, alt: `pt_shell64`)
- Synopsys Formality (`formality`, alt: `fm_shell`)

---

## MCP Architecture — Two Tiers

### Tier 1: Batch MCP servers（短、单次运行）
适用于几秒到几分钟的工具。每次调用启动 wrapper、捕获 compact JSON 后返回。

| MCP config | Tool | 典型时长 |
|---|---|---|
| `mcp-yosys.json` | Yosys synthesis | 秒–分钟 |
| `mcp-openroad.json` | 单个 OpenROAD stage | 分钟 |
| `mcp-opensta.json` | OpenSTA batch report | 秒–分钟 |
| `mcp-klayout.json` | KLayout DRC/LVS | 分钟 |
| `mcp-verilator.json` | Verilator lint/sim | 秒–分钟 |
| `mcp-bambu.json` | Bambu HLS | 分钟 |
| `mcp-gem5.json` | gem5 short benchmark | 分钟，设置 TOOL_TIMEOUT_S |
| `mcp-symbiflow.json` | SymbiYosys bounded proof | 分钟–小时 |

Adapter：`plugins/infrastructure/tools/mcp-adapter.py`。

### Tier 2: Interactive session MCP servers（有状态）
适用于 Agent 对已加载 design 反复查询，例如 ECO timing loop。进程跨调用保持，不重复 load design。

| MCP config | Tool | 暴露工具 |
|---|---|---|
| `mcp-openroad-session.json` | OpenROAD Tcl session | `load_design`, `query_timing`, `query_drc`, `get_design_area`, `get_power`, `run_tcl`, `close_design` |
| `mcp-opensta-session.json` | OpenSTA Tcl session | `load_design`, `report_timing`, `report_slack_histogram`, `check_timing`, `run_tcl`, `close_design` |

Adapter：`plugins/infrastructure/tools/mcp-session-adapter.py`。

### Full-flow tools — 不使用 MCP
以下工具常运行 30 分钟到数小时，并在磁盘生成结构化文件。Agent 应通过 Bash 启动，再直接读取结果文件。

| Tool | Launch command | 读取文件 |
|---|---|---|
| LibreLane / OpenLane 2 | `openlane config.json` | `runs/<design>/<tag>/metrics.json` |
| ORFS / OpenROAD Flow Scripts | `make DESIGN_CONFIG=... finish` | `reports/<platform>/<design>/metrics.json` |
| gem5 full-system | `gem5 config.py ...` | `m5out/stats.txt`, `m5out/simout` |

### Execution Hierarchy
1. Tier 2 session MCP：工具支持 session 且 design 已加载
2. Tier 1 batch MCP：配置了 batch MCP
3. Wrapper script：MCP 未配置时，返回 compact JSON
4. Direct execution：最后手段，raw log 很耗 context

下游 Agent 必须先检查 `.claude/settings.json` 是否启用相关 MCP，再 fallback。

---

## Stage: tool_discovery

### Domain Rules
1. 对每个开源工具执行 `which <command>` 和 `<command> --version`（或 `-version`）。
2. **Python interpreter detection** 在任何 Python package 检查前只执行一次，first match wins。

   **Step A — Module system probe（优先于 PATH）**
   a. 检查 `$MODULESHOME` 或 PATH 中 `modulecmd`。
   b. 若存在 module system，运行 `module avail 2>&1`，大小写不敏感搜索 `python/python3`。
   c. 若有 Python module，选最新版本，`module load <python-module>` 后运行 `which python3` 得到 `PYTHON_EXEC`；
      设置 `python_env.type="module"`，记录 `module_name`，并在整个 Orchestrator run 中保持 module 已加载。
   d. 没有 module system/Python module 时进入 Step B。

   **Step B — PATH fallback**
   e. `which python3`，保存为 `PYTHON_EXEC`。
   f. 找不到则在 `tool-status.json` 把 python3 记为 `MISSING` 并立即 FAIL；所有 wrapper/Python package 都依赖它。
   g. 分类：
      - `system`：`PYTHON_EXEC == /usr/bin/python3`
      - `custom`：其他路径（pyenv/conda/venv/custom prefix）

   **Step C — Finalize**
   h. `PYTHON_BIN_DIR=$(dirname "$PYTHON_EXEC")`。
   i. `tool-status.json` 顶层保存：
   ```json
   {"python_env":{"exec":"<absolute path>","type":"module | system | custom","bin_dir":"<absolute dir>","module_name":"<module or null>"}}
   ```
   j. 保存 `"$PYTHON_EXEC" --version`，并在 `tools[]` 增加普通 python3 FOUND 条目，便于后续 module_discovery 升级状态。

3. **Python package 特例**
   - **cocotb**：custom/module Python 时先检查 `"$PYTHON_BIN_DIR/cocotb-config" --version`，失败再检查 PATH；system Python 只检查 PATH。
   - **openlane**：`"$PYTHON_EXEC" -m pip show openlane`，成功且包含 `Name: openlane` 才记 FOUND。
   - **uv**：custom/module 时优先 `"$PYTHON_BIN_DIR/uv" --version`，再 fallback PATH；system 只查 PATH。
4. 商业工具仅 `which <primary-executable>`；找到记 `PROPRIETARY_ONLY`，否则 `MISSING`；绝不安装。
5. 每个工具状态只能是 `FOUND/MISSING/PROPRIETARY_ONLY`。
6. 对 FOUND 保存精确 version string。
7. 本 stage 不执行安装。
8. 进入下一 stage 前必须写 `tool-status.json`。

### QoR Metrics to Evaluate
- `tools_detected`：FOUND 数，功能性开源 flow 目标 ≥10
- `tools_missing`：缺失开源工具数
- `proprietary_found`：PATH 中检测到的商业工具数

### Output Required
- `tool-status.json`，顶层含 `python_env` 和 `tools[]`
- Module availability 相关状态在下一 stage 增加

---

## Stage: module_discovery

### Domain Rules

#### Module system detection
1. Classic Environment Modules（TCL）：`$MODULESHOME` 或 PATH 中 `modulecmd`
2. 都没有：设置 `module_system:"none"`，输出 WARN，写空 `module-status.json`，继续 `tool_installation`

#### Module listing
- Classic：`module avail 2>&1`
- listing command 非 0：WARN、记录错误，但继续

#### Module-to-tool mapping
保持以下机器匹配模式不变：

| Tool command | Module name pattern |
|---|---|
| `vcs` | `vcs`, `synopsys-vcs`, `synopsys/vcs` |
| `xrun` | `xcelium`, `cadence-xcelium`, `cadence/xcelium` |
| `dc_shell` | `design-compiler`, `synopsys/dc`, `dc_shell` |
| `innovus` | `innovus`, `cadence/innovus`, `cadence-innovus` |
| `vsim` | `questa`, `questasim`, `mentor/questa` |
| `pt_shell` | `primetime`, `synopsys/pt`, `pt_shell` |
| `formality` | `formality`, `synopsys/formality` |
| `verilator` | `verilator` |
| `yosys` | `yosys` |
| `openroad` | `openroad` |
| `klayout` | `klayout` |
| `iverilog` | `icarus`, `iverilog` |
| `sta` | `opensta` |
| `gcc` | `gcc` |
| `llvm-config` | `llvm` |
| `xschem` | `xschem` |
| `gtkwave` | `gtkwave` |
| `uv` | `uv` |
| `python3` | `python`, `python3` |
| `slang` | `slang` |
| `surelog` | `surelog` |
| `sv2v` | `sv2v` |
| `sby` | `symbiyosys`, `sby`, `yosyshq/sby` |
| `bambu-hls` | `bambu`, `bambu-hls`, `panda-bambu` |
| `nextpnr` | `nextpnr` |
| `openFPGALoader` | `openfpgaloader` |
| `openocd` | `openocd` |

#### Rules
1. 检测 module system。
2. 运行对应 listing command。
3. 每条 module entry 按上表大小写不敏感匹配。
4. 收集所有 available version。
5. 进入下一 stage 前写 `module-status.json`。
6. PATH 已 FOUND 且 module 也有：改为 `FOUND_PREFER_MODULE`，增加 `module_names/versions_available`，写入 `load-modules.sh`；module 优先于 PATH version。
7. PATH MISSING 但 module 可用：改为 `MISSING_LOAD_MODULE`。
8. 为所有 `FOUND_PREFER_MODULE/MISSING_LOAD_MODULE` 生成 `load-modules.sh`，默认最新版本并把备选版本写注释。
9. 不自动 source 脚本；提示用户 review/source 后重新运行。

### QoR Metrics to Evaluate
- `module_system_detected`
- `tools_found_via_modules`

### Output Required
- `module-status.json`
- 更新后的 `tool-status.json`
- 必要时的 `load-modules.sh`

机器 schema 与原版保持：
```json
{"module_system":"tclmod | none","module_system_version":"","tools_via_modules":[{"tool":"<command>","module_names":[],"versions_available":[]}]}
```

---

## Stage: tool_installation

### Domain Rules
1. **绝不自动执行安装**，只生成 per-tool install script。
2. python3 缺失立即 FAIL/escalate。
3. 只为 `MISSING` 工具生成 `install-<toolname>.sh`；FOUND、module-available、commercial 均跳过。
4. 每个脚本按下述固定结构。
5. 根据 OS/package manager 使用 Package Mapping Table。
6. Python package（openlane/cocotb/uv）使用 `tool-status.json` 的 `python_env.exec/bin_dir`；禁止在 custom/module Python 情况使用裸 `pip install`。
7. Commercial tool 不生成安装脚本，仅在 sign-off summary 备注。
8. Modulefile 永远用 classic TCL、无扩展名；即使无 module system 也生成，并发 WARN。
9. 每个脚本结尾说明如何把 `$EDA_MODULEFILES_ROOT` 注册进 `$MODULEPATH`。
10. 所有脚本写入 `install-missing-tools/`；没有 MISSING 时不要创建目录。

### Common Issues & Fixes
| Issue | Fix |
|---|---|
| python3 不存在 | 立即 escalate，wrapper 全依赖 Python |
| OpenROAD 需要源码编译 | 参考 OpenROAD upstream |
| Bambu HLS 仅 Linux | macOS/Windows 报 WARN |

### Install Directory Layout
```text
$EDA_TOOLS_ROOT/                         # 默认 /tools
  <toolname>/<version>/
$EDA_MODULEFILES_ROOT/                   # 默认 /tools/toolmgr/env/modulefiles
  <toolname>/<version>
```

### Per-Tool Script Structure
保留原 shell 模板和变量名：
`TOOL_NAME`、`TOOL_VERSION`、`EDA_TOOLS_ROOT`、`EDA_MODULEFILES_ROOT`、`INSTALL_DIR`。
脚本安装后生成 TCL modulefile，至少设置 `PATH`、`LD_LIBRARY_PATH`，按需增加
`MANPATH/PKG_CONFIG_PATH/PYTHONPATH`。工具特有变量：
Verilator→`VERILATOR_ROOT`，Yosys→`YOSYS_DATDIR`，LLVM→`LLVM_DIR`，cocotb→`COCOTB_SHARE_DIR`。

### Package Name Mapping Table
安装命令/包名属于机器内容，保持原命令：
- verilator/slang/surelog/sv2v/iverilog/yosys/abc/openroad/openlane/klayout/OpenSTA/SymbiYosys/gem5/Bambu/nextpnr/openFPGALoader/cocotb/LLVM/GCC/OpenOCD/xschem/GTKWave/uv
- build-from-source 项继续指向原 upstream
- Python package 使用 `<PYTHON_EXEC> -m pip install ...`
- uv 优先 standalone installer，custom/module Python 可 pip fallback

### Output Required
- 每个 MISSING 工具一个 `install-<toolname>.sh`，写入 `install-missing-tools/`

---

## Stage: wrapper_deployment

### Domain Rules
1. 部署全部 8 个 wrapper 到 `plugins/infrastructure/tools/`。
2. 全部 `chmod +x`；权限失败则 FAIL，并给出 `sudo chmod +x ...` 指引。
3. 无论 tool exit code 如何，wrapper 都必须输出 schema 合法 JSON。
4. 部署后用 `--version/--help` smoke test；工具缺失可以容忍。版本命令本身没有设计结果，因此正确结果是 `WARN + verified:false`。
5. 不得吞掉原始 exit code。
6. 没有可识别结果时绝不能报 PASS；即使 exit 0 也应 WARN + verified:false。

### Wrapper JSON Output Schema
```json
{
  "tool":"<tool-name>",
  "exit_code":0,
  "status":"PASS|FAIL|WARN",
  "verified":true,
  "summary":{},
  "errors":[],
  "warnings":[],
  "raw_log":"/tmp/<tool>-XXXXXX.log"
}
```

判定优先级：
1. 非零 exit、error/fail marker、tool not found → FAIL
2. exit 0 但没有可识别 result → WARN + `verified:false`
3. 有 result 且有 warning → WARN
4. 有 result 且无 warning → PASS

`verified:true` 只代表状态建立在实际解析结果或明确失败上；
`verified:false` 的结果**绝不是 PASS**，必须读 raw_log/tool report 后才能决定 stage。
找不到的 metric 用 null/省略，绝不能伪造 0。

### QoR Metrics to Evaluate
- `wrappers_deployed`：可执行 wrapper 数，目标 8

### Output Required
- 8 个 executable wrapper

---

## Stage: mcp_configuration

### Domain Rules
1. 生成全部 10 个 MCP config（8 batch + 2 session）。
2. Batch config 使用 `python3 + mcp-adapter.py`，不要直接把 wrapper 当 MCP server。
3. Session config 使用 `mcp-session-adapter.py --tool openroad/opensta`。
4. 运行时通过 realpath/pwd 解析绝对路径，不得保留 `/absolute/path/to/` placeholder。
5. 打印每个 snippet，并明确提示粘贴到 `.claude/settings.json`。
6. snippet 文件写到 `plugins/infrastructure/mcp/`。
7. 不自动修改用户的 `.claude/settings.json`。

### QoR Metrics to Evaluate
- `mcp_servers_configured`：目标 10

### Output Required
Batch：`mcp-yosys/openroad/opensta/klayout/verilator/bambu/gem5/symbiflow.json`
Session：`mcp-openroad-session.json`、`mcp-opensta-session.json`
以及 `mcp-adapter.py`、`mcp-session-adapter.py`。

---

## Stage: environment_validation

### Domain Rules
1. 首先验证 `python_env`：
   - type=module：`which python3` 确认 module 仍 active，否则立即 FAIL 并提示 source `load-modules.sh`
   - type=custom/system：确认当前 python3 path 与 `python_env.exec` 一致，不一致 WARN
2. 按 tool_discovery 相同的 Python-aware 方法重新检测 openlane/cocotb/uv，并对照 `tool-manifest.json`。
3. 确认 8 个 wrapper 存在且 executable。
4. 确认 10 个 MCP snippet 以及两个 adapter 存在。
5. Yosys、Verilator、OpenROAD、OpenSTA 任一仍为 `MISSING` 时 FAIL。
6. `MISSING_LOAD_MODULE` 的工具发 WARN，并提示 source `load-modules.sh` 后重跑。
7. Critical tool 为 `MISSING_LOAD_MODULE` 时 `suggested_next_step:"escalate"`。
8. 打印 tools detected / tools via modules / wrappers / MCP summary。

### Sign-off Checklist
- [ ] `tool-status.json` 已写，包含 `python_env`
- [ ] `module-status.json` 已写
- [ ] 所有 MISSING tool 都有 install script
- [ ] 有 module 工具时生成 `load-modules.sh`
- [ ] `tool-manifest.json` 已写
- [ ] 8 wrapper 可执行
- [ ] 两个 MCP adapter 存在
- [ ] 10 MCP config 均使用解析后的绝对路径
- [ ] Critical-path tool 不得是 MISSING/MISSING_LOAD_MODULE

### Output Required
- Environment validation report
- 最终 `tool-manifest.json`
