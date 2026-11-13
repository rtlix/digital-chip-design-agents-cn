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
- **Magic** (`magic`) — layout editor、DRC 与 extraction
- **Netgen** (`netgen`) — LVS netlist comparison
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

#### Roles and dialects (open-source)

`role` 将功能相同的工具归为一组；`dialect` 表示工具接受的命令行选项及源语言词汇。`role` 相同而 `dialect` 不同的工具**不能互换**，为其中一个工具构造的命令行对另一个工具并不有效。

| Tool command | `role` | `dialect` |
|---|---|---|
| `verilator` | `rtl_simulator` | `verilator` |
| `iverilog` | `rtl_simulator` | `icarus` |
| `yosys` | `synthesis` | `yosys` |
| `openroad` | `physical_design` | `openroad` |
| `openlane` | `physical_design` | `openlane` |
| `sta` | `sta` | `opensta` |
| `sby` | `formal` | `symbiyosys` |
| `klayout` | `drc_lvs` | `klayout` |
| `magic` | `drc_lvs` | `magic` |
| `netgen` | `drc_lvs` | `netgen` |
| `bambu-hls` | `hls` | `bambu` |
| `gem5` | `arch_simulator` | `gem5` |
| `nextpnr` | `fpga_pnr` | `nextpnr` |

其他开源工具——`slang`、`surelog`、`sv2v`、`abc`、`openFPGALoader`、`cocotb`、`llvm-config`、`gcc`、`openocd`、`xschem`、`gtkwave`、`uv`、`python3`——在此没有同功能的其他工具，记录为 `"role": null, "dialect": null`。不要编造角色填充字段：`null` 不会产生虚假的冲突。

### Proprietary (detect only — never install)（商业工具：只检测，绝不安装）

| 工具 | Command (alt) | `role` | `dialect` | Version probe（无需占用许可证的版本探测） |
|---|---|---|---|---|
| Synopsys VCS | `vcs` | `rtl_simulator` | `synopsys` | `vcs -ID` — parse the `Compiler version` line only |
| Cadence Xcelium | `xrun` (`xmsim`) | `rtl_simulator` | `cadence` | `xrun -version` — parse the `TOOL:<tab>xrun(64)<tab><version>` line |
| Mentor QuestaSim | `vsim` (`questa`, `questasim`, `vlog`, `vcom`) | `rtl_simulator` | `siemens` | none — UNVERIFIED |
| Synopsys URG | `urg` | `coverage_report` | `synopsys` | `urg -version` — parse the `URG Version` line |
| Cadence IMC | `imc` | `coverage_report` | `cadence` | none — UNVERIFIED |
| Synopsys Design Compiler | `dc_shell` (`dc_shell-t`) | `synthesis` | `synopsys` | `dc_shell -version` — parse the `dc_shell version` line |
| Cadence Genus | `genus` | `synthesis` | `cadence` | `genus -version` — parse the `Program Name:` line |
| Synopsys Fusion Compiler | `fc_shell` | `synthesis` | `synopsys` | none — UNVERIFIED |
| Synopsys Library Compiler | `lc_shell` | `library_prep` | `synopsys` | `lc_shell -version` — parse the `lc_shell version` line |
| Cadence Innovus | `innovus` | `physical_design` | `cadence` | `innovus -version` — parse the `@(#)CDS: Innovus v` line |
| Synopsys IC Compiler 2 | `icc2_shell` | `physical_design` | `synopsys` | none — UNVERIFIED |
| Synopsys IC Compiler II Library Manager | `icc2_lm_shell` | `library_prep` | `synopsys` | `icc2_lm_shell -version` — parse the `lm_shell version` line |
| Synopsys PrimeTime | `pt_shell` (`pt_shell64`) | `sta` | `synopsys` | `pt_shell -version` — parse the `pt_shell version` line |
| Cadence Tempus | `tempus` | `sta` | `cadence` | none — UNVERIFIED (optional; absent on some hosts — use PrimeTime) |
| Synopsys Formality | `fm_shell` (`formality`) | `lec` | `synopsys` | `fm_shell -version` — parse the `Formality (R) Version` line |
| Cadence Conformal LEC | `lec` | `lec` | `cadence` | `lec -version` — parse the `Tool:` line (`Tool:<tab>lec<tab><version>`) |
| Cadence JasperGold | `jg` | `formal` | `cadence` | none — UNVERIFIED |
| Synopsys VC Formal | `vcf` | `formal` | `synopsys` | none — UNVERIFIED |
| Siemens Questa Formal | `qformal` | `formal` | `siemens` | none — UNVERIFIED |
| Synopsys TetraMAX | `tmax` | `atpg` | `synopsys` | none — UNVERIFIED |
| Cadence Modus Test | `modus` | `atpg` | `cadence` | none — UNVERIFIED |
| Siemens Tessent | `tessent` | `atpg` | `siemens` | none — UNVERIFIED |
| Synopsys SpyGlass | `spyglass` | `lint_cdc` | `synopsys` | none — UNVERIFIED |
| Xilinx Vitis HLS | `vitis_hls` | `hls` | `xilinx` | none — UNVERIFIED |
| Cadence Stratus | `stratus` | `hls` | `cadence` | none — UNVERIFIED |
| Siemens Catapult | `catapult` | `hls` | `siemens` | none — UNVERIFIED |
| Xilinx Vivado | `vivado` | `fpga_pnr` | `xilinx` | none — UNVERIFIED |
| Intel Quartus | `quartus_sh` | `fpga_pnr` | `intel` | none — UNVERIFIED |
| Microchip Libero | `libero` | `fpga_pnr` | `microchip` | none — UNVERIFIED |
| ARM Artisan | `artisan` | `mem_compiler` | `arm` | none — UNVERIFIED |
| Synopsys SiliconSmart | `siliconsmart` | `characterisation` | `synopsys` | none — UNVERIFIED |
| Cadence Liberate | `liberate` | `characterisation` | `cadence` | none — UNVERIFIED |
| Synopsys StarRC | `StarXtract` | `extraction` | `synopsys` | none — UNVERIFIED |
| Synopsys StarRC grdgenxo | `grdgenxo` | `extraction_tech` | `synopsys` | `grdgenxo -v` — parse the `Version` line of the StarRC banner |
| Cadence Quantus | `quantus` | `extraction` | `cadence` | `quantus -version` — parse the `Version        :` line |
| Cadence Quantus Techgen | `Techgen` | `extraction_tech` | `cadence` | `Techgen -version` — parse the `Version        :` line |
| Cadence Voltus | `voltus` | `power_analysis` | `cadence` | none — UNVERIFIED (optional; absent on some hosts — use RedHawk for IR/EM, PrimePower for power) |
| Cadence Joules | `joules` | `power_analysis` | `cadence` | `joules -version` — parse the `Program Name:` line |
| Ansys RedHawk | `redhawk` | `ir_em` | `ansys` | `redhawk -v` — parse the release (`2025 R2.2`) at the start of the first line |
| Ansys Totem | `totem` | `ir_em` | `ansys` | `totem -v` — parse the release at the start of the first line |
| Siemens Calibre | `calibre` | `drc_lvs` | `siemens` | `calibre -version` — parse the `//  Calibre v` line |
| Cadence Pegasus/PVS | `pvs` | `drc_lvs` | `cadence` | `pvs -version` — parse the `Version        :` line |
| Arm Compiler 6 | `armcc` | `embedded_compiler` | `arm` | none — UNVERIFIED |
| SEGGER J-Link GDB Server | `JLinkGDBServer` | `debug_probe` | `segger` | none — UNVERIFIED |
| Lauterbach TRACE32 | `t32marm` | `debug_probe` | `lauterbach` | none — UNVERIFIED |
| Arm Development Studio | `armds` | `debug_probe` | `arm` | none — UNVERIFIED |

**Commercial PD/signoff probes, measured 2026-10-25 on a second EDA host** (stdin `/dev/null`,
each probe in its own process group, 120 s budget, light load): `lc_shell -version` 30 s,
`icc2_lm_shell -version` 41 s (`lm_shell version X-2025.06`), `grdgenxo -v` 4 s (StarRC banner
`Version X-2025.06-SP1`), `quantus -version` 32 s and `Techgen -version` 2 s (`Version        :
23.1.1-p051`), `fm_shell -version` 38 s, `lec -version` 20 s (`Tool:	lec	24.10-p100`),
`pvs -version` 36 s (`Version        : 24.12-s015`), `calibre -version` 62 s (`//  Calibre
v2026.1_17.11`), `redhawk -v` 5 s and `totem -v` 53 s (`2025 R2.2 ...`), `genus -version` 75 s
(`Version: 23.14-s090_1`), `joules -version` 30 s (`Version: 23.14-s077_1`), `innovus -version`
**123 s** (`@(#)CDS: Innovus v23.14-s088_1`) and `pt_shell -version` **≈120 s** — all exit 0
with the named line, and recorded in the table above. **On that host `dc_shell -version`
printed `dc_shell version    -  X-2025.06-SP3` but exited 1** (twice), so parse the line and
do not gate on the exit code. `StarXtract -v` printed `Version: X-2025.06-SP1` and also exited 1
(twice); it stays UNVERIFIED until a clean probe is found. `icc2_shell -version` and
`fc_shell -version` printed nothing within 120 s and stay UNVERIFIED. An earlier pass at
load average ~10 with a 60 s budget timed out on `pt_shell`, `genus`, `innovus` and `joules` as
well — which is why rule 4 below now budgets 180 s. **A vendor launcher is a shell script that execs a
child (`pt_shell` → `pt_shell_exec`); `timeout` kills only the script and the child survives
holding a licence.** Run every probe in its own process group (`setsid`) and kill the group
(`kill -- -<pgid>`) on timeout, then confirm with `ps` that no `*_exec` child remains.

**Two command fixes.** Cadence Conformal's batch command is `lec` (the product was listed as
`conformal`, which is not a binary), and StarRC's is `StarXtract` (`starrc` is not a binary);
both resolve under their install `bin/` on the second host. `tempus`, `voltus`, `icv` and
`redhawk_sc` are absent there: Tempus and Voltus are kept as optional rows, and a flow that
needs signoff STA, power or IR/EM uses PrimeTime / PrimePower and RedHawk/Totem instead.
`magic` and `netgen` are commonly not on the host PATH at all but inside the LibreLane container
image; detect them there when the flow runs LibreLane.

**`vcs -ID` also prints a FLEXlm host ID.** Parse and store the `Compiler version`
value only — never write the host ID into `tool-status.json`.

**A probe flag is listed only once confirmed on a real install** — a guessed flag can open
an interactive shell or check out a license. The flags above were each measured: exit 0
with the named line present, in 1–26 s, no license queue. `dc_shell -version` prints an
unrelated ASLR advisory first, so parse the line containing `version`, never the first line
of output. `genus -version` was measured the same way: 26 s cold, 12 s warm, which is why
rule 4 below sets the probe timeout at 180 s (originally 10 s, then 60 s): `innovus` and
`pt_shell` took about 2 minutes on the second host.

**The two original `UNVERIFIED` rows were unverified upstream, not an oversight** (Innovus has
since been measured on a second host; see the commercial-probe paragraph above). Neither
could be confirmed on the reference host, and in both cases the obstacle was the install
rather than the flag: `innovus -version` exits 0 reporting an expired build authorisation,
and `vsim -version` exits 0 failing to load `libXext.so.6`. A site with a working install of
either should confirm the flag and contribute it here.

**The remaining `UNVERIFIED` rows above have no probe evidence at all, which is worth
recording precisely so a later contributor does not re-measure it blind:**
`voltus -version` and `tempus -version` each exit 0 but with `cds_plat.dat` absent, the
same shape as the `innovus` failure. `joules`, `conformal`, `starrc`, `liberate`, and `jg`
did not resolve to a binary under `<root>/linux/<version>/bin/` on the reference host at
all. Three of the exit-0 cases print no version line, which is exactly why rule 4's WARN
conditions below treat "exits 0, no version line" as its own case rather than a pass.

**`urg` and `imc` read the coverage databases their simulator writes, and nothing else.** `urg`
ships in the VCS tree (`$VCS_HOME/bin/urg`); `urg -version` was measured on the reference host:
exit 0 in under 1 s, `URG Version Y-2026.03`, no license checkout. `imc` is **not** reliably
installed with Xcelium: it ships under `$XCELIUM_HOME/tools/bin` on some installs and with
vManager/IMC on others, and is often off PATH even when `xrun` is on it. On the reference host
the Xcelium 24.03 tree holds only `tools/bin/launch_rmi_imc.sh` and no `imc` binary anywhere,
which is why `imc` has no measured probe. `tool_discovery` rule 4 searches for it off PATH and
records a missing one as a coverage-reporting gap, not as a coverage failure.
The two share the role `coverage_report` and are not substitutable: each reads only its own
simulator's database (`.vdb` vs `cov_work/**/*.ucd`), so a VCS database cannot be reported by
`imc`, nor an Xcelium one by `urg`.

Note on Formality: the primary command is `fm_shell`. `formality` is the legacy GUI wrapper
and is absent from recent installs, so it is listed as the alternate.

Same `role` with a different `dialect` means the two tools are not interchangeable
however similar their purpose. `environment_validation` reports such coexistence.

**Single-member roles are intentional, not an oversight** — each is a role whose only
plausible peers are already claimed by their primary role, so the role can never produce a
dialect-conflict WARN today:
- `lint_cdc` holds only `spyglass`. `jg` and `vsim` also do clock-domain-crossing work, but
  `jg` is recorded under `formal` and `vsim` under `rtl_simulator` — a tool carries one
  `role` in `tool-status.json`, and each already does its primary job elsewhere.
- `mem_compiler` holds only `artisan`. Synopsys's memory compiler shares a binary with
  `siliconsmart`, which is recorded under `characterisation` — the job that binary performs.
- `extraction` holds `StarXtract` (synopsys) and `quantus` (cadence): two dialects, and their
  tech files (`nxtgrd` vs `qrcTech`) are not interchangeable either. `extraction_tech` holds the
  two tech-file generators, `grdgenxo` and `Techgen`, kept apart from the extractors because they
  run once per PDK, not once per design.
- `library_prep` holds `lc_shell` and `icc2_lm_shell`, both synopsys: `.lib`→`.db` and the NDM
  reference library. The Cadence flows read `.lib`/LEF directly and need no peer.
- `ir_em` holds `redhawk` and `totem` (ansys). Voltus would be its cadence peer but is filed under
  `power_analysis`, the job it is used for here.
- `power_analysis` has three single-command peers plus three commandless ones (below); none
  of `voltus`, `primepower`, `joules`, or `powerpro` has a second same-dialect alternative.
- `embedded_compiler` holds only `armcc` with a command; Green Hills and IAR are its
  commandless peers.

**Products named in domain skills with no documented command, so not detectable by this
table** (the table is keyed on `which <command>`; a row with no command cannot be probed):
Synopsys Platform Architect (`arch_simulator`/`synopsys`), ARM Performance Models
(`arch_simulator`/`arm`), Cadence Virtual System Platform (`arch_simulator`/`cadence`),
Green Hills MULTI (`embedded_compiler`/`greenhills`), IAR Embedded Workbench
(`embedded_compiler`/`iar`), Synopsys Synplify (`synthesis`/`synopsys`), Siemens Aprisa
(`physical_design`/`siemens`), Synopsys PrimePower (it runs inside `pt_shell`, so detecting
PrimeTime is detecting it) and Siemens Questa PowerPro (both `power_analysis`; Cadence Joules
now has its `joules` row above), Synopsys VC Static (`lint_cdc`/`synopsys`). A command name
is not guessed here any more than a probe flag is above; each is instead given its `role`
and `dialect` at the point of use in its domain skill.

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
| `mcp-verilator.json` | Verilator lint (`mode: "lint"`) or a compiled sim binary (`mode: "sim"`) | 秒至分钟 |
| `mcp-bambu.json` | Bambu HLS | 分钟 |
| `mcp-gem5.json` | gem5 short benchmark | 分钟，设置 TOOL_TIMEOUT_S |
| `mcp-symbiflow.json` | SymbiYosys bounded proof | 分钟–小时 |

适配器为 `plugins/infrastructure/tools/mcp-adapter.py`。每个服务器运行 `--wrapper` 指定的一个 Wrapper，但 `verilator` 例外：`mode: "lint"` 会运行已配置的 `wrap-verilator-sim.sh` 同目录中的 `wrap-verilator-lint.sh`，因为仿真 Wrapper 的第一个参数是已编译的仿真可执行文件。因此 8 个批处理服务器使用 25 个 Wrapper 中的 9 个；`wrap-vcs-compile.sh` 和 `wrap-xrun-compile.sh` 直接调用，不经过 MCP。

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

### `tool-status.json` is a discovery-state artifact
```json
{
  "python_env": {"exec":"","type":"module | system | custom | venv","bin_dir":"","module_name":null},
  "tools": [{"tool":"","command":"","status":"FOUND | MISSING | PROPRIETARY_ONLY","version":"","path":"","role":null,"dialect":null}]
}
```

### Licensed tools on a small shared host (measured)

以下规则来自 8 vCPU / 15 GB VMware 共享 EDA 主机的两周 RTL→GDS 实测。

- **One heavy tool at a time, enforced by a lock**：不能用“先 `pgrep` 再启动”这种 check-then-act 方式；两个 Agent 会同时通过检查。统一用 host-wide `flock -x 9`，包装成 `licensed_lock.sh <cmd>`，锁覆盖工具及其 child 的整个生命周期。对尚未接入 lock 的 caller 只用精确进程名 `pgrep -x`。
- **Gate load/memory and kill the process group**：`safe_run.sh` 启动前检查 1-min load 与 `MemAvailable`，使用 `systemd-run --user --scope -p MemoryMax=<cap> -p MemorySwapMax=0`；CPU 线程 **2 or fewer**。超时要 kill **process group**，不能只杀 launcher。
- Vendor launcher 常 exec `*_exec` 子进程；裸 `timeout` 会留下子进程继续占 license。不要用宽泛 `pkill -f`，它可能匹配 caller 自己。
- 商业工具 cold start 可能 **30-65 min**；runtime 必须同时记录 load。长任务使用 `setsid`/`nohup`，结束时写 **done-marker**，session 结束后仍可恢复。
- License yes/no 使用 vendor 的 `ckout_test` 或实际 checkout smoke；仅 `lmstat` 的 server 文本不能替代真实 checkout。
- 日志 parser 必须找明确的 **result line**；exit 0、启动 banner 或空 report 都不是 PASS。

## Stage: tool_discovery

### Domain Rules
1. 对每个开源工具执行 `which <command>` 和 `<command> --version`（或 `-version`）。
2. **Python interpreter detection** 在任何 Python package 检查前只执行一次，first match wins。

   **步骤 A：模块系统探测（在 PATH 检查前执行）：**
   a. 根据下方 `module_discovery` 的检测规则与调用阶梯分类模块系统，并证明能够调用；不要在此重新推导，也不能只凭 `$MODULESHOME` 就认定 `module` 可运行。
   b. 获得列表（`module_listing` 为 `"LISTED"`）后，不区分大小写搜索匹配 `python` 或 `python3` 的条目。
   c. 找到 Python 模块时，按下方 **Module version selection** 选取版本，不能简单排序。运行 `module load <python-module>`，再用 `which python3` 解析 `PYTHON_EXEC`。排除非发布版本在此尤其重要：选中的解释器会保持加载整个运行过程，选中 `_test` 或 `-debug` 构建会影响所有后续阶段。设置 `python_env.type = "module"`，并在 `python_env.module_name` 记录所加载模块名。**整个编排器运行期间保持模块加载，不能卸载**；后续 `tool_installation`、`wrapper_deployment`、`environment_validation` 均依赖可解析的 `PYTHON_EXEC`。生成的 `load-modules.sh` 负责未来 Shell 会话的持续加载。
   d. `module_system` 为 `"none"`、调用阶梯耗尽（`module_listing` 为 `"UNAVAILABLE"`）或列表无 Python 模块时，进入步骤 B。检测到但无法列出的模块系统不等于不存在模块系统：虽然在此回退到 PATH 解释器，`module_discovery` 仍须报告 WARN，不能因已找到解释器而省略警告。

   **Venv check before generic PATH fallback:** 若当前 shell 已激活 virtual environment（`VIRTUAL_ENV` 非空）且 `$VIRTUAL_ENV/bin/python3` 可执行，优先记为 `python_env.type == "venv"`，并把该解释器作为 `PYTHON_EXEC`。只有没有有效 venv 时再进入通用 PATH。

**Step B — PATH fallback**
   e. `which python3`，保存为 `PYTHON_EXEC`。
   f. 找不到则在 `tool-status.json` 把 python3 记为 `MISSING` 并立即 FAIL；所有 wrapper/Python package 都依赖它。
   g. 分类：
      - `system`：`PYTHON_EXEC == /usr/bin/python3`
      - `module_system == "custom"`：其他路径（pyenv/conda/venv/custom prefix）

   **步骤 C：完成记录：**
   h. 无论如何解析到 `PYTHON_EXEC`，均设置 `PYTHON_BIN_DIR = $(dirname "$PYTHON_EXEC")`。
   i. 在 `tool-status.json` 的顶层 `python_env` 键下记录：
      ```json
      {
        "python_env": {
          "exec": "<absolute path>",
          "type": "module | system | custom | venv",
          "bin_dir": "<absolute dir>",
          "module_name": "<module name, or null if not module-based>"
        }
      }
      ```
   j. 获取 `"$PYTHON_EXEC" --version`，在 `tools` 数组中存为普通条目（`"tool": "python3"`、`"command": "python3"`、`"status": "FOUND"`、`"version": "<output>"`、`"path": "<PYTHON_EXEC>"`），让 `module_discovery` 能找到 `python3` 并升级为 `FOUND_PREFER_MODULE`。

3. **例外：Python 包：**
   - **cocotb：** 按规则 2 确定的解释器类型检测：
     - `python_env.type == "custom"` 或 `"module"` 时，先检查 `"$PYTHON_BIN_DIR/cocotb-config" --version`；退出为零则记录 FOUND 和返回的版本字符串。仅在不存在或退出非零时回退到 PATH 上的 `cocotb-config --version`。
     - `python_env.type == "system"` 时，仅使用 PATH 上的 `cocotb-config --version`。
     - 所有尝试失败时报告 MISSING。
   - **openlane：** 运行 `"$PYTHON_EXEC" -m pip show openlane 2>/dev/null`。退出码为 0 且输出含 `Name: openlane` 时记录 FOUND 并提取 `Version:`；否则记录 MISSING。
   - **uv：** `python_env.type == "custom"` 或 `"module"` 时先检查 `"$PYTHON_BIN_DIR/uv" --version`，再回退到 PATH 上的 `uv --version`。`system` 类型仅使用 `uv --version`。
4. **专有工具：** 使用 `which <primary-executable>` 检查 PATH（主命令及备用命令见上方专有工具表）；绝不尝试安装。找到则记录 `PROPRIETARY_ONLY`，否则为 `MISSING`。PATH 中找到且表中有版本探测命令时，以 60 秒超时运行并解析指定行，将解析后的字符串存入 `version`。不能使用过短超时：Cadence Common UI 为回答 `-version` 会启动完整 Shell，冷 NFS 缓存下需要数十秒（`genus -version` 实测冷缓存 26 秒、热缓存 12 秒）。对 `vcs` 仅保存 `Compiler version`，丢弃 FLEXlm host ID。

   表中无探测命令、探测超时、退出非零，**或退出 0 但未打印指定行**时，将 `version` 留空，并输出注明工具及原因的 WARN。只有真正找到指定行才记录版本；退出 0 不代表打印了版本。

   在参考主机上直接调用工具的实测结果：`innovus -version` 退出 0 但报告构建授权过期，`voltus -version` 退出 0 但报告“cannot find a proper installation”，`vsim -version` 退出 0 但共享库加载失败。**上表这三个工具都没有探测命令**，因此其空 `version` 来自“无探测命令”条件，而非最后一个条件。这些例子证明，无论厂商，损坏的安装都可能退出 0；因此最后一个条件须保护确实有探测命令的五个工具，其安装也可能同样损坏。版本探测绝不会使阶段失败。
5. 每个工具记录为 `FOUND`、`MISSING` 或 `PROPRIETARY_ONLY` 之一
6. 捕获 PATH 中每个已找到工具的精确版本字符串：`FOUND` 使用规则 1；专有工具表中有探测命令的 `PROPRIETARY_ONLY` 使用规则 4
7. 按上方专有工具表与角色/方言表设置 `tools` 数组每项的 `role` 和 `dialect`；两表均未列出的工具，两字段均设为 `null`
8. 本阶段绝不尝试安装
9. 前进前将结果写入 `tool-status.json`

### QoR Metrics to Evaluate
- `tools_detected`：FOUND 数，功能性开源 flow 目标 ≥10
- `tools_missing`：缺失开源工具数
- `proprietary_found`：PATH 中检测到的商业工具数
- `proprietary_versioned`: count of PROPRIETARY_ONLY tools with a non-empty `version`

`dialect_conflicts` 不是本阶段的指标；虽然使用这里记录的 `role` 和 `dialect`，但由 `environment_validation` 规则 7 计算并声明。

### Output Required
- `tool-status.json` 包含两个顶层键：
  - `python_env`：`{ "exec": "", "type": "module|system|custom|venv", "bin_dir": "", "module_name": "" }`，由规则 2 填充
  - `tools`：由 `{ "tool": "", "command": "", "status": "FOUND|MISSING|PROPRIETARY_ONLY", "version": "", "path": "", "role": null, "dialect": null }` 组成的数组

每项始终包含 `role` 和 `dialect`，值为上表中的字符串或 `null`。每个 `FOUND` 工具以及探测成功的 `PROPRIETARY_ONLY` 工具，`version` 均非空。

`tool` 与 `command` 均保存**命令名**，即 `which` 检查的可执行文件名，见上方开源/专有工具表中的反引号内容。`module-status.json` 保存相同值（`"tool": "<command>"`），使 `module_discovery` 能将条目匹配回此文件。产品名只用于说明文字及专有工具表首列，**绝不用于规则匹配的字段**。产品名与命令名不同时，以产品名匹配会找不到条目——OpenSTA 命令为 `sta`，Formality 为 `fm_shell`——而“未找到条目”与“工具缺失”并不相同。

此约定仅适用于 `tool-status.json` 和 `module-status.json`。下方 Wrapper JSON Output Schema 有意使用另一约定：`"tool": "<tool-name>"` 是 `opensta` 或 `verilator-sim` 这样的 Wrapper 标签，用于识别输出记录的 Wrapper，而非匹配工具条目。不要把 Wrapper 改成输出命令名。

注：基于模块的可用状态（`FOUND_PREFER_MODULE`、`MISSING_LOAD_MODULE`）及 `module_names`/`versions_available` 字段由下一阶段 `module_discovery` 添加。

---

### Python candidate classification supplement
模块发现的 candidate 可以记录：
```json
{"exec":"<path>","type":"module | system | custom | bundled","version":"<python3.N>"}
```
其中 **bundled** 仅表示某 EDA/tool tree 内附带的 Python；它 **is never selected as `PYTHON_EXEC`**。如果 module/PATH/venv 都找不到合适解释器，也 **never fall back to a `bundled` one**。识别 `python3.N`（例如 python3.11、python3.12）时按真实版本比较，不按字符串排序。

## Stage: module_discovery

### Domain Rules

#### Module system detection

环境变量已设置不能证明 `module` 可运行。先分类，再通过下方调用阶梯**证明可调用性**；决定依据是阶梯结果，而非分类。

1. PATH 中存在 `modulecmd` ⇒ `module_system: "tclmod"`；在 `module_system_detail` 中记录 `$MODULESHOME` 是否也已设置。
2. `$MODULESHOME` 已设置但 PATH 中无 `modulecmd` ⇒ `module_system: "custom"`。这表示“尚未确认是 Environment Modules”，不能认定“已证明为自定义系统”：经典安装的 `modulecmd` 也可能不在 PATH，下方第 3 级调用用于区分。
3. 两者均无 ⇒ `module_system: "none"`、`module_listing: "UNAVAILABLE"`、`module_listing_error: "no module system present"`。报告下方的 none WARN，跳过其余规则，写入 `module-status.json`，前进到 `tool_installation`。

#### Module invocation ladder
`module` 通常是 **Shell 函数或别名**，不是可执行文件；因此即使主机显然已安装模块系统，非交互 Shell 中也可能没有它。实际探测调用，不能由环境变量推断。按顺序尝试以下各级，在首个满足下方成功条件的级别停止，将该调用原样记入 `module_invocation`。

| # | 调用方式 | 使用条件及证明内容 |
|---|---|---|
| 1 | `module avail` | 若编排器从交互或登录 Shell 启动，其自身 Shell 可能已定义 `module` |
| 2 | `modulecmd bash avail` | 仅当 PATH 中存在 `modulecmd`；得到列表即确认 `tclmod` |
| 3 | `. "$MODULESHOME/init/bash"; module avail` | 经典 Environment Modules 提供 `init/bash`；得到列表后将 `custom` **升级**为 `tclmod`，在 `module_system_detail` 记录 `modulecmd` 只是未加入 PATH |
| 4 | `. "$MODULESHOME/module.sh"; module avail` | 站点 Wrapper 的 sh 初始化。参考主机实测：`module` 成为 Shell 函数，`module avail` 用时 159.5 秒、退出 0、输出 3813 行，其中 3812 行符合条目格式；分类保持 `custom` |
| 5 | `MODULESHOME="$MODULESHOME" "$MODULESHOME/module" avail` | 最后备选方案，适用于 Wrapper 自身为可执行脚本的情况；还要导出其初始化脚本设置的路径变量，站点 Wrapper 常用这些变量代替 `$MODULESHOME` |

- **某一级仅在退出 0 且输出至少有一行符合条目格式时才成功。任一条件单独成立都不够。失败时继续下一级，不能认定主机没有模块。** 两个条件都有实测依据。参考主机第 5 级退出 **1** 并输出 `Usage: [-n] subcommand [arguments ...]`，其中包含 `modulename/scope`、`modulename/version`、`modulename/scope/version`；只看输出形状会误认为列出了三个名为 `modulename` 的模块。反向情形——退出 0 却无列表——与 `tool_discovery` 规则 4 的损坏安装版本探测案例一致。
- **对 Shell 设置超时，不能直接包裹命令。** `timeout` 执行二进制文件，不能直接调用 Shell 函数。实测在第 4 级刚成功的主机上，`timeout 60 module avail` 返回 127 并报 `timeout: failed to run command 'module'`。每一级应按 `timeout 300 bash -c '<rung>; module avail </dev/null 2>&1'` 运行。
- **超时预算为 300 秒，而非版本探测的 60 秒。** 列表遍历所有 modulefile 树：热 NFS 缓存下实测 159.5 秒，途中可能输出失效路径产生的 `ls: cannot access ...` 噪声。过短预算会误判正常模块系统无法探测。
- **标准输入始终重定向自 `/dev/null`。** 否则要求输入的 Wrapper 会阻塞整个运行且无法产生诊断输出。
- 所有级别均失败后，设置 `module_listing: "UNAVAILABLE"`，将最后一级 stderr 存入 `module_listing_error`。只有整个阶梯耗尽才构成 WARN，单级失败不构成 WARN。

#### Listing entry format
条目包含由 `/` 分隔的**两个或更多**片段，末尾可带括号注释。参考主机实测：`klayout/adi/0.29.0`、`verilator/adi/3.922`、`klayout/adi/0.27.11 (adi default)`。先移除末尾 `(...)` 注释，再将**最后一个** `/` 片段作为版本，将不含注释的条目字符串存入 `module_names`。不能假定格式只有 `<name>/<version>`，否则会把 `klayout/adi/0.29.0` 的 `adi` 误记为版本。

**注释是数据，不能忽略。** 注释含 `default`（不区分大小写）的条目是模块系统为该工具选择的默认版本，参考主机以 `klayout/adi/0.27.11 (adi default)` 标识。记录该条目；下方选择规则优先采用它，而非本阶段计算出的版本。

将条目按 `/` 拆成 token 后，不区分大小写地匹配映射表；模式必须匹配**完整 token**，含 `/` 的模式则匹配连续多个完整 token。**绝不能匹配任意子串。** 对真实 3812 项列表实测，子串匹配产生两类误报：名字仅以映射命令结尾的模块（名为 `...slang` 的优化工具误匹配 `slang`），以及名字或版本仅包含命令的模块（版本以 `_python2` 结尾的验证工具及名字含 `python3` 的 GUI 工具包误匹配 `python3`）。第二类尤其有害：`tool_discovery` 步骤 A 会加载选中的 Python 模块并保持整个运行过程，子串匹配排名最高的却是 GUI 工具包而非解释器。完整 token 匹配排除两类误报，留下 12 个真实工具。

#### Module version selection
本 Skill 选择工具版本时（`tool_discovery` 规则 2 步骤 A c 及下方规则 9），均使用此规则。不要在调用位置重复规则，也不能用简单排序替代。**字典序最大值不等于最新版本**：真实树上实测，覆盖 3.6.x–3.14.x 的 13 版本 Python 树，最新为 `3.14.6`，字典序最大却为第四旧的 `3.9.7`，因为第二段中 `"9" > "1"`。

结果是**该主机应使用的版本**，并不总是最新版本。模块系统指定默认版本时优先使用它；站点默认通常是经过验证的较旧构建。同一参考主机上，每个检查工具的注释默认版本都与最新版本不同，有些相差数个版本。这是预期行为，不应绕过。

**Selection order.**（选择顺序）采用第一个适用项：

1. 若列表标注系统 `default`，选择该条目；站点自身的选择高于任何本地计算结果。
2. 否则按下方比较器选择最高的**发布版本（release）**。
3. 仅当所有候选均为非发布版本时，选择所有版本中最高者。

**非发布版本**指任意片段等于 `dev`、`test`、`debug`、`rc`、`alpha`、`beta`、`snapshot` 或 `nightly`（不区分大小写）的版本。它们保留在 `versions_available`，因为确实存在且用户可能需要，但有发布版本时绝不自动选择。参考主机中 `3.12.2_test`、`3.6.2-debug`、`5.24-dev` 与正常版本位于同一树中。该列表有意保持简短：`3.12.2.R10` 这样的站点修订标签或 `3.9.7n` 这样的补丁字母仍属于**发布版本**，使用同一比较器排序。

**比较器。** 将版本按 `.`、`-`、`_` 分割，再逐段比较：

- 两段均为数字：按整数比较，因此 `3.14.6` > `3.9.7`。
- 数字后跟字母的片段（`7n`、`03b`）：先比较数字前缀，再按文本比较字母后缀，因此 `3.9.7n` > `3.9.7`。
- 一段为数字而另一段不是：数字段更高。
- 两段均非数字：按文本比较。

所有共同片段都相等时，片段**更多**的版本更高：`3.12.2.1` > `3.12.2`，`3.12.2.R10` > `3.12.2`，因为附加段表示较短版本的修订。不要将额外的非数字段特殊处理为较低版本：`5.24` 应优于 `5.24-dev` 已由前面的非发布版本排除规则解决；发布版本池内剩余附加段都是发布后修订标签，此时更长确实更新。

实现应检查以下能暴露各类简单比较器缺陷的集合：`3.9.7`、`3.9.7n`、`3.12.2`、`3.12.2.1`、`3.12.2.R10`、`3.14.6`、`5.048`、`5.24-dev`。文本比较会选 `3.9.7`；按 `.` 分段再转整数会在 `R10` 报错；仅比较片段数则会选 `5.24-dev`，除非已先排除非发布版本。

将逐工具选择结果以 `selected`、`selected_basis` 和 `candidates` 写入 `module-status.json`，使错误选择在产物中可见，而非只影响已加载环境。

#### WARN taxonomy
| Condition | Severity | `description` / `fix` |
|---|---|---|
| `module_system: "none"` | WARN，继续 | `"未找到模块系统：$MODULESHOME 未设置且 PATH 无 modulecmd；未通过模块调查工具"` / `"全部所需工具已在 PATH 时无需操作"` |
| `module_system` 不为 `"none"` 且 `module_listing: "UNAVAILABLE"` | WARN，继续 | `"检测到 <module_system> 模块系统（<module_system_detail>），但调用未得到列表（<module_listing_error>）；tools_via_modules 为空是列表失败，不能说明没有模块"` / `"在能解析 module 的 Shell 重跑，或先 source $MODULESHOME/module.sh（bash）/module.csh（tcsh），再重跑 module_discovery"` |
| 上行条件成立，**且**关键路径工具 (`yosys`, `verilator`, `openroad`, `sta`)在 `tool-status.json` 中为 `MISSING` | WARN **并升级处理** | 在上述描述后补充 `"关键工具 <list> 为 MISSING，且无法通过模块列表核对"`; `failure_class: "tool_error"`, `suggested_next_step: "escalate"` |

仅当 `module_listing` 为 `"LISTED"` 时，空 `tools_via_modules` 才能证明主机没有可提供的模块。不能将调用阶梯耗尽报告为“没有找到模块”；不读取 `module_listing` 就无法区分两种情况。

修复文字同时列出两种初始化脚本，因为探测始终在 `bash -c` 下运行，而用户手工重跑时可能使用 `bash` 或 `tcsh`。

#### `module-status.json` is a module-discovery receipt
```json
{
  "module_system": "tclmod | custom | none",
  "module_system_detail": "",
  "module_invocation": "",
  "module_listing": "LISTED | UNAVAILABLE",
  "module_listing_error": null,
  "tools_via_modules": [
    {
      "tool": "<command>",
      "module_names": [],
      "versions_available": [],
      "selected": null,
      "selected_basis": "site_default | highest_release | highest_any | null",
      "candidates": []
    }
  ]
}
```

#### Module-to-tool mapping table（模块到工具映射表）

| Tool command | Module name patterns to match (case-insensitive substring) |
|---|---|
| `vcs` | `vcs`, `synopsys-vcs`, `synopsys/vcs` |
| `xrun` | `xcelium`, `cadence-xcelium`, `cadence/xcelium` |
| `dc_shell` | `design-compiler`, `synopsys/dc`, `dc_shell` |
| `innovus` | `innovus`, `cadence/innovus`, `cadence-innovus` |
| `vsim` | `questa`, `questasim`, `mentor/questa` |
| `urg` | `vcs`, `synopsys-vcs`, `synopsys/vcs` |
| `imc` | `imc`, `vmanager`, `xcelium`, `cadence/xcelium` |
| `pt_shell` | `primetime`, `synopsys/pt`, `pt_shell` |
| `fm_shell` | `formality`, `synopsys/formality`, `fm_shell` |
| `genus` | `genus`, `cadence-genus`, `cadence/genus` |
| `fc_shell` | `fusion-compiler`, `synopsys/fc`, `fc_shell` |
| `icc2_shell` | `ic-compiler`, `icc2`, `synopsys/icc2` |
| `tempus` | `tempus`, `cadence-tempus`, `cadence/tempus` |
| `lec` | `conformal`, `cadence-conformal`, `cadence/conformal` |
| `jg` | `jaspergold`, `cadence-jg`, `cadence/jg` |
| `vcf` | `vc-formal`, `vcf`, `synopsys/vcf` |
| `qformal` | `questa-formal`, `qformal`, `mentor/qformal` |
| `tmax` | `tetramax`, `tmax`, `synopsys/tmax` |
| `modus` | `modus`, `cadence-modus`, `cadence/modus` |
| `tessent` | `tessent`, `siemens-tessent`, `siemens/tessent` |
| `spyglass` | `spyglass`, `synopsys-spyglass`, `synopsys/spyglass` |
| `vitis_hls` | `vitis`, `vitis-hls`, `xilinx/vitis` |
| `stratus` | `stratus`, `cadence-stratus`, `cadence/stratus` |
| `catapult` | `catapult`, `siemens-catapult`, `siemens/catapult` |
| `vivado` | `vivado`, `xilinx/vivado` |
| `quartus_sh` | `quartus`, `intel/quartus` |
| `libero` | `libero`, `microchip/libero` |
| `artisan` | `artisan`, `arm-artisan`, `arm/artisan` |
| `siliconsmart` | `siliconsmart`, `synopsys/siliconsmart` |
| `liberate` | `liberate`, `cadence-liberate`, `cadence/liberate` |
| `StarXtract` | `starrc`, `synopsys-starrc`, `synopsys/starrc` |
| `grdgenxo` | `starrc`, `synopsys-starrc`, `synopsys/starrc` |
| `quantus` | `quantus`, `cadence-quantus`, `cadence/quantus` |
| `Techgen` | `quantus`, `cadence-quantus`, `cadence/quantus` |
| `lc_shell` | `library-compiler`, `synopsys/lc`, `lc_shell` |
| `icc2_lm_shell` | `ic-compiler`, `icc2`, `synopsys/icc2`, `fusion-compiler` |
| `joules` | `joules`, `cadence-joules`, `cadence/joules` |
| `redhawk` | `redhawk`, `ansys/redhawk` |
| `totem` | `totem`, `ansys/totem` |
| `calibre` | `calibre`, `mentor/calibre`, `siemens/calibre` |
| `pvs` | `pvs`, `pegasus`, `cadence/pvs` |
| `magic` | `magic` |
| `netgen` | `netgen` |
| `voltus` | `voltus`, `cadence-voltus`, `cadence/voltus` |
| `armcc` | `armcc`, `arm-compiler`, `arm/armcc` |
| `JLinkGDBServer` | `jlink`, `segger`, `segger/jlink` |
| `t32marm` | `trace32`, `lauterbach`, `lauterbach/trace32` |
| `armds` | `armds`, `arm-ds`, `arm/armds` |
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
1. 使用上方检测规则分类模块系统
2. 使用上方调用阶梯获得列表，记录 `module_invocation`、`module_listing`；耗尽时记录 `module_listing_error`
3. `module_listing` 为 `"UNAVAILABLE"` 时，报告上方分类表对应的 WARN；关键路径工具为 `MISSING` 时先升级处理。以 `tools_via_modules: []` 写入 `module-status.json` 后前进。跳过规则 4–9：未获得列表就无法匹配工具，未匹配不代表没有模块提供该工具。
4. 对列表每个条目，不区分大小写地匹配映射表
5. 对每个匹配工具，按上方条目格式规则收集所有版本字符串
6. 前进前写入 `module-status.json`
7. `tool-status.json` 中为 `FOUND` 且存在模块的工具，改为 `FOUND_PREFER_MODULE`，添加 `module_names` 和 `versions_available`，纳入 `load-modules.sh`；模块优先于 PATH 版本
8. `tool-status.json` 中为 `MISSING` 且存在模块的工具，改为 `MISSING_LOAD_MODULE`，添加 `module_names` 和 `versions_available`
9. 为所有 `FOUND_PREFER_MODULE` 和 `MISSING_LOAD_MODULE` 工具生成 `load-modules.sh`，按上方 **Module version selection** 选版本；替代版本以内联注释保留，并在选中行末注释注明选择依据
10. 绝不自动执行 `load-modules.sh`。打印：“检查并 source `load-modules.sh` 以加载 EDA 模块，然后重新运行流程”。

#### Extended `tool-status.json` schema
本阶段为 `tools` 数组各项添加以下字段（向后兼容）：
```json
{
  "tool": "",
  "command": "",
  "status": "FOUND | FOUND_PREFER_MODULE | MISSING | MISSING_LOAD_MODULE | PROPRIETARY_ONLY",
  "version": "",
  "path": "",
  "role": null,
  "dialect": null,
  "module_names": [],
  "versions_available": []
}
```

注：本阶段**原样保留**顶层 `python_env` 对象，只修改 `tools` 数组。`python3` 条目与其他工具相同：`python_env.type == "module"` 时，数组内状态从 `FOUND` 升级为 `FOUND_PREFER_MODULE`，并纳入 `load-modules.sh`。`tool_discovery` 写入的 `version`、`role`、`dialect` 也原样保留。本阶段只添加模块字段，并可能改变 `status`。

### QoR Metrics to Evaluate
- `module_system_detected`：布尔值，`module_system` 不为 `"none"` 时为 true；自定义 Wrapper 也算
- `module_listing_ok`：布尔值，`module_listing` 为 `"LISTED"` 时为 true。只有此时 `tools_found_via_modules: 0` 才有意义；false 时该数量无法说明主机提供哪些工具
- `tools_found_via_modules`：状态为 `MISSING_LOAD_MODULE` 或 `FOUND_PREFER_MODULE` 的工具数

### Stage Output Summary
Print a human-readable table before advancing:
```text
Module system     : custom - $MODULESHOME=<site path>, no modulecmd in PATH, no init/bash
Module listing    : LISTED via `. "$MODULESHOME/module.sh"; module avail` (3813 entries, 160s)
Tools in PATH     : 12
Tools via modules : 5
  vcs        — selected synopsys/vcs/2021.01 (highest_release, 2 candidates); also 2020.03
  xrun       — selected cadence/xcelium/20.09 (site_default, 1 candidate)
  dc_shell   — selected synopsys/dc/2022.03 (site_default, 3 candidates); also 2021.06, 2020.09
  innovus    — selected cadence/innovus/21.1 (highest_release, 2 candidates); also 20.12
  pt_shell   — selected synopsys/primetime/2022.06 (site_default, 2 candidates); also 2021.06
```

始终打印选择依据和候选数量。`site_default` 比最新版本旧数个版本是正常且预期的情况；`highest_prerelease` 才是需要关注的结果。

调用阶梯耗尽时，第二行打印 `Module listing    : UNAVAILABLE (<module_listing_error>)`，`Tools via modules` 数量打印为 `not surveyed`，不能打印 `0`，否则会被误解为已检查且主机未提供模块。

### Output Required
- `module-status.json`
- 更新后的 `tool-status.json`
- `load-modules.sh`：任一工具状态为 `FOUND_PREFER_MODULE` 或 `MISSING_LOAD_MODULE` 时生成；没有符合工具时省略。不能仅按 module_system 推断省略：module_system 为 none，或已检测到系统但 module_listing 为 UNAVAILABLE 时均无符合工具；后者须报告 WARN，不能干净跳过。

`module-status.json` 数据结构：
```json
{
  "module_system": "tclmod | custom | none",
  "module_system_detail": "<evidence: $MODULESHOME value, whether modulecmd was in PATH, what was found under $MODULESHOME>",
  "module_system_version": "",
  "module_listing": "LISTED | UNAVAILABLE",
  "module_invocation": "<the ladder rung that produced the listing, verbatim, or null>",
  "module_listing_error": null,
  "tools_via_modules": [
    {
      "tool": "<command>",
      "module_names": ["synopsys/vcs/2020.03", "synopsys/vcs/2021.01"],
      "versions_available": ["2020.03", "2021.01"],
      "selected": "synopsys/vcs/2021.01",
      "selected_basis": "site_default | highest_release | highest_prerelease",
      "candidates": 2
    }
  ]
}
```

`tools_via_modules: []` 也可能表示列表获取失败，不能据此断定主机没有模块；此时须记录 module_listing 和 module_listing_error，并报告 WARN。

`module_system` 表示安装了什么，`module_listing` 表示 `tools_via_modules` 是否可信。两者独立：`tclmod` 主机可以是 `UNAVAILABLE`，`custom` 主机可以是 `LISTED`。`module_system: "none"` 始终配合 `module_listing: "UNAVAILABLE"` 和 `module_listing_error: "no module system present"`，使所有情况下均可通过一个字段判断可信性。

`load-modules.sh` format:
```bash
#!/usr/bin/env bash
# Generated by module_discovery — source this file to load EDA tool modules
# Usage: source load-modules.sh

module load synopsys/vcs/2021.01       # selected: highest_release; alternatives: 2020.03
module load cadence/xcelium/20.09
# module load cadence/innovus/21.1     # uncomment if needed
```

---

## Stage: tool_installation

### Domain Rules
1. **绝不自动安装**，仅生成逐工具安装脚本。

2. 缺少 `python3` 时立即 FAIL 并升级处理，所有 Wrapper 都依赖它。

3. 为每个 `MISSING` 工具生成一个 `install-<toolname>.sh`；跳过 `FOUND`、`FOUND_PREFER_MODULE`、`MISSING_LOAD_MODULE`、`PROPRIETARY_ONLY`。

4. 每个脚本遵循下方 Per-Tool Script Structure。

5. 使用包名映射表，为检测到的操作系统/包管理器输出正确安装命令。

6. **Python 包安装脚本**（`openlane`、`cocotb`、`uv`）：读取 `tool-status.json` 中的 `python_env.exec` 替换 `<PYTHON_EXEC>`，以 `python_env.bin_dir` 替换 `<PYTHON_BIN_DIR>`。每个脚本顶部输出：
   ```bash
   PYTHON_EXEC="<PYTHON_EXEC>"
   PYTHON_BIN_DIR="<PYTHON_BIN_DIR>"
   ```
   安装使用 `"$PYTHON_EXEC" -m pip install <package>`；`python_env.type` 为 `custom` 或 `module` 时，绝不能直接用 `pip install`。

7. 专有工具不生成脚本，仅在签核摘要中记录说明。

8. modulefile 始终使用经典 TCL（无文件扩展名），无条件生成；可能需适配的 modulefile 仍比没有更有用。每种 `module_system` 对应一种警告：`tclmod` 不警告，Environment Modules 能读经典 TCL；`none` 或 `custom` 按下方 Per-Tool Script Structure 的 WARN 文字处理，但两者仍生成 modulefile。

9. 每个脚本末尾按 `module_system` 输出注册指引：
   - `tclmod`：若尚未存在，将 `$EDA_MODULEFILES_ROOT` 注册到 `$MODULEPATH`。
   - `module_system == "custom"`：说明站点 Wrapper 以自身方式注册 modulefile，可能完全不读 `$MODULEPATH`；注册机制须参考站点自身文档，不能将 `$MODULEPATH` 行当作操作指令。
   - `none`：说明目前没有可注册的模块系统，安装 Environment Modules 后才适用 `$MODULEPATH` 行。

10. 将全部 `install-<toolname>.sh` 写入 `install-missing-tools/`，目录不存在时创建；没有 MISSING 工具时，不创建目录或任何脚本。

### QoR Metrics to Evaluate
- `install_scripts_generated`：写入 `install-missing-tools/` 的 `install-<toolname>.sh` 数量；每个 `MISSING` 工具一个，等于 `tools_missing`；没有缺失工具时为 `0`。

### Common Issues & Fixes
| Issue | Fix |
|---|---|
| python3 不存在 | 立即 escalate，wrapper 全依赖 Python |
| `openroad` (OpenROAD): build required | Refer to https://github.com/The-OpenROAD-Project/OpenROAD |
| `bambu-hls` (Bambu HLS): Linux only | Wrap with `status: WARN` on macOS/Windows |

### Install Directory Layout
```text
$EDA_TOOLS_ROOT/                         # 默认 /tools
  <toolname>/<version>/
$EDA_MODULEFILES_ROOT/                   # 默认 /tools/toolmgr/env/modulefiles
  <toolname>/<version>
```

### Per-Tool Script Structure

每个 `install-<toolname>.sh` 的 modulefile 路径为 `$EDA_MODULEFILES_ROOT/<toolname>/<version>`（TCL，无扩展名）：

```bash
#!/usr/bin/env bash
# install-<toolname>.sh — generated by infrastructure-orchestrator
# Installs <Tool Full Name> to $EDA_TOOLS_ROOT/<toolname>/<version>
# and generates a TCL modulefile at $EDA_MODULEFILES_ROOT/<toolname>/<version>
set -euo pipefail

TOOL_NAME="<toolname>"
TOOL_VERSION="<detected-or-latest>"
EDA_TOOLS_ROOT="${EDA_TOOLS_ROOT:-/tools}"
EDA_MODULEFILES_ROOT="${EDA_MODULEFILES_ROOT:-/tools/toolmgr/env/modulefiles}"
INSTALL_DIR="${EDA_TOOLS_ROOT}/${TOOL_NAME}/${TOOL_VERSION}"

# --- Install ---
# Build-from-source: pass --prefix="${INSTALL_DIR}" to configure/cmake
# Package manager: use apt-get/brew/pacman (see mapping table below)

# --- Generate TCL modulefile ---
MODFILE_DIR="${EDA_MODULEFILES_ROOT}/${TOOL_NAME}"
mkdir -p "${MODFILE_DIR}"

cat > "${MODFILE_DIR}/${TOOL_VERSION}" <<EOF
#%Module1.0
proc ModulesHelp { } {
    puts stderr "<Tool Full Name> ${TOOL_VERSION}"
}
module-whatis "<Tool Full Name> ${TOOL_VERSION} — <one-line description>"

set prefix ${INSTALL_DIR}
prepend-path PATH            \$prefix/bin
prepend-path LD_LIBRARY_PATH \$prefix/lib
prepend-path MANPATH         \$prefix/share/man
# add PYTHONPATH, PKG_CONFIG_PATH, or tool-specific setenv as needed
EOF

echo "Modulefile written: ${MODFILE_DIR}/${TOOL_VERSION}"

# --- Register modulefiles root (if not already set) ---
# tclmod only — see rule 9 for custom and none:
# export MODULEPATH=${EDA_MODULEFILES_ROOT}:${MODULEPATH}
# Add the above line to ~/.bashrc or /etc/profile.d/eda-modules.sh
```

所有情况下仍生成 modulefile 块，并在阶段输出中按以下条件报告 WARN：
- `module_system == "none"`：“未检测到模块系统，无法自动加载模块；安装 Environment Modules 后可使用生成的 modulefile”。
- `module_system == "custom"`：“生成的 modulefile 为TCL classic（经典 TCL）格式；检测到的是站点 Wrapper，尚未确认是 Environment Modules，可能无法读取此格式。查看 module-status.json 中的 module_system_detail；若 module load 失败，将 modulefile 适配为站点格式”。

**Modulefile 内容规则：**
- 每个 modulefile 至少设置 `PATH`、`LD_LIBRARY_PATH`
- 适用时添加 `MANPATH`、`PKG_CONFIG_PATH`、`PYTHONPATH`
- 工具特有根变量（存在时设置）：按命令名，即 `tool-status.json` 中的 `tool` 值匹配，不按括号中的产品名匹配。Python 包使用包名，所以 cocotb 行匹配 `cocotb`，而非探测命令 `cocotb-config`：
  - `verilator`（Verilator）→ `VERILATOR_ROOT`
  - `yosys`（Yosys）→ `YOSYS_DATDIR`
  - `llvm-config`（LLVM）→ `LLVM_DIR`
  - `cocotb`（Python 包）→ `COCOTB_SHARE_DIR`

### Package Name Mapping Table

包名与安装命令保留原始英文，避免改变执行语义。

| Tool command | apt package(s) | brew formula | pacman pkg | fallback / notes |
|---|---|---|---|---|
| `verilator` | `verilator` | `verilator` | `verilator` | — |
| `slang` | build-from-source | — | — | https://github.com/MikePopoloski/slang |
| `surelog` | build-from-source | — | — | https://github.com/chipsalliance/Surelog |
| `sv2v` | build-from-source | — | — | https://github.com/zachjs/sv2v |
| `iverilog` | `iverilog` | `icarus-verilog` | `iverilog` | — |
| `yosys` | `yosys` | `yosys` | `yosys` | — |
| `abc` | build-from-source | `berkeley-abc` | — | https://github.com/berkeley-abc/abc |
| `openroad` | build-from-source | — | — | https://github.com/The-OpenROAD-Project/OpenROAD |
| `openlane` | `<PYTHON_EXEC> -m pip install openlane` | `<PYTHON_EXEC> -m pip install openlane` | `<PYTHON_EXEC> -m pip install openlane` | Python 包；将 `<PYTHON_EXEC>` 替换为 `tool-status.json` 的 `python_env.exec` |
| `klayout` | `klayout` | `klayout` | `klayout` (AUR) | — |
| `sta` | build-from-source | — | — | https://github.com/The-OpenROAD-Project/OpenSTA |
| `sby` | `symbiyosys` | — | — | https://github.com/YosysHQ/sby |
| `gem5` | build-from-source | — | — | https://github.com/gem5/gem5 |
| `bambu-hls` | 厂商下载（仅 Linux） | — | — | https://github.com/ferrandi/PandA-bambu; macOS/Windows 报 WARN |
| `nextpnr` | `nextpnr-ice40 nextpnr-ecp5` | `nextpnr` | `nextpnr` | — |
| `openFPGALoader` | `openfpgaloader` | — | — | https://github.com/trabucayre/openFPGALoader |
| `cocotb` | `<PYTHON_EXEC> -m pip install cocotb` | `<PYTHON_EXEC> -m pip install cocotb` | `<PYTHON_EXEC> -m pip install cocotb` | Python 包；使用 `<PYTHON_BIN_DIR>/cocotb-config` or `cocotb-config` 检测 |
| `llvm-config` | `llvm-dev` | `llvm` | `llvm` | — |
| `gcc` | `build-essential` | `gcc` | `gcc` | — |
| `openocd` | `openocd` | `open-ocd` | `openocd` | — |
| `xschem` | `xschem` | build-from-source | — | https://github.com/StefanSchippers/xschem |
| `gtkwave` | `gtkwave` | `gtkwave` | `gtkwave` | — |
| `uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` (standalone) or `<PYTHON_EXEC> -m pip install uv` | `uv` (brew) or `<PYTHON_EXEC> -m pip install uv` | `<PYTHON_EXEC> -m pip install uv` | 优先独立 astral.sh 安装器；激活 custom/module Python 时可回退 pip |

### Output Required
- 每个 MISSING 工具一个 `install-<toolname>.sh`，写入 `install-missing-tools/`

---

## Stage: wrapper_deployment

### Domain Rules
1. 将全部 25 个 Wrapper 脚本部署到 `plugins/infrastructure/tools/`
2. 对每个 Wrapper 运行 `chmod +x`；权限被拒绝时判为 FAIL，并以 `sudo chmod +x` 指引升级处理
3. 无论退出码如何，每个 Wrapper 均须输出符合下方数据结构的 JSON
4. 部署后使用 `--version` 或 `--help` 检查每个 Wrapper；允许工具 MISSING，Wrapper 必须以 `status: "FAIL"` 妥善处理工具不存在。`--version` 不产生设计结果，因此返回 `status: "WARN"`、`verified: false` 是预期结果，证明 Wrapper 可以运行并输出合法 JSON。`wrap-verilator-sim.sh` 接收仿真可执行文件而非工具参数，所以自行处理 `--version` / `--help` 并返回同样 WARN。此检查出现 FAIL 因而始终表示工具缺失或 Wrapper 损坏，而非调用方式错误。
5. 绝不隐藏工具原始退出码
6. 未获得结果时绝不报告 PASS：Wrapper 未识别出工具输出结果时，即使工具退出 0，也报告 WARN 且 `verified: false`。

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
- `wrappers_deployed`：已设置可执行位的 Wrapper 数量（目标：11）

### Output Required
- plugins/infrastructure/tools/ 中的 11 个可执行 Wrapper 脚本

---

## Stage: mcp_configuration

### Domain Rules
1. 输出 10 个工具服务器（8 个批处理、2 个会话）的 MCP 配置片段。另解析可选 `chip-design-memory` 服务器的 `mcp-memory.json` 路径；该服务器提供编排器语义经验查询使用的 `query_experiences`，不属于工具服务器、不计入数量，因此 `plugins/infrastructure/mcp/` 共 11 个文件。
2. 所有批处理配置使用 `"command": "python3"` 配合 `mcp-adapter.py`；绝不能直接将 Wrapper 脚本设为 command，因为 Wrapper 不是 MCP 服务器。
3. 会话配置使用 `mcp-session-adapter.py`，参数为 `--tool openroad` 或 `--tool opensta`；`mcp-memory.json` 直接运行 `mcp-memory.py`，不使用 `--wrapper` 或 `--tool`。
4. 运行时用 `realpath` 或 `pwd` 解析适配器、Wrapper 和 `mcp-memory.py` 的绝对路径，输出片段绝不能保留 `/absolute/path/to/` 占位符。安装器不会代为处理：`install.sh`、`install.ps1`、`bin/install.mjs` 均不修改 MCP 配置。
5. 打印每个片段并明确提示：“将 `mcpServers` 块粘贴到 `.claude/settings.json`”。
6. 将片段文件写入 `plugins/infrastructure/mcp/`
7. 不得自动修改 `.claude/settings.json`；由用户手工操作。

### MCP Config Templates
`command` 始终为 `python3`，首个参数为 MCP 服务器脚本，绝不能是 `wrap-*.sh`（规则 2）。每个工具的 `--description` 和 `env` 以 `plugins/infrastructure/mcp/` 中的文件为准；修改路径，不改变结构。

批处理（Tier 1）：`mcp-adapter.py` 运行 `--wrapper` 指定的 Wrapper：
```json
{
  "mcpServers": {
    "<tool>": {
      "type": "stdio",
      "command": "python3",
      "args": [
        "/absolute/path/to/plugins/infrastructure/tools/mcp-adapter.py",
        "--wrapper", "/absolute/path/to/plugins/infrastructure/tools/wrap-<tool>.sh",
        "--tool", "<tool>",
        "--description", "<what the tool returns>"
      ],
      "env": {
        "TOOL_TIMEOUT_S": "300"
      }
    }
  }
}
```

会话（Tier 2）：`mcp-session-adapter.py` 保持工具进程存活：
```json
{
  "mcpServers": {
    "openroad-session": {
      "type": "stdio",
      "command": "python3",
      "args": [
        "/absolute/path/to/plugins/infrastructure/tools/mcp-session-adapter.py",
        "--tool", "openroad"
      ],
      "env": {
        "SESSION_TIMEOUT_S": "120"
      }
    }
  }
}
```

Memory (optional) — `mcp-memory.py` is the server itself:
```json
{
  "mcpServers": {
    "chip-design-memory": {
      "type": "stdio",
      "command": "python3",
      "args": [
        "/absolute/path/to/plugins/infrastructure/tools/mcp-memory.py"
      ],
      "env": {}
    }
  }
}
```

### QoR Metrics to Evaluate
- `mcp_servers_configured`：已写入的工具服务器配置片段数（目标：10；`mcp-memory.json` 可选，不计入）。

### Output Required
批处理 MCP 配置（Tier 1）：
- `plugins/infrastructure/mcp/mcp-yosys.json`
- `plugins/infrastructure/mcp/mcp-openroad.json`
- `plugins/infrastructure/mcp/mcp-opensta.json`
- `plugins/infrastructure/mcp/mcp-klayout.json`
- `plugins/infrastructure/mcp/mcp-verilator.json`
- `plugins/infrastructure/mcp/mcp-bambu.json`
- `plugins/infrastructure/mcp/mcp-gem5.json`
- `plugins/infrastructure/mcp/mcp-symbiflow.json`

会话 MCP 配置（Tier 2）：
- `plugins/infrastructure/mcp/mcp-openroad-session.json`
- `plugins/infrastructure/mcp/mcp-opensta-session.json`

可选记忆服务器配置（非工具服务器，不计数量）：
- `plugins/infrastructure/mcp/mcp-memory.json`

适配器脚本（必需，缺少则 MCP 服务器无法启动）：
- `plugins/infrastructure/tools/mcp-adapter.py`
- `plugins/infrastructure/tools/mcp-session-adapter.py`

为每个工具打印已解析绝对路径的 MCP 配置片段

---

## Stage: environment_validation

### Domain Rules

**关键路径工具**指 `tool-status.json` 中 `tool` 为 `yosys`、`verilator`、`openroad` 或 `sta` 的条目，分别对应 Yosys、Verilator、OpenROAD、OpenSTA。下方规则均匹配**该命令键而非产品名**。OpenSTA 命令为 `sta`，匹配 `"OpenSTA"` 会找不到条目，无法判断工具缺失；用于 FAIL 门控时会导致静默通过。

1. 首先验证 `python_env`：
   - type=module：`which python3` 确认 module 仍 active，否则立即 FAIL 并提示 source `load-modules.sh`
   - type=custom/system：确认当前 python3 path 与 `python_env.exec` 一致，不一致 WARN
2. 严格按 `tool_discovery` 规则 2–3 重新检查工具存在性，包括 PATH 回退及 `python_env.type` 分支。不同检测方式会在真实安装上产生静默分歧：
   - `openlane`：使用 `"$PYTHON_EXEC" -m pip show openlane`，规则 3 对它没有回退。
   - `cocotb`、`uv`：custom/module 类型先尝试 `"$PYTHON_BIN_DIR/<tool>"`，再回退 PATH 命令；system 类型只用 PATH，不构造 `$PYTHON_BIN_DIR` 探测。
   在 `tool-manifest.json` 的 `resolved_via` 记录解析路径。custom/module 类型通过 PATH 回退找到包时，报告 WARN：“<tool> 从 PATH 的 <path> 解析，位于当前 Python bin 目录 <python_env.bin_dir> 之外，可能使用不同于 <python_env.exec> 的解释器”；修复指引为确认解释器或以 `"$PYTHON_EXEC" -m pip install <tool>` 重装到当前环境。工具确实存在，不能判缺失。
   此风险很常见：`tool_installation` 优先使用 astral.sh 独立 uv 安装器，安装前缀并非 `$PYTHON_BIN_DIR`；参考主机的 uv 就位于与解释器无关的共享 bin 目录。system 类型的 PATH 就是当前环境，绝不报此 WARN。
   与 `tool-status.json` 比较，该文件由 tool_discovery 写入、module_discovery 原地更新，是此时唯一工具记录。不能与本阶段输出 `tool-manifest.json` 比较，因为尚无内容可比。本阶段只读 tool-status.json；分歧为 WARN，不降级工具状态。

3. 确认全部 25 个 Wrapper 脚本存在并设置可执行位。

4. 确认 `plugins/infrastructure/mcp/` 中全部 10 个工具服务器片段存在（`mcp-memory.json` 可选，缺少不判 FAIL），以及 tools 目录中的 `mcp-adapter.py` 和 `mcp-session-adapter.py` 存在。

5. 关键路径工具（`yosys`、`verilator`、`openroad`、`sta`）仍为 MISSING 时判 FAIL 并升级，不能回退 `tool_installation`。该阶段仅生成 `install-<toolname>.sh` 而不执行（规则 1），重试无法改变状态。报告缺失命令，要求用户审查并运行 `install-missing-tools/` 中生成的脚本，再重新运行 `environment_validation`。

6. `MISSING_LOAD_MODULE` 的工具发 WARN，并提示 source `load-modules.sh` 后重跑。
7. **命令方言冲突检查（Dialect-conflict check）：** 将状态为 `FOUND`、`FOUND_PREFER_MODULE`、`PROPRIETARY_ONLY` 或 `MISSING_LOAD_MODULE` 的工具按 `role` 分组，忽略 role=null 的条目。MISSING_LOAD_MODULE 也计入，因为用户将加载它并构建命令行，正是此检查要提醒的情况；仅排除 MISSING。每个包含至少两种不同 dialect 且至少一个 PROPRIETARY_ONLY 工具的 role，报告**一条** WARN。不能逐工具对报告，五成员角色会产生十条同义警告而被忽视。
   description：“role <role> 中工具使用不同命令方言：<tool_a> (<dialect_a>)、<tool_b> (<dialect_b>)、…，命令行无法在它们之间移植”。fix：“为该流程每个角色选择一种方言，并使用该厂商选项构建命令行，不跨方言复用命令行”。一条说明列出全部成员，`dialect_conflicts` 记录此类**角色数**，不是工具对或工具数。仅 WARN，绝不使阶段 FAIL，也不阻止 environment.signoff。共存正常，假定可互换才有风险；要求至少含一个专有工具，可避免几乎所有主机的两个开源仿真器都产生无用警告。

8. 任一关键路径工具（`yosys`、`verilator`、`openroad`、`sta`）为 MISSING_LOAD_MODULE 时，报告 WARN 并设置 `suggested_next_step: "escalate"`，提示“关键工具 <tool> 必须加载模块后下游才能运行；source load-modules.sh 并重跑 environment_validation”。

9. **仿真器编译冒烟检查（Simulator compile smoke test，主动启用）：** 由布尔值 `design_state.pipeline_config.simulator_smoke_test` 控制，缺失或 false 为默认关闭。编译占用许可证，而 tool_discovery/tool_installation 不占用，因此只能显式启用后运行。
   - **关闭（默认）：** WARN，说明“仿真器调用未经验证”，修复指引为设置 `design_state.pipeline_config.simulator_smoke_test = true`；绝不因此 FAIL。
   - **启用：** 对 tool-status.json 中 role=rtl_simulator 且状态为 FOUND 或 FOUND_PREFER_MODULE 的每个工具，通过 Wrapper 编译一个三行占位模块（`module adice_smoke_test; endmodule`）。vcs 使用 `wrap-vcs-compile.sh`，xrun 使用 `wrap-xrun-compile.sh`，verilator 使用 `wrap-verilator-lint.sh`。vsim 与 iverilog 无 Wrapper，记录 UNVERIFIED 且无命令，与未探测的专有工具相同。读取 Wrapper 自身 status，不能只看退出码：本主机 innovus、vsim、voltus 的 -version 都曾退出 0 却报许可证过期、共享库缺失或平台安装错误。
     - `status: "FAIL"`：阶段 FAIL，工具无法编译简单模块。
     - `status: "WARN"`、`verified: false`，且 warnings 显示许可证队列或超时：WARN 而非 FAIL，使许可证不足的站点仍可签核。
     - `status: "PASS"`，或 WARN 且 `verified: true`：冒烟检查通过。
   在 tool-manifest.json 的 `simulator_smoke_test.results` 中，将每个探测仿真器记录为 `{tool, status, verified}`。

10. 打印最终签核摘要：发现的工具、模块提供的工具、已部署 Wrapper、已配置 MCP 服务器及仿真器冒烟检查结果。

### QoR Metrics to Evaluate
- `dialect_conflicts`：由规则 7 计算，检测到同一角色下至少两种不同 `dialect`，且至少一个工具为 `PROPRIETARY_ONLY` 的**角色**数量（非工具对数量）。仅 WARN，不阻止签核。
- `simulator_smoke_tests_run`：启用 `pipeline_config.simulator_smoke_test` 时，规则 9 实际执行编译检查的 `rtl_simulator` 工具数；关闭或无 FOUND 工具时为 `0`。逐工具编译 FAIL 通过规则 9 的阶段 FAIL 路径报告，不通过此数量表示。

本阶段其余结论记录在 `tool-manifest.json`（Output Required）中，而非 QoR 计数：Python 环境存活情况、Wrapper 可执行位、MCP 文件存在性及关键路径检查。

### Sign-off Checklist
- [ ] `tool-status.json` 已写，包含 `python_env`
- [ ] `module-status.json` 已写
- [ ] 所有 MISSING tool 都有 install script
- [ ] 有 module 工具时生成 `load-modules.sh`
- [ ] 本阶段已写入 tool-manifest.json，符合 Output Required 数据结构
- [ ] 全部 25 个 Wrapper 已部署且可执行
- [ ] 仿真器编译冒烟检查已运行并记录，或明确以 WARN 标为未经验证（由 design_state.pipeline_config.simulator_smoke_test 控制）
- [ ] 两个 MCP adapter 存在
- [ ] 全部 10 个工具服务器 MCP 片段已写入、使用解析后的绝对路径且已打印
- [ ] Critical-path tool 不得是 MISSING/MISSING_LOAD_MODULE
- [ ] tool-status.json 每项均记录 role 和 dialect，所有涉及专有工具的同角色不同方言共存均已报告

### Output Required
- 环境验证报告
- `tool-manifest.json`：由本阶段创建。此前没有 manifest 可更新，因为前面的阶段均不生成它。

`tool-manifest.json` 是**验证凭据，而非工具列表**。它记录本阶段测量结果，并引用逐工具状态而非复制；`tool-status.json` 已保存所有逐工具字段（`tool`、`command`、`status`、`version`、`path`、`role`、`dialect`、`module_names`、`versions_available`）及 `python_env`，`module_discovery` 也已确立后续阶段原地更新该文件而非另建副本的方式。重复这些字段会让同一事实产生第二个权威来源。

本阶段确认了 `tool-status.json` 无法表达的内容：`python_env` 的**存活情况**（记录的模块可能已卸载、`exec` 可能已不匹配）、Wrapper 可执行位、MCP 产物存在性、计算出的方言冲突集合及签核结论：

```json
{
  "run_id": "",
  "timestamp": "<ISO-8601>",
  "host": "",
  "tool_status_source": "tool-status.json",
  "python_env_live": {
    "type": "module | system | custom | venv",
    "exec_expected": "",
    "exec_actual": "",
    "matches": false
  },
  "python_packages": [
    {
      "tool": "",
      "resolved_via": "python_env_bin_dir | path | pip_show",
      "path": ""
    }
  ],
  "wrappers": { "expected": 25, "executable": 0, "missing": [] },
  "mcp": { "snippets_expected": 10, "snippets_present": 0, "adapters_present": false, "missing": [] },
  "dialect_conflicts": [
    { "role": "", "members": [ { "tool": "", "dialect": "" } ] }
  ],
  "simulator_smoke_test": { "enabled": false, "results": [] },
  "critical_path": { "required": ["yosys", "verilator", "openroad", "sta"], "missing": [] },
  "signoff": false
}
```

`python_packages[].resolved_via` 是规则 2 WARN 的记录依据，使“已找到但位于当前环境之外”在运行后可审计，而非只打印。`dialect_conflicts` 列出每个角色的成员，不只是规则 7 的数量，无需重新推导即可回读冲突。`simulator_smoke_test.results` 是 `{tool, status, verified}` 列表，规则 9 探测的每个 `rtl_simulator` 工具一项，用于区分许可证排队 WARN 和门控关闭导致的未探测。