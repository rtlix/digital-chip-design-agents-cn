# 变更记录

## [Unreleased]


### 商业 RTL→GDS：Sky130 三流程对比的实测 Tool Notes

下面“商业 RTL→GDS 脚手架”中的概念性说明，现已替换为真实命令和实测失败模式。测试环境是一台
8 vCPU / 15 GB 主机，对约 3 万 cell、10 个 SRAM macro 的 Sky130 CPU macro 分别执行
DC-NXT → ICC2、Genus → Innovus，并以 OpenROAD/LibreLane 为参考，使用
StarRC + PrimeTime/PrimePower 统一评估，Formality/Conformal 做等价验证，
Magic/KLayout/Netgen 做物理检查，RedHawk 做 IR/EM。
所有 Tool Notes 都注明实测工具版本；未实测内容不会被写成“可直接照做”的 recipe。

插件版本：
`chip-design-pd`、`-sta`、`-synthesis`、`-formal` 从 1.3.0 升到 1.4.0；
`chip-design-infrastructure` 从 1.4.0 升到 1.5.0；
其他领域因 Memory-root 文案更新做 patch bump。

#### 新增

- **PD：`## PDK Enablement` → “Measured on Sky130”**
  - `lc_shell` 在 `read_lib` 完成后可能于进程退出阶段 segfault，必须根据生成物 read-back 判断，而不能只看 exit code。
  - 从 tech LEF 构造 `.tf` 时处理 LIB-007、gapless mask、各 block routing direction。
  - ICC2 multi-corner 使用一个 **multi-pane NDM**，并运行 `check_workspace -allow_missing`。
  - 记录 `grdgenxo` / `Techgen` runtime。
  - 修复 `generateCapTbl` 把 li1 当 POLY 的问题，以及 ICT 中 `li1 → met0` 映射。
  - 增加 StarRC vs OpenRCX correlation、RedHawk tech conversion、Genus/Innovus MMMC dialect 分离。

- **PD Tool Notes（实测）**
  - Innovus 23.14：每 view 使用 `-latency_file`；`update_io_latency false`；完整 MMMC 消除 ss reg-to-reg 漏检；
    `holdTargetSlack 0.2` 对冲实测约 0.17 ns 的 ff optimism；
    activity 0.2 vs 0.1；`create_inst` / `editAddRoute` 静默无效时改用
    `addInst -physical` / `add_shape`；`refinePlace` 必须先于 `ecoRoute`；
    antenna 修复采用 source 端 tap；记录 `npc.2` 等 rule。
  - ICC2 X-2025.06-SP1：`global_min_layer_mode hard`；fat-table 到 power strap 的 met4 spacing
    不会自动保证，因此增加 0.1 um halo；PVT pane selection；tt-only hold 可能形成弱 delay chain；
    `add_buffer` 后可能落到 row grid 外；支持 forced min-layer reroute；
    antenna ECO 可由 OpenROAD list 驱动；使用 `change_names -case_insensitive` +
    `write_verilog -exclude supply_statements`；cold startup 实测 30–65 min。
  - 新增 **StarRC**、**RedHawk** Tool Notes：
    `INSTANCE_POWER_FILES` 必须用复数；实例名建议 escape-free；
    `ENABLE_AUTO_EM 1`；PEAK-mode EM 不能直接判 PASS/FAIL；
    dynamic IR 与 decap 配置相关。
  - 新增 **Magic/KLayout/Netgen** 实测说明：部分 full-chip 检查约需 11 GiB，
    工具应单独运行；区分 SRAM footprint 和 `nwell.4` 等 artifact 类别。

- **STA**
  - 新增 PrimeTime X-2025.06 multi-corner judge recipe：每 library × RC corner 独立 session；
    SDC 以 md5 验证；pin-to-pin annotation gate；拒绝空 metric。
  - 记录 `read_sdc` 遇到首个 unsupported command 后会丢弃后续约束的风险，特别是 Innovus 导出的 SDC。
  - 区分工具自己写出的 SDC variant。
  - PrimePower activity 与 OpenSTA 对齐。
  - Fair-comparison rule 7：通过 md5 证明每次 judge 用到的输入；
    rule 8：implementation 必须在实际被 judge 的 corner 中 closure。

- **Synthesis**
  - DC-NXT X-2025.06-SP3：NDM 使用 `dcnxt_shell -topographical_mode`；
    TLU+；SVF；tt-only area recovery 可能生成 ripple adder，改为 MCMM。
  - Genus 23.14：记录 `syn_*` timing、缺 QRC tech file 时的 PHYS-1015、SDC-200。
  - 记录 peak RSS。

- **Formal**
  - 增加 Formality / Conformal Tool Notes：SVF 和 read order、Genus dofile 使用 `lec -xl`、
    `tclmode`、direct/flat confirmation、diode-stripped compare。
  - Flat netlist negative control 改为按结构定位 mutant anchor，不能依赖容易变化的 literal instance name。

- **Infrastructure**
  - 新增 *Licensed tools on a small shared host*：
    用 `flock` 替代 `pgrep` gate；
    启动前检查 load / memory，放进可 group-kill、带 MemoryMax 的 scope；
    线程数 ≤2；考虑共享 VM 上慢 license startup；长任务用 done-marker 等待。

- 将本轮 campaign 的经验蒸馏进
  `memory/{pd,sta,synthesis,formal,infrastructure}/knowledge.md`。

#### 变更

- 所有 domain Skill 都使用解析后的 `<MEM>` 根目录，而不是字面量 `memory/`。
- `wrap-innovus.sh` / `wrap-genus.sh` 的示例更新为实测调用：
  `innovus -nowin -files … -log … -overwrite`、
  `genus -no_gui -overwrite -f …`。

### 商业 RTL→GDS 脚手架：PD/signoff wrapper、extraction/IR stage 与公平对比

为在 open PDK 上引入商业流程并和 OpenROAD/LibreLane 公平比较，新增
DC/Genus/FC、Innovus/ICC2、StarRC/Quantus、PrimeTime/PrimePower、
RedHawk、Formality/Conformal 的基础设施和流程结构。
未实测部分明确标成 scaffolding，后续实测结果见上一节。

插件版本：
`chip-design-infrastructure` 1.3.0 → 1.4.0；
`chip-design-pd`、`chip-design-sta`、`chip-design-formal`、`chip-design-synthesis`
1.2.1 → 1.3.0。

#### 新增

- **11 个 wrapper（14 → 25）**：
  `wrap-dc.sh`、`wrap-genus.sh`、`wrap-innovus.sh`、`wrap-icc2.sh`
  （`WRAP_ICC2_TOOL=fc_shell`）、`wrap-pt.sh`、`wrap-starrc.sh`、
  `wrap-fm.sh`、`wrap-lec.sh`、`wrap-redhawk.sh`
  （`WRAP_REDHAWK_TOOL=totem`）、`wrap-magic.sh`、`wrap-netgen.sh`。
  与已有 wrapper 使用相同 contract。
  Message prefix 必须按行首匹配：Synopsys `Error:/Warning:` + code，
  Cadence `**ERROR:/**WARN:`，Conformal `// Error:`，避免把 “0 error(s)” 当错误。
  Formality 的 `FAILED/INCONCLUSIVE`、Conformal 的 `Non-equivalent/Abort`、
  Netgen 的 `Netlists do not match` 即使 exit 0 也判 FAIL。
  `wrap-starrc.sh` 判断 command file 指向的 SPEF 是否新鲜、是否有 `*SPEF` header 和 `*D_NET`，
  而不是只看 log。所有 wrapper 的 `--version` 不启动重工具。

- **PD 新增 `extraction` 与 `ir_em` stage**：
  `… routing → extraction → timing_optimization … → ir_em → signoff`。
  增加 annotation coverage gate、IR 前 PG-shape 检查以及 `## PDK Enablement`。
  包括每 corner `.lib→.db`（含 macro）、tech LEF → NDM、MMMC、
  authored ITF/ICT → `nxtgrd/qrcTech`，并和 OpenRCX/Magic correlation，
  以及 RedHawk tech 和开源 Magic/KLayout/Netgen deck。

- **STA Fair Cross-Tool Comparison**
  - 比较 flow 必须使用相同 SDC（记录 md5）、相同 extractor + tech、相同 STA engine、
    相同 activity assumption。
  - 工具自身报告仅标为 `native`，不能直接跨工具排名。
  - PrimeTime multi-corner / PrimePower outline。
  - 未 annotation 的 parasitic 以 `input_setup` FAIL。

- **Formal**：`lec_run` 增加 Formality 和 Conformal，并要求在相信 EQUIVALENT 前跑 mutated-netlist negative control。

- **Synthesis**：
  DC topographical、Genus（`read_mmmc`、`read_physical`、`syn_*`）、
  FC（`compile_fusion`）流程 outline。

- **Infrastructure**
  - 增加 `lc_shell`、`icc2_lm_shell`、`grdgenxo`、`quantus`、`Techgen`、
    `joules`、`redhawk`、`totem`、`calibre`、`pvs`、`magic`、`netgen`。
  - 第二台主机实测 version probe：Innovus 约 123 s、PrimeTime 约 120 s，
    因此 probe budget 从 60 s 提到 180 s。
  - Vendor launcher 的 `*_exec` child 可能在裸 `timeout` 后继续占 license，
    所以必须以 process group 运行。
  - ≤16 GB 主机一次只跑一个重 PD/STA tool。

- **QoR trends**：新增 `power_mw`、`runtime_s`、`peak_rss_gb`；
  PD 还增加 `hold_wns_ns`、`tns_ns`、`util_pct`、`wirelength_um`。

#### 变更

- `conformal` → `lec`，`starrc` → `StarXtract`；旧名字都不是实际 binary。
- Tempus/Voltus 作为 optional row；主机缺少时可用 PrimeTime/PrimePower + RedHawk。
- PD Agent sign-off criteria 新增 IR drop、EM、power、density。
- Comparison run（`pipeline_config.comparison_run`）允许 synthesis/PD 缺 area/power target，
  记录为 **“comparison run, no target”**，不升级为 spec_gap。
- maxTurns：synthesis 40→100，PD 100→150。
- PD/STA/Synthesis Skill 全部使用解析后的 `<MEM>`。

#### 修复

- `memory/formal/knowledge.md`：
  `sby --depth/--vacuity/--multiclock` 不是 CLI flag；
  depth/multiclock 属于 `.sby [options]`，vacuity 使用 cover/reachability 检查。
  删除 JasperGold 2024.12 console 中不存在的 `jg -allow_empty_cex`。
- `memory/synthesis/knowledge.md`：
  原文把 `compile_ultra` 错归到 Genus/Fusion Compiler；已纠正为 Design Compiler 命令。

### SpyGlass 与 Tessent：证明静态检查真的执行，并固化 Tessent 流程

本轮来自同一主机上的 SoC SpyGlass lint/CDC/RDC、Tessent scan+ATPG 和 Tessent MemoryBIST 实测。
这些工具都曾出现“exit 0，但实际上没有检查任何东西”的情况，因此新增 fail-capable contract。

#### 新增

- **rtl-design `cdc_rdc_analysis` rules 7–9**
  - CDC/RDC 只有在 negative-control design（未同步 crossing、已同步 crossing、跨域 async reset）
    能被正确识别时才算实际执行，否则阶段是 NOT RUN。
  - 实测 SpyGlass `cdc_verify_struct` 在全部 crossing rule 被跳过时仍 exit 0；
    日志出现 `Ac_license01`，请求 feature `cdc_adv_checker`，而 server 只列出 `Advanced_CDC`。
  - 必须解析 skipped-rule 与 license failure。

- **rtl-design `lint_check` rule 16**
  - First-party module 被 black-box 后，其 finding 数是 unknown，不是 0。
  - SpyGlass 遇到带 `string` 或 `real` parameter 的 module 可能 black-box，甚至把 SoC top 整体移除。
  - 修复方式是 line-count-preserving analysis copy，绝不能修改真实 RTL 来迁就 lint 工具。

- **DFT Skill：Siemens Tessent Tool Notes**
  - context-based scan insertion + ATPG。
  - legacy `add_scan_groups` 流程曾“成功退出但插入 0 个 cell”。
  - LibComp → `.tcelllib`、`dft_cell_selection` 人工筛选、MemoryBIST、TCD trap。
  - Batch 使用 `< /dev/null`、`-replace`，并清理 stale TSDB。

- **DFT fail-capable rules**
  - ATPG 6–8：pattern-subset simulation 必须明确是 subset；
    pattern testbench 必须能让 broken-scan-link netlist 失败；
    由同一 source 生成的两个模型不是独立验证。
  - BIST 6–8：按 fault class 做 detection；
    使用独立 golden model；
    fault proof 覆盖完整地址空间（关闭 `reduced_address_count`）；
    与自研 MBIST 做 like-for-like 比较。
  - scan insertion rule 10：只有架构明确要求某些 flop 不进 scan chain 时，才允许把 Scan DRC error 降为 warning。
  - DFT Orchestrator Behaviour Rule 10 指向这些 fail-capable check。

- **Seed knowledge**
  - `memory/dft`：Tessent 2025.4。
  - `memory/rtl-design`：SpyGlass X-2025.06（`mthresh`、license feature）以及 Cadence HAL `-NOHALSYNTH`。

#### 变更

- DFT `dft_architecture` rule 2：
  如果项目 DFT architecture 已固定 chain count，则该值优先；√(flip-flops) 仅在未指定时作为 fallback。
- 除 Infrastructure 外的 15 个 Orchestrator：
  如果解析后的 `knowledge.md` 不存在，继续流程但必须在 experience record 中明确记录，
  并提示 `memory_root.py --init`，不再静默忽略。

### 商业仿真器移植：VCS/Xcelium、Coverage Review 与“不要相信 exit code”

来自一个约 1100 个 testcase 的 Verilator-only cocotb regression 移植到
Synopsys VCS 与 Cadence Xcelium，并加入 code coverage。
`chip-design-verification` 和 `chip-design-infrastructure` 从 1.2.0 升到 1.3.0。

#### 新增

- **`wrap-cocotb-results.sh`、`wrap-urg.sh`、`wrap-imc.sh`（11→14 wrapper）**
  - `wrap-cocotb-results.sh` 不运行 simulator，只汇总 cocotb `results.xml`。
    failure/error >0、testcase=0、missing/empty/unparseable/stale 文件都判 FAIL。
    原因：cocotb 1.9.2 在 VCS/Xcelium 下即使 testcase 失败，`make` 也可能 exit 0。
  - `wrap-urg.sh` 解析 VCS Y-2026.03 实测格式的 `dashboard.txt` 并拒绝 stale report。
  - `wrap-imc.sh` 会在 PATH 之外继续查找 `$XCELIUM_HOME/tools/bin` 等目录；
    如果 Xcelium 安装本身没有 IMC，则报告 clean tool-missing，而不是伪造 coverage。

- **Verification port mode + `simulator_portability` stage**
  `simulator_portability → coverage_analysis → regression_signoff`。
  包括 cocotb `SIM` 与 make variable、Verilator→VCS/Xcelium flag translation、
  单一 SIM-gated make include、`make -n + cmp -s` 证明 reference simulator 未被改动、
  per-simulator `SIM_BUILD`、LRM strictness triage、每 simulator negative control、
  staged scope 以及按 testcase 名称匹配 skip set。
  新 simulator 暴露的 RTL LRM defect 必须走 `fix_request`，不能用 TB workaround 掩盖。

- **Coverage mechanics**
  - VCS / Xcelium / Verilator 命令表。
  - DUT scope/exclusion。
  - 每 test 唯一 coverage DB，merge 后再 report。
  - 新增 report-only mode：禁止两个 coverage loop-back，只输出排序后的 hole list。

- **Turn cap**
  - DFT Orchestrator 50→150。
  - RTL Design Orchestrator 60→120。
  - 原因是实测单个 scoped Tessent task 和几个小型 RTL fix task 会在旧 cap 前被截断。
  - Long-Running Jobs 已支持 checkpoint/resume，提升 cap 只是避免报告前被强制切断。

- **RTL Lint Gate item 10**
  - 使用 CI 实际运行的工具版本，并检查 CI 实际编译的所有文件。
  - 实测 CI 注释写 Verilator 5.036，但 CI 实际是 5.048，新版 `PROCASSINIT` warning
    会使 `-Wall` 下 behavioral SRAM model 失败。
  - 版本来自 CI log/lockfile，而不是 README/comment。
  - CI 会编译的 testbench/model 同样纳入 gate。
  - 本地无法使用对应版本时必须构建或标记 NOT RUN。
  - power-up value 使用 `initial` block，不使用 declaration initializer，也不写到 `always_ff` target。

- **Multi-top coverage merge**
  - cocotb 不同 suite 有不同 top；plain `urg -dir a.vdb b.vdb` 会静默只保留第一个 database 的 design。
  - 使用 `urg -lca ... -flex_merge modules`。
  - 每 build 的 `-cm_hier` 以 `+filelist` 开头。
  - URG 全部 metric 为 `--` 即使 exit 0 也属于 NOT RUN；`wrap-urg.sh` 返回 unverified WARN。
  - VCS 对 generate-loop iteration 的 line/branch 计数方式与 Verilator 不同，
    waiver/exclusion 未翻译前不能直接比较 hole 数量。

- **Regression license / resource rules**
  - compile-and-run license smoke + timeout。
  - Xcelium `-licqueue` 无 seat 时可能一直等待。
  - job bound = `min(cores, RAM / peak, seats)`。
  - 检查 `sim_build` free space。
  - 长 regression 后台分 shard，并写入 `run_state.md` 以恢复。

- **Infrastructure**
  - 新增 `urg/imc`，role=`coverage_report`。
  - 新增 `coverage_reporting_gaps`。
  - environment validation 增加 regression resource 记录。
  - cocotb 版本必须从 CI line 获取，并检查 1.x/2.x API 差异。
  - csh activation script 防止 `prompt: Undefined variable`。

- **VCS/Xcelium 实测移植问题**
  - `xrun -defparam` 会忽略 string parameter（`*W,BDDSTR`），应通过 generated `defparam` top。
  - VCS `-pvalue+` string 还需额外 shell escaping，否则出现 `PRM_ILLG`。
  - Xcelium 绝不能在 make command line 上覆盖 `EXTRA_ARGS`。
  - Verilator 的 `-I` 除 include 外也会帮助找 module；VCS/Xcelium 需同步为 `-y/+libext+`。
  - 4-state `X` 来自 undriven input / unwritten state 时属于 TB defect。
  - 使用单一 VPI hierarchy-access helper。
  - Verilator 接受但 VCS 按 LRM 拒绝的问题（如 use-before-declare、LRM 9.2.2.4 `ICPD`）属于 RTL defect。
  - Verilator-only test 在商业 simulator 对比时记 NOT RUN，不能计入 pass floor。
  - Reference simulator 不存在时，`make -n` parity proof 使用 stub。
  - 每 run 独立 results file，防止 rollup/concurrent collision。
  - 仿真环境使用 UTF-8 locale。
  - 长任务使用后台 notification 或每 turn 一次 bounded wait，不能 busy polling。

#### 变更

- **Python 选择不再直接使用 `which python3`**
  - EDA vendor tree 内的 Python 标记为 `bundled`，永不作为 `PYTHON_EXEC`。
  - 实测主机上的裸 `python3` 曾指向 Calibre 3.8.16。
  - 选择满足 cocotb `Requires-Python` 的最新 `python3.N`，并优先 project-local venv。
  - `python_env.type` 新增 `venv`；`bundled` 只存在于 `candidates[]`。

- Tool resolution 使用非交互 bash 的 `command -v`，不能依赖用户 alias
  （实测存在 `alias vcs 'vcs -full64'`）。

- `environment_validation` 的 simulator smoke test 现在是**编译并运行**，不再只编译。

- **Experience-record rule**
  Verification 以及 Architecture、Compiler、DFT、Firmware、Formal、FPGA、HLS、
  Memory-IP、PD、RTL-Design、SoC、STA、Synthesis 共 14 个 stage Orchestrator：
  每次 task invocation 结束都写 experience record，包括 scoped single-stage task；
  后续结果推翻旧结果时通过 `supersedes` 关联旧记录。
  Meta/Infrastructure 使用不同 wording，不在此项修改。
  Verification Orchestrator maxTurns 80→150，并通过 run_state 让长 regression 可恢复。


### Issue #35：保存架构候选并按下游差距进行细化

#### 新增

- **持久化 architecture.candidates[]。** 过去候选仅保存在会话上下文，schema 字段一直为 []。架构行为规则 10 在 arch_exploration 保存完整权衡矩阵，包括拒绝/不可行候选、PPA 估计、风险、status、rejection_reason，按 name 新建或更新。
- **综合、PD、STA 的细化请求。** 新共享 Architecture Refinement Request 同步到三者，是“不得修改其他领域状态”的有限例外。故障位于微架构时，仅设置 architecture.refinement_needed 和 refinement_request（请求方、timing/power_area、约束、实测值、原因、证据），不覆盖未关闭请求，随后仍升级。Stage Gating 第 4 项引用此规则。
- **架构细化模式。** 标志已设且候选已保存时，跳过 spec_analysis/arch_exploration，从 perf_modelling 开始。下游实测覆盖模型估计，重新评分全部候选；只有 arch_signoff 通过才将请求移入 refinement_history[]。没有保存候选时回退完整流程。
- **经验记录** key_metrics 新增 candidates_evaluated、winning_candidate_profile、refinement_of。
- **Schema** 定义 architecture、archCandidate、archRefinementRequest；refinement_needed=true 必须有未关闭请求。字段均可选且为增量添加，不提高 format_version。新增有效/无效候选 fixture。

#### 保持的行为

- pipeline-orchestrator 尚不根据标志自动派发架构阶段，重新进入仍由用户手工触发，属于 V2 扩展点。

## [1.9.1] — 2026-10-04

修正编排器检查与报告的正确性（#126–#129）：

- RTL Lint Gate 检查下游实际读取的转换文件，并确认每个工具列表都能看到新增模块。
- Reporting Contract 第 8、9 项要求运行变更触发的所有 CI job，即使不签核也交接本次已确认内容。
- RTL 关闭修复请求时重跑全部受影响门控，逐阶段建立未经验证声明列表。

### Issue #129：未签核的运行仍须交接已确认内容

#### 修复

- **rtl.unverified[] 原先仅由 rtl_signoff 生成。** 正确因 CDC 工具缺失或门控 NOT RUN 而拒绝签核的运行无法到达此阶段，下游只能读到“RTL 未报告”。全部 16 个编排器的 Reporting Contract 第 9 项要求每条终止路径都合并本次实际确认的领域字段：列表由已运行阶段完整写入，未测状态为 false/null 并说明原因，交接列表在生成每项的阶段逐步建立。拒绝签核不能导致拒绝交接；IDE 防护也包含精简规则。
- **rtl-design 逐阶段建立列表。** rtl_coding、lint_check、cdc_rdc_analysis 及时追加 UNVERIFIED 结论，rtl_signoff 补全。CDC 工具缺失时阶段 NOT RUN，每个推理分析跨域成为 cdc 声明。rtl.files[] 为当前完整文件集合，lint_clean/cdc_clean 仅本次实测干净才为 true。规则加入 Reporting Contract，不重新编号行为规则。

### Issue #128：报告变更触发的所有门控

#### 修复

- **原 Reporting Contract 第 1 项只约束任务点名门控及声称满足的标准。** 第 8 项现要求全部 16 个编排器在报告完成或向有 CI 的仓库推送前，读取工作流路径过滤器，确定变更触发的所有 job，在本地运行每个 job 的步骤，不能只运行上次失败步骤；无法运行时列出步骤和原因。Codex、Gemini、Copilot 防护同样更新。
- **rtl-design 行为规则 10 原先仅靠 lint_check 关闭 fix_request。** 现在运行编辑影响的全部门控，始终包括 lint 和前端检查；跨域、同步器、复位路径重跑 CDC/RDC；逻辑深度、状态或新增模块重跑 synth_check。status=fixed 要求 lint 与前端检查通过；其他受影响门控通过或明确 NOT RUN，diff_summary 记录各项结果。

### Issues #126、#127：检查转换后的 RTL 和全部源文件列表

#### 修复

- **#126：sv2v 无法降低的合法 SystemVerilog 曾通过全部门控。** 函数结果直接部分选择 f(x)[N-1:0] 可通过 Verilator、slang、仿真回归，但 sv2v 原样输出，yosys 拒绝。五个 RTL 编写编排器新增 RTL Lint Gate 第 8 项“前端检查”：下游有 sv2v、Surelog/UHDM 或厂商转换时，运行转换，并用实际消费工具解析（yosys read_verilog; hierarchy -check），作为独立门控报告。rtl-design 中对应 lint_check 规则 15、签核标准和修复请求门控。synth_check 区分前端失败与 QoR 回退，并使用下游前端；记忆不再推荐无法发现该问题的 Surelog 前端或用 iverilog 解析 sv2v 输出。
- **#127：某工具列表缺失模块曾被静默黑盒化。** RTL Lint Gate 第 9 项要求新增模块对仿真、lint、综合、PD、形式验证的每个列表可见才算集成。stub 例外仅限能指出库/宏/IP 的情况，自有模块未知表示缺少列表项。同步到 design_input_check 规则 8、lint_check 规则 8、SoC top_integration 规则 11–13、逐 IP 清单与签核。新增仅注册列表的 design_input_check 回退，不改 RTL。综合 netlist_qc 黑盒行以 input_setup 升级，compile_explore 增加前端解析失败行。

#### 新增

- check_design_inputs.py 支持 `--rtl-dir DIR --list NAME=FILELIST [--exempt [LIST:]MODULE]`，遍历自有 RTL，逐项 ERROR 指出磁盘上存在但某列表缺失的模块、列表和文件。跳过测试平台，-y 库目录视为可见。Makefile 变量可先导出列表。

## [1.9.0] — 2026-10-01

主要修正编排器规则正确性：

- 新增 input_setup 分类与 design_input_check，输入失败直接升级。
- 移除无法成功的回退，失败回退新增 decision 值，迭代还须取得进展。
- 基础设施完善专有版本/角色/方言、模块探测与版本选择、关键命令键、Verilator MCP lint、Wrapper 冒烟检查、MCP 配置、custom 警告、modulefile 根变量、QoR 所有权。
- 新增跨轮次长任务、报告合约与阶段门控共享规则。
- 流程文档引用 Agent 权威规则，新建基础设施流程文档。
- 仓库迁移到 hdl-tools/digital-chip-design-agents，包与插件 URL 同步。

### Issues #99、#103、#104：安装规则与 QoR 所有权

#### 修复

- **#99：custom 模块系统曾收到经典 TCL modulefile 而无警告。** 规则 8 与 modulefile 下的提示原先仅警告 none。现在 custom 与 none 各有 WARN，custom 说明 TCL 格式假设并指向 module_system_detail；生成仍无条件。规则 9 的 MODULEPATH 注册仅用于 tclmod；custom 参考站点机制，none 待安装 Environment Modules 后使用。tclmod 输出不变。
- **#103：modulefile 根变量表曾按产品名匹配。** LLVM 无法匹配 llvm-config，遗漏 LLVM_DIR。现在按命令为键、产品名放括号。cocotb 按包名匹配，而非 cocotb-config。Common Issues 中 openroad、bambu-hls 同样修正。
- **#104：QoR 指标未声明或由错误阶段声明。** tool_installation 和 environment_validation 曾无 QoR 章节；dialect_conflicts 由 tool_discovery 声明却由 validation 计算。现在安装声明 install_scripts_generated，方言冲突移到 validation，Agent qor 新增 proprietary_found 与 install_scripts_generated，恰好覆盖阶段指标。各阶段只返回自身键，省略其他键，不能填占位 0/null。

**相关测试标识（保留原名）：**

- `tests/test_agent_contract.py`
- `test_every_infrastructure_qor_key_is_declared_by_the_stage_that_computes_it`
- `test_modulefile_root_vars_are_keyed_by_command`
- `test_custom_module_system_is_warned_about_tcl_modulefiles`

### 仓库迁移到 hdl-tools

#### 变更

- package.json、全部 plugin.json、README、INSTALL、CONTRIBUTING、schema $id、发布说明的仓库 URL 改为 hdl-tools/digital-chip-design-agents。GitHub 虽重定向旧 URL，但 npm trusted publishing 与 provenance 绑定实际运行 release workflow 的仓库，保留 chuanseng-ng 会导致下一次发布被拒绝。author 和 marketplace owner 是人名，保持不变；历史日志保留旧名称。
- 发布说明加入 Codex CLI（bash install.sh --ide codex）。

#### 新增

- tests/test_repo_identity.py 检查 package.json 指向当前仓库，除历史 CHANGELOG 外无文件引用旧仓库。

**相关测试标识（保留原名）：**

- `tests/test_repo_identity.py`

### Issue #118：流程文档重复规则已与编排器偏离

各 docs/*Flow*.md 最多重复三次规则：带回退箭头的阶段图、Loop-Back 表、系统提示词。#86、#102、#113、#83 修正 Agent 后文档未更新，13 个中 8 个与 Agent 不符，包括无法成功的 LEC、FPV、定向测试、扫描 DRC 回退，以及错误目标、上限、阈值或单侧新增行。

#### 变更

- 全部 14 个流程文档（含 Memory IP、PD）阶段章节保留 Agent 阶段顺序并链接其 Loop-Back Rules，移除重复表与回退箭头；系统提示词链接 Agent，因为 Agent 本身即提示词。PD Failure Escalation 及 §7 构建步骤同样引用 Agent。概览、共享状态、Skill 定义保持不变。
- MASTER_INDEX 明确 Agent 对阶段顺序、回退、门控、升级具有权威性。
- 新建此前只在索引列出、从未写入的 Infrastructure_Setup_Flow.md：共享状态及写入方、各阶段概述、调用层级、添加工具清单、交接说明（目前无领域编排器读取 environment.signoff）。纳入 FLOW_DOCS 检查。

#### 修复

- tool-manifest 中 wrappers.expected 曾为 8，实际为 9；加入 lint Wrapper 时未更新。数量检查原先只匹配说明文字，现在也匹配 JSON 字段，MCP 检查匹配 snippets_expected/mcp_target。PIPELINE 将 PD 示例标为示例并链接 Agent。

#### 新增

- 参数化检查全部 14 个文档的 Agent 映射、不得重复旧形式回退规则、Agent 链接与阶段顺序。原 RTL 专用阶段顺序检查由参数化检查覆盖。

**相关测试标识（保留原名）：**

- `tests/test_agent_contract.py`
- `test_every_flow_doc_is_mapped_to_its_agent`
- `test_flow_docs_do_not_restate_loop_back_rules`
- `test_flow_doc_stage_sequence_matches_the_agent`
- `test_rtl_flow_doc_and_knowledge_follow_the_agent`

### Issue #117：MCP 配置文字与磁盘文件互相矛盾

#### 修复

- **mcp_configuration 模板把 Wrapper 当 MCP 服务器。** command=wrap-<tool>.sh 违反规则 2；Wrapper 打印一个 JSON 后退出，无法完成 MCP initialize，还会覆盖现有正常配置。现在从磁盘配置提供三种模板：批处理 python3 mcp-adapter.py --wrapper/--tool、会话 mcp-session-adapter.py --tool、记忆 mcp-memory.py。
- **mcp-openroad.json 曾声称 bash install.sh 会复制模板并替换路径。** 实际任何安装器都未这样做。_setup 改为 infrastructure 的 mcp_configuration 或手工替换，规则 4 同样明确。
- **可选 mcp-memory.json 曾未纳入路径解析。** 它是目录第 11 个文件，但阶段只列十个，导致 absolute/path 占位保留，语义查询不能工作。规则 1 与 Output Required 现在列出可选且不计数的记忆配置，与其他路径一起解析。指标、validation 规则 4、签核清单、Agent 行为规则 5 明确为“10 个工具服务器”，不能误读成全部 11 文件；memory README 链接该阶段。

#### 新增

- 检查所有 mcpServers 使用 python3 加真实 MCP 服务器脚本，不能使用 Wrapper；不得声称安装器处理配置；阶段列出全部配置且数量等于实际工具服务器数。

**相关测试标识（保留原名）：**

- `tests/test_agent_contract.py`
- `test_mcp_configs_run_a_server_script_not_a_wrapper`
- `test_no_mcp_config_credits_an_installer`
- `test_stated_mcp_count_matches_the_mcp_directory`

### Issue #83：输入集合失败不应触发 RTL 编辑

原 lint 只有 errors>0 回退 rtl_coding 五次，未检查工具输入。实际陈旧寄存器头文件树位于 include 首位，遮蔽当前版本，产生 19 个重复声明/未声明标识符 fatal 并中止规则检查；只需改一行 filelist。若派到 RTL 编辑，容易误删真实端口。

#### 新增

- input_setup → escalate：工具正确运行但输入（filelist、include、项目/配置、生成头文件、库视图）错误。不是会 regenerate 的 tool_error，也不是从未评估过产物的 functional。加入权威表、决策表、15 个共享块、schema enum/allOf 映射、全部 16 Agent 枚举、MASTER_INDEX 和 memory README。format_version 仍 1.5；旧读取方会按保守规则升级。
- Loop-Back Rules 不能覆盖 input_setup。它与 Stage Gating 第 4、7 项一样，凭证据立即停止循环，不能因还有迭代次数继续。
- rtl_coding 与 lint_check 间新增 design_input_check：打印 filelist/配置绝对路径和有序 include；同名不同内容为 ERROR，标出同级版本树、根目录外路径、生成树早于源。FAIL 升级且不修改文件。行为规则 11 在首次 lint、输入改变后及修复请求模式下运行。
- 纯标准库、只读 check_design_inputs.py 支持 .f 的 -f/-F、+incdir+、-I、-y、$VAR，输出 JSON，FAIL 退出 1。厂商项目文件按相同规则手工检查。
- lint_check 规则 12–14：中止意味着零规则，数量为 null 而非 0，绝不分类 functional。编辑前归因全部 fatal；混代头文件、同文件双路径、缺 include、非本次写入文件 fatal 为 input_setup。先按输入、库模型噪声、RTL 归因，再看严重级别。Wrapper 非零不等于 lint 失败。
- 五个 RTL 编写 Agent 的 RTL Lint Gate 第 7 项覆盖中止运行，IDE header 精简加入；可选 hdl-rtl-skill 项移至 8。
- RTL 记忆增加陈旧头文件、中止 lint、用户覆盖目录绕过管理配置三种模式。已有记忆根仅在文件缺失时复制种子，因此不会自动得到这些新增模式。
- 新增有效 input_setup 与无效 input_setup_regenerate fixture；19 个文件输入测试检查同名路径、无文件修改、正常设计、嵌套列表、变量、同级版本树及非版本编号实例。

#### 变更

- lint 行拆为四类：输入检查 FAIL 和输入导致/无法归因的中止升级；仅本次写入 RTL 的解析错误且输入检查通过时，以 tool_error 回退，不能为 functional；原 errors>0 行仅用于完整规则检查。这有意偏离 issue “绝不回退 RTL”字面标准，因为 Verilator 会对任何语法错误中止，完全禁止会把每个新代码拼写错误都升级给用户。
- pipeline 遇子流程 input_setup 直接升级，不开 fix_request，不再派发。
- RTL 流程文档的阶段列表、图、回退与提示词同步。

**相关测试标识（保留原名）：**

- `tests/test_design_inputs.py`
- `tests/test_agent_contract.py`
- `test_input_setup_always_escalates`
- `test_no_loop_back_row_overrides_input_setup`
- `test_failure_class_enum_lists_input_setup`
- `test_rtl_design_checks_its_inputs_before_linting_them`
- `test_rtl_skill_defines_the_input_check_and_aborted_run_rules`
- `test_rtl_lint_gate_covers_an_aborted_run`
- `test_rtl_flow_doc_and_knowledge_follow_the_agent`

### Issue #112：修复 Verilator MCP 的 lint 模式

#### 修复

- mode=lint 原先将 --lint-only 交给期望仿真二进制的 wrap-verilator-sim.sh，报告找不到名为 --lint-only 的 binary，根本未调用 Verilator。RTL/SoC 无法使用结构化 lint，只能直接执行。现在调用所配置 sim Wrapper 同目录的 wrap-verilator-lint.sh，旧 MCP 配置无需修改。
- 缺可执行位的 Wrapper 曾抛出未捕获 PermissionError 并结束服务器循环，现在返回 FAIL 与 chmod +x 指引；旧安装在第九个 Wrapper 出现前已执行过 chmod，因而会遇到此问题。
- RTL、SoC 曾将 sim Wrapper 用于 lint，mcp-verilator 描述也承诺无法产生的 lint 计数，现已修正。

#### 新增

- wrap-verilator-lint.sh 运行 verilator --lint-only（未提供时补上），统计 %Error、%Warning-<CODE> 为 error_count、warning_count、warnings_by_code。结束汇总 %Error: Exiting due to N 不计发现，记 exited_on=errors/warnings；Verilator 默认警告也退出非零，不能误计一个错误。
- 干净 lint 无输出；仅至少一个参数指向实际存在设计文件时，才 PASS/verified=true。--version 或全部输入缺失为 WARN/false。
- Wrapper 与端到端 MCP 测试使用 PATH 上假 Verilator，覆盖干净、警告、错误、警告致命、版本、输入缺失、工具缺失；新增检查确保每个 Wrapper 都有测试。

#### 变更

- Wrapper 数量 8→9，MCP 仍为 10，因为通过现有 Verilator 服务器访问。数量检查将声明与实际 wrap-*.sh 比较。

**相关测试标识（保留原名）：**

- `tests/test_wrappers.py::test_lint_*`
- `tests/test_mcp_adapter.py::test_lint_mode_end_to_end_*`
- `tests/test_wrappers.py::test_every_wrapper_script_is_exercised_here`
- `tests/test_agent_contract.py::test_stated_wrapper_count_matches_the_tools_directory`

### Issue #95：区分正常仿真 Wrapper 与错误调用

#### 修复

- wrap-verilator-sim.sh --version 曾把选项当 binary 路径，返回与损坏 Wrapper 相同的 FAIL。现在自行处理 --version、--help、-h，输出用法及 WARN/verified=false，与其他 Wrapper 版本检查一致；不存在或不可执行的实际路径仍 FAIL。部署规则 4 明确该行为，并新增相应测试。

**相关测试标识（保留原名）：**

- `tests/test_wrappers.py::test_verilator_sim_answers_version_and_help_itself`
- `::test_verilator_sim_still_fails_on_a_missing_binary`
- `tests/test_agent_contract.py::test_smoke_test_rule_covers_the_wrapper_that_takes_a_binary`

### #107 后续：回退次数上限也须约束收敛

#### 新增

- Stage Gating 第 7 项“重试必须朝同一目标取得可测进展”同步到除 pipeline 外的 15 个 Agent（pipeline 自有跨领域分歧检查）及 IDE header。次数上限无法处理结果更差、完全不变或改变检查目标而通过的情况；原先仅 RTL Lint Gate 和 verification/formal/dft 有防护，架构、综合、STA、PD、编译器、固件、基础设施没有。FPGA sw_validation 两行与 STA path_analysis 甚至不限次数。
- 每次回退比较实测：回归则恢复前一产物，仍计一次；连续两次相同则无进展，提前升级；通过放宽约束、加豁免/例外、弱化检查、改行为压下工具而得到的“通过”不算通过。仅目标本身错误且引用来源、记录原因时可改目标，不能修改其他领域所有的目标。
- 防护优先于行中剩余迭代：上限是最多尝试，不是必须花完。Failure Classification 明确 Stage Gating 第 4、7 项凭证据停止循环。
- 提前停止记录实测 failure_class，不是未达到上限的 resource_limit；无需新增 enum/schema。新增测试保护关键条款。

#### 变更

- RTL Lint Gate 第 6 项成为第 7 项的 RTL 实例，不再把无进展路由到上限耗尽流程而误记 resource_limit。

**相关测试标识（保留原名）：**

- `tests/test_agent_contract.py::test_progress_guard_present_in_stage_gating`

### #107 后续：DFT、验证、形式验证的编码与 RTL 交接规则

#107 将这三个领域另行处理。它们不属于可综合 RTL 编写 Agent，所以不加 RTL Lint Gate，但仍会写/审查代码，并接收 RTL 未证明事项。

#### 修复

- formal Skill 曾要求“修 RTL 后重跑 FPV”，而 Agent 要求 fix_request、不本地重试；仅加载 Skill 的 IDE 会擅自改 RTL。cex_analysis 与结果表现在交回 RTL 流程。
- DFT 单条扫描 DRC 回退曾覆盖生成时钟、不可控异步复位等插入无法修复的问题；拆为可插入修复者重试，设计问题升级 RTL。
- rtl-design Skill 明确测试平台不在范围，不能只依赖 Agent 豁免，因为 Copilot 将 Skill 应用于所有 .sv。
- 假定正确的形式属性不再计结果，记 UNVERIFIED，不计 PROVEN，P0 未验证阻止签核。

#### 新增

- rtl.unverified[] 交接，结构为 module/category/claim，包括依赖恢复断言的每个 FSM；Agent 写入 design_state，formal property_planning 与 verification test_planning 必须逐项对应属性、测试或说明理由。缺失键为未报告，非无需检查。
- fix_request 可选 suspected_rtl.basis=traced/hypothesis，兼容 schema。猜测或未提供依据时，RTL 修改前先证实原因。
- verification：测试平台 default_nettype、命名连接、参数类型、带符号字面量陷阱、!== 对 X 比较；ready/valid 驱动及断言合约；困难边界、参数边界、DUT/测试平台现象排查表。
- formal：lint 不能证明的 ready/valid、FSM 可达/退出/非法恢复、仲裁、FIFO、算术范围、复位、死锁目标表，及边界参数证明规则。
- DFT：插入前扫描就绪审查，RTL 交付逻辑遵守 rtl-design 规则；RTL 增加对应扫描就绪规则。
- 各域禁止弱化检查取得通过：不放宽 scoreboard/豁免断言，不排除合法激励，不通过排除扫描触发器清 DRC。
- 新增合约与 schema 测试。大多数内容来自 hdl-rtl-skill 的审查、自评、调试流程；!== 和测试平台末尾恢复 default_nettype wire 为本次新增。

**相关测试标识（保留原名）：**

- `test_planning`
- `tests/test_agent_contract.py`
- `::test_formal_skill_hands_rtl_bugs_to_the_rtl_flow`
- `::test_scan_drc_design_fault_escalates_instead_of_retrying_insertion`
- `::test_rtl_unverified_handoff_has_a_producer_and_consumers`
- `::test_suspected_rtl_schema_carries_basis`
- `::test_rtl_design_scopes_out_testbenches`

### Issue #107：安全 FSM 恢复与 slang 完整检查

#### 修复

- 综合安全规则 3 原先强制 unique case，无法与 FSM default 恢复分支一致：unique 声称非法状态不出现，default 则恢复非法状态，slang 报 -Wcase-redundant-default。现在禁止 casex、无理由 casez、full_case/parallel_case；规则 7 默认普通 case+default 恢复，或无 default 的 unique case 配恢复断言，不能同时用两者。
- ASIC initial 禁令新增唯一例外：translate_off/on 内 initial+$fatal 的 elaboration 参数断言，用于拒绝非法配置，如深度 12 的 Gray FIFO。
- slang 原无完整调用，记忆命令缺 Weverything。lint-only 跳过 elaboration，漏掉 ERROR 级锁存器及多驱动；Wall 也非 slang 选项。Skill、Agent、记忆统一 slang -Weverything --ignore-unknown-modules，禁止 lint-only。依据 #107 记录及 hdl-rtl-skill 生成警告表，本次未重跑验证这两个工具行为。
- HLS 生成 RTL 只检查正确性，不强制命名风格，不手改生成代码；锁存器检查必须 slang 完整 elaboration。
- fix_request 关闭前必须 lint 通过并在 diff_summary 记录；pipeline 说明缺 lint 结果时如何处理。

#### 新增

- 共享 RTL Lint Gate 同步到 rtl-design、fpga、soc、memory-ip、hls；除 RTL 外四者不加载 RTL Skill，此前仅有“lint 干净”目标而无规则。覆盖 slang、filelist、stub、证据层级及回归/无进展/意图偏移。
- lint_check 规则 6–11 供仅加载 Skill 的 IDE 使用，BLOCKER/HIGH→ERROR、MEDIUM→WARNING，保持 lint_waivers 有效。
- 新 RTL 用项目风格，已有文件按其风格；_i/_o 可选，默认约定不变。
- FPGA 编辑后重新 lint，initial 仅 FPGA 文件，原语为 stub；SoC 命名端口、完整列表、黑盒 IP 为 stub；memory Wrapper RTL 遵守规则，仿真行为模型豁免。
- hdl-rtl-skill 为可选配套，不是依赖。其仅 Claude Code 且需 symlink/手工 hook，强依赖会使其他 IDE 无规则。规则吸收到本项目，可用时使用 runner、模板、目录，不可用时静默跳过。
- 新增 slang 调用、五个 Agent 门控、FSM/参数安全规则回归检查。

**相关测试标识（保留原名）：**

- `tests/test_agent_contract.py::test_slang_is_never_invoked_with_lint_only_or_wall`
- `::test_rtl_lint_gate_present_in_rtl_authoring_agents`
- `::test_rtl_design_rules_do_not_contradict_safe_fsm_recovery`

### Issue #76：跨轮次长任务的运行与交接

#### 新增

- 全部 16 Agent 及 IDE header 新增共享 Long-Running Jobs。此前仅 PD 说明 ORFS/LibreLane 完成后读哪些文件，没有后台、轮询、区分慢与卡死、超出轮次预算的交接规则。固件 Agent 实测忙等后台构建耗费约 250k token，未完成验证却交付失败套件，而其签核标准要求 24 小时压力测试。另一实例 Verilated SoC 编译约 20 分钟日志不变但 cc1plus CPU 为 99.9%，说明静默不等于挂起。
- 后台启动并记录任务 ID/日志，按任务时间尺度轮询，先查存活再判断静默日志卡死；超预算则交接任务 ID、日志、调用方式及剩余阶段；未读取结果不能报告。刻意不提高 maxTurns，因为缺等待协议只会延长阻塞。新增关键条款测试。

**相关测试标识（保留原名）：**

- `tests/test_agent_contract.py::test_long_running_jobs_guidance_present`

### Issue #102：LEC 不再回退到无法修复网表的阶段

#### 修复

- lec_run 只比较 RTL/golden 与综合网表，不重新生成任何一方。unmatched points 曾回退 lec_run 三次，输入不变必然重复失败。这与 #86 一样，虽共享规则要求上游故障交回，但原行仍授予三次迭代，按优先级必须花完。现立即升级，指出不匹配及须由综合产生修复网表。

#### 新增

- 新增检查防止该行再次回退 lec_run。

**相关测试标识（保留原名）：**

- `tests/test_agent_contract.py::test_lec_mismatch_escalates_instead_of_looping_back_to_lec_run`

### Issue #94：回退失败具有独立 decision 值

#### 修复

- history decision 原只有 proceed/escalate/abandoned/await_approval，无“失败后回退”的常见非终止结果。每阶段必须写记录，原只能错误地选 proceed，与实际相反。参考主机两次 validation 因关键工具缺失回退安装，两次均记 proceed；pipeline 无法区分干净通过与此类失败。
- 全部 15 个领域 Agent 枚举新增 loop_back。pipeline 保持较窄 proceed/escalate，说明其只在 signoff_or_escalate 的两个终止分支写记录，内部 check_iteration_cap 回退不单独写。
- failure-classification 共享块明确何时写 loop_back 而非 proceed。

#### 新增

- 对所有含 Loop-Back Rules 的 Agent 参数化检查 decision 枚举包含 loop_back。

**相关测试标识（保留原名）：**

- `tests/test_agent_contract.py::test_decision_enum_lists_loop_back_for_agents_with_loop_back_rules`

### Issue #98：模块版本选择

#### 修复

- tool_discovery 步骤 A c 和 module_discovery 规则 9 原称“最高 semver/字典序”，把不同排序当相同。13 版本 Python 树中最新为 3.14.6，字典序最大却为第四旧的 3.9.7，因为第二段 9>1。步骤 A 优先于 PATH，曾将主机 3.12.2 替成旧模块并保持后续五阶段；load-modules 也选错。现在两处引用唯一 Module version selection。
- module avail 的 default 注释原被丢弃；3813 项中 372 项有注释，现在捕获并优先采用站点默认。
- dev/test/debug/rc/alpha/beta/snapshot/nightly 任一片段标记为非发布版本，有发布版时不自动选，但保留候选。3.12.2.R10 和 3.9.7n 等站点修订/补丁仍属发布版。

#### 变更

- 结果是“主机应使用的版本”，不保证最新；站点默认通常是经过验证的旧版，参考主机所有检查工具均如此。
- module-status 逐工具记录 selected、selected_basis（site_default/highest_release/highest_prerelease）、candidates，使选择可审计；highest_prerelease 应少见。
- load-modules 行末注明 selected 依据与 alternatives，摘要打印依据/候选数。
- 记忆建议仅在站点默认不适合具体流程时固定版本，不再常规弥补字典序错误。

#### 新增

- 四项经变异检查的断言：调用点不能字典序排序、规则唯一且双方引用、默认优先且列全非发布标记、schema 有三个选择字段。
- 实测校验修正比较器：额外非数字段若排低会错误认为 3.12.2.R10<3.12.2。5.24 优于 5.24-dev 已由非发布排除解决，发布池剩余附加段是修订，故共同段相等时更多段更高，可用普通 tuple 比较。

**相关测试标识（保留原名）：**

- `tests/test_agent_contract.py::test_module_version_selection_is_specified`

### Issues #91、#90：环境验证基线与 Python 检测

#### 修复

- #91：tool-manifest 有五处引用，却无 schema/创建方。不是最初遗漏，而是 f1124c5 重写模块支持时删除了创建规则与 Output Required，仍保留“比较/已写/已更新”的引用，导致两次运行编造不兼容结构。现在明确创建方及 schema。
- 规则 2 曾与同阶段自身输出比较，任何运行都无基线。现与 tool_discovery 写入、module_discovery 原地更新的唯一 tool-status 比较，明确不比较自身输出；分歧 WARN 不降级，保持 tool-status 只读。
- #90：声称与 discovery Python 检测相同，实则去掉 cocotb/uv 的 bin_dir→PATH 回退，并在 system 类型构造 discovery 从不使用的 bin_dir 路径。现在完全遵循规则 3；openlane 原无回退，保持不变。

#### 变更

- tool-manifest 是验证凭据，不重复 tool-status 已有逐工具字段及 python_env。只记录 Python 存活、Wrapper 可执行位、MCP 存在性、方言冲突及成员、签核结论；tool_status_source 引用原文件。记录模块可能已卸载或 exec 不再匹配。
- 有意不恢复原安装规则 6，因为它依赖执行单一安装脚本再调查，现在只生成逐工具脚本、从不执行。
- MASTER_INDEX 基础设施产物补 tool-status、module-status。

#### 新增

- custom/module 的包从 PATH 回退解析、位于当前解释器 bin 之外时 WARN，可能解释器不匹配；system 不警告。manifest 的 python_packages.resolved_via 使其可审计。issue 提议警告或镜像检测链，两者互补。没有 Wrapper/MCP 使用 PYTHON_BIN_DIR、uv、cocotb-config、openlane，因此不能以“Wrapper 找不到”为理由；真实风险是解释器不匹配。uv 独立安装器常装在另一前缀，参考主机如此，旧规则误报缺失，新规则 FOUND/path 并 WARN。
- 四项变异检查：承诺 JSON 产物必须定义/schema；不得比较自身产物（否定语句不误报）；不得禁止 discovery 已支持的 PATH 回退；manifest 不重复逐工具字段。

#### 后续范围

- #104 的 QoR 声明问题独立处理；另行记录索引指向不存在基础设施文档的问题。

**相关测试标识（保留原名）：**

- `tests/test_agent_contract.py::test_environment_validation_artifacts_are_defined`

### Issues #92、#86：按命令匹配关键工具，移除无效回退

#### 修复

- #92：关键工具集合曾按 Yosys/Verilator/OpenROAD/OpenSTA 产品名匹配，但条目按命令为键，OpenSTA 是 sta。找不到条目不等于工具缺失，导致签核静默通过。现在在 validation 顶部统一定义 yosys/verilator/openroad/sta，三处规则均引用命令；#87 曾增加第三处副本，故须单一规则。
- tool 与 command 原未解释，现在明确二者都是可执行命令名。仅针对两个 status 文件；Wrapper 的 tool 有意为 opensta/verilator-sim 标签，用于识别记录生成方，不能改为命令。
- Formality 主命令 #82 已改 fm_shell，但模块映射和 Agent 仍为旧 formality，导致模块升级静默遗漏。现在键改 fm_shell，仍匹配产品命名 formality、synopsys/formality。七个专有主命令复查仅此不一致。
- #86：validation 因缺关键工具回退安装两次永远无效，安装仅生成脚本而不运行，MISSING 输入也不改变。现立即升级，说明脚本位置、重跑步骤及为何重试无效，防止再被改回循环。与 python3 缺失及需 module load 两行一致；pending_approval 不设置，按 Stage Gating 只用于门控。

#### 变更

- validation 规则 5 不只写 FAIL，也写完整升级操作及理由，避免 Skill 与 Agent 各持一半合约。

#### 新增与后续

- 四项变异检查覆盖集合命令键、表中存在、缺工具不能回退安装、专有主命令均有模块映射。
- 回退 failure_class 标注留给 #93，当时所有 83 行尚无 history 分类，不能单独创造第三种格式。LEC 同类无效回退、LLVM 产品名变量键、validation 无 QoR 分别另立问题。历史 #87 产品名记录保留，检查仅限 plugins。

**相关测试标识（保留原名）：**

- `tests/test_agent_contract.py::test_critical_path_tools_are_keyed_by_command`

### Issue #87：模块系统检测与列表来源

#### 修复

- 原 `$MODULESHOME` 已设或 modulecmd 在 PATH 就一律 tclmod，仅有 tclmod/none 枚举，站点 Wrapper 被误标。现在需 modulecmd 才初判 tclmod，只有 MODULESHOME 则 custom，并记录 module_system_detail。
- 空 tools_via_modules 与列表未运行无法区分。module 常为 Shell 函数，非交互 bash 实测返回 127；两次运行误记 tclmod/[]，静默丢失仅模块提供的七工具（verilator、iverilog、klayout、vsim、innovus、pt_shell、formality），随后错误 FAIL。现在 module_listing 记录是否获得列表；只有 LISTED 时空列表才表示没有。
- 分类仅为初始推断，成功调用可升级：init/bash 获得列表证明 tclmod，即使 modulecmd 未在 PATH。由探测而非变量决定。
- load-modules.sh 省略条件由 module_system=none 改为“无工具符合”，none 只是其中一种情况。
- 映射不能任意子串匹配。3812 项实测误匹配以 slang 结尾的优化工具，以及版本含 python2、名称含 python3 的 GUI 包；后者可能取代解释器并保持全程。现在只匹配完整 / token，含 / 模式须连续匹配，排除两类误报，留下 12 个真实工具。
- 条目不只 name/version，可为 klayout/adi/0.29.0 或带 adi default 注释。去末尾注释后取最后 / 段为版本，保留完整模块名，不能误把 adi 当版本。

#### 新增

- 五级调用阶梯：自身 Shell、modulecmd bash avail、init/bash、module.sh、直接 Wrapper；成功调用原样记 module_invocation。参考主机第 4 级 159.5 秒返回 0、3813 项，真正找回七工具。
- 成功须退出 0 且至少一条条目格式行。第 5 级实测退出 1，用法中也有 modulename/scope 等形似条目，单看形状会误报三个模块；退出 0 无列表同样失败。
- timeout 包 Shell 而非函数，300 秒预算；timeout 60 module avail 返回 127。每级用 timeout 300 bash -c，并 stdin=/dev/null，避免提示阻塞。遍历 NFS modulefile 可耗 159.5 秒并有陈旧路径噪声，短超时会误判。
- WARN 区分无模块系统与检测到但无法列出，后者给出分类/证据/失败及 bash module.sh 或 tcsh module.csh 指引。后者且关键工具仍 MISSING 时，以 tool_error 在本阶段升级，不能数阶段后误报工具未安装。
- 新 module_listing_ok；custom 也计 module_system_detected，只有列表成功时 tools_found_via_modules=0 有意义。新增 enum、记忆副本、schema、空列表语义检查。

#### 变更

- Python 步骤 A 引用相同检测与阶梯，UNAVAILABLE 时明确回退 PATH，但不压下 module_discovery WARN。
- 摘要打印分类/证据/获胜调用；未调查工具数打印 not surveyed 而非 0。
- 发现的字典序版本问题另立 #98，custom 收到 TCL modulefile 却无警告另立 #99。

**相关测试标识（保留原名）：**

- `tests/test_agent_contract.py::test_module_system_records_a_custom_wrapper_and_a_listing_status`

### Issue #85：每个编排器都能读取重试映射

#### 修复

- 16 个编排器中的 15 个行为规则曾要求从 pipeline-orchestration Skill 推导 retry_strategy，却未声明该 Skill，仅 meta 所有者可读。1.5 要求每个 history 包含策略，pipeline 依此选择重试/跨域/升级，靠每次推测会静默漂移且违反源读取合约。

#### 变更

- failure-classification 共享块同步到 15 个领域 Agent，含当时 10 行映射及 regenerate/refine/escalate/none 含义。行为规则改指向本地表。没有将 494 行 meta Skill 加载到每个 Agent，因为只需一张表，且其中 pipeline 专属 escalation 所有权会引起混淆。

#### 新增

- 检查共享表与权威 Skill 表一致（sync --check 本身只比较 Agent 与共享文件）；检查写策略的 Agent 必须携带表或声明 Skill，未声明不能引用。后一检查发现 verification 中不同措辞的重复陈旧引用。

**相关测试标识（保留原名）：**

- `tests/test_agent_contract.py::test_retry_strategy_mapping_matches_the_authoritative_table`
- `tests/test_agent_contract.py::test_retry_strategy_mapping_is_reachable_by_the_agent`

### Issue #82：专有工具版本与命令方言模型

#### 新增

- tool-status 每项增加 role/dialect：功能分组与接受的命令/源语言词汇。开源/专有均记录；无同角色同类工具时为 null，不能编造而造成假冲突。module_discovery 原样保留。
- 实际安装上测量免许可证版本探测：vcs -ID（只取 Compiler version，绝不存 FLEXlm host ID）、xrun -version、dc_shell -version、pt_shell -version、fm_shell -version，1–26 秒、退出 0、有指定行、无许可证队列。Questa/Innovus 保留 UNVERIFIED，不能猜选项而启动交互或占许可证；参考主机分别缺 libXext 与构建授权过期。
- 超时 60 秒：Cadence Common UI 启完整 Shell，genus 实测冷 26 秒、热 12 秒，10 秒会误判。
- 退出 0 但无指定行仍空 version 并 WARN：innovus 授权过期、voltus 平台损坏、vsim 共享库失败均退出 0 无版本。只有真正找到行才记录。
- Formality 主命令 fm_shell，formality 为近期安装缺失的旧 GUI 备用命令。
- validation 对同 role 不同 dialect 且至少一个 PROPRIETARY_ONLY 的组，仅每角色一条 WARN，列出所有成员；dialect_conflicts 计角色而非工具对。此检查可提前发现 Xcelium 编译行误用于 VCS、静默丢弃八开关和 access 再失败的问题；限制专有工具参与以免普通双开源仿真器遍地产生警告。
- 增加 proprietary_versioned、dialect_conflicts 指标及合约测试，防止专有工具缺角色/方言、已验证探测丢命令或 schema 丢字段。

#### 变更

- discovery 规则 6 从仅 FOUND 版本扩展到 PATH 中有已验证探测的 PROPRIETARY_ONLY，避免该类 version 永远空。
- 基础设施记忆 tool_versions 从仅 FOUND 扩展到所有非空 version 的 FOUND/FOUND_PREFER_MODULE/PROPRIETARY_ONLY，后续可按精确构建查询选项。

#### 后续范围

- 主动启用编译冒烟检查另立 #88，专有编译 Wrapper 另立 #89。当时 Wrapper 仍 8、MCP 10；扩展原七工具及验证本机无法验证的 Questa/Innovus 选项另立 #84。

**相关测试标识（保留原名）：**

- `tests/test_agent_contract.py::test_proprietary_tools_carry_role_and_dialect`

### feat/reporting-contract branch

#### 新增

- **全部 16 个 Orchestrator**：新增 `## Reporting Contract` 章节（issues #75、#78），内容统一从 `tools/agent_shared_sections.md` 同步。过去 sign-off 判据只是声明式属性，没有规则要求这些判据必须经过实际观测，而不是由 Agent 自行声称。新契约要求：运行任务中点名的每个 gate 并引用其准确输出；本次会话没有实际运行的 gate 绝不能报告为通过（应报告 NOT RUN 并说明原因）；exit code 为 0 但输出为空或无法解析不能算 PASS；结束前重新核对交付物清单；明确区分 measured value 与 inference；对测试依赖的所有 generated artifact，在每个实际运行环境中验证其来源；只有全部判据都是 measured-PASS 时，才能把 `signoff` / `signoff_achieved` 设置为 true。
- **Codex、Gemini、Copilot header**：在 `## Verification and Reporting` 中加入上述契约的 5 条精简规则。
- **Wrapper JSON 的 `verified` 字段**：当 `status` 基于工具输出中成功解析出的结果，或明确失败证据时为 `true`；当工具 exit 0 但没有可识别结果，或工具根本没有运行时为 `false`。Infrastructure Skill 的 wrapper schema 已补充说明。
- **测试**：`tests/test_wrappers.py` 通过 bash 使用 fake tool 运行每个真实 wrapper（Windows 默认跳过，除非 `RUN_WRAPPER_TESTS=1`）；`tests/test_mcp_adapter.py` 覆盖 adapter 对 wrapper 输出的解释逻辑。

#### 变更

- **行为变化——8 个 EDA wrapper 不再在缺乏证据时报告 `PASS`。** 过去状态只根据 exit code 和 ERROR/WARNING 行计算，因此工具 exit 0 且输出中没有 wrapper 认识的内容时也会被判为 `PASS`。现在 wrapper 必须从输出中解析出有效结果，否则返回 `WARN`、`verified:false`，并在第一条 warning 中明确说明。证据仍使用 wrapper 已有的字段，不新增 log marker。安静运行，例如 `yosys -q` 或仅执行 `--version` 的 smoke test，过去返回 PASS，现在返回 WARN。exit code 本身仍原样透传。
  - `wrap-verilator-sim.sh`：只有出现 `TEST PASSED` 才能判定 `PASS`。exit 0 时即使出现 ERROR 行也只给 `WARN` 而不是 `FAIL`，因为仿真日志中可能出现诸如 “Error count: 0”。
  - `wrap-klayout.sh`：若 report 可解析且没有 category，视为 clean run；如果既没有 report，也无法从 log 中解析 count，则 `drc_total` 为 `null`，不再伪装成 `0`。
- **行为变化——`mcp-adapter.py`**：过去 exit 0 时，空 wrapper 输出会被判 PASS，非 JSON 输出判 WARN，无合法 `status` 的 JSON 也会继续透传。现在这三类情况全部返回 `FAIL` 且 `verified:false`，因为 wrapper contract 要求每次运行都必须输出 JSON。合法 wrapper JSON 仍保持原样透传。只有 `status == "FAIL"` 时 `isError` 才为 true。
- **`mcp-session-adapter.py`**：`query_drc` 在无法解析 count 时返回 `drc_total:null`，不再返回 0。

### feat/shared-orchestrator-guards branch

#### 新增

- **共享 Orchestrator 章节，从单一源同步**（issue #77）。`tools/agent_shared_sections.md` 保存所有 Orchestrator 必须逐字一致的共享规则；`tools/sync_agent_sections.py` 将内容写入每个目标文件的 `BEGIN SHARED` / `END SHARED` 标记之间。`--check` 用于检测 drift 并在 CI 中运行；`--list` 显示每个共享 block 应写入哪些文件。脚本会保留原文件换行风格，因此 CRLF 工作区和 LF CI 环境可以得到一致结果。对应测试位于 `tests/test_sync_agent_sections.py`。
- **15 个 Orchestrator**：新增 `## Stage Gating and Escalation`。规则包括：给 stage 设置状态前必须先读取工具真实结果；遇到 FAIL 必须应用 loop-back，不能直接越过；loop cap 用尽后必须停止并携带状态/根因升级；如果故障来自上游 artifact，则停止本域循环并交回。过去这些 guard 只零散存在于 `pd`、`rtl-design`、`memory-ip`、`architecture`、`infrastructure` 的一两个规则中，另外十个 domain Orchestrator 对达到最大迭代次数完全没有统一规则。由于 `pipeline-orchestrator` 本身负责 dispatch，并拥有 `pending_approval` 的 `escalation` 类型，因此不包含该共享段。
- **`compiler` 和 `firmware` Orchestrator**：新增 `### MCP Preference`。这些 toolchain 没有 MCP Server 或 wrapper，因此规则要求使用直接执行并把输出保存到 log 文件，而不是 EDA domain 常用的 MCP → wrapper → direct 三级路径。
- **Codex、Gemini、Copilot header**：增加精简版 `## Verification and Reporting`。Copilot/Codex 安装只接收 Skill，不会安装 Agent 文件。
- **`.gitattributes`**：加入 `* text=auto` 和 `*.sh text eol=lf`，保证 Windows checkout 后 shell script 仍可正常运行。

#### 变更

- **统一 `pending_approval` 所有权。** Pipeline Skill 一度规定 domain Orchestrator 只能设置 `type:"checkpoint"`，但又要求 constraint validation 使用 `type:"constraint_gap"`；同时 15 个 Orchestrator 里还有一句话暗示任何 escalation 都可设置 `pending_approval`。现在 domain Orchestrator 只在两个 gate 使用它：checkpoint 和 constraint validation。loop cap 耗尽或上游 fault 的 escalation 只写 terminal `history[]`，其 `reason` 必须包含 `failure_class` 和用户需要补充的内容。`type:"escalation"` 仍由 `pipeline-orchestrator` 独占。Schema 不变。
- `pd`、`architecture`、`infrastructure`、`rtl-design`、`memory-ip` 中已有的一次性 guard 保留原 rule number，现在改为引用共享章节。
- **`validate.yml`**：Agent 必须包含 `## Behaviour Rules`，作为共享区块插入锚点；新增步骤运行 `tools/sync_agent_sections.py --check`。
- **`CONTRIBUTING.md`**：补充同步步骤；修正 “Adding a New Skill” 和本地校验示例中的错误路径（过去误写成不存在的根目录 `skills/`）；修正数量约束，Skill 数可以大于 Agent 数。
- 修正 `CONTRIBUTING.md`、`docs/MASTER_INDEX.md`、`memory/README.md`、`FUTURE_WORK.md` 中过时的数量统计。

### fix/signoff-achieved-template branch

#### 修复

- **13 个 Orchestrator**：`experiences.jsonl` 模板原来写死 `"signoff_achieved": true`，但外围规则又要求 escalation/abandonment 时也写该记录（issue #74）。`distill.py` 使用 `is True` 统计 sign-off，因此默认 true 会把失败 run 错记成成功。模板现统一默认 false，与 `pd` 和 `infrastructure` 保持一致，并在模板下直接说明什么时候才允许改为 true（`soc` 过去没有该说明）。使用 literal `false`，而不是 `"<true|false>"` 字符串，因为字符串永远不会满足 `is True`。`memory/README.md` 的 canonical schema 也同步修正。
- **8 个 Orchestrator**（`dft`、`firmware`、`fpga`、`memory-ip`、`rtl-design`、`sta`、`synthesis`、`verification`）：过去写着 “append one JSON line”，同时模板又没有 `run_id`，与 `memory/README.md` 及各自 Skill 自相矛盾。现在统一按 `run_id` upsert。`fpga` Skill 曾有一套独立 append-only schema（`stage`、`outcomes`、`metrics`、`tools`），`distill.py` 无法从中读取 metrics，现在改为引用共享 record schema。README 也不再称该文件为 append-only。
- **6 个 Orchestrator**（`architecture`、`dft`、`firmware`、`formal`、`fpga`、`hls`）：history 中 `decision` enum 漏了 checkpoint gate 实际会写入的 `await_approval`，现已补齐。

#### 新增

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

## [1.7.0] — feat/semantic-experience-search branch

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

## [1.5.11] — feat/agent-auto-detect branch

### 变更

- **`bin/install.mjs` 现在原生使用 Node 安装全部 5 个 target**，不再依赖 Python。过去仅存在于 `install.sh` Python block 中的 Copilot/Gemini/OpenCode/Codex generator 已移植到 Node，生成结果在除绝对路径和 “Generated by” 注释外与原实现 byte-identical。Gemini/OpenCode 会嵌入 runtime file reference，因此使用 `npx` 时，相关 payload 会复制到持久路径 `~/.digital-chip-design-agents/payload/`，避免 npm 临时 package 目录回收后引用失效。显式 `--ide`（包括 `all`）跳过自动检测并保持原行为。
- **`install.sh` / `install.ps1`** 也增加同样的自动检测模式，当未指定 `--ide` / `-IDE` 时默认启用。它们仍需要 `python3`，因为 Claude 安装逻辑用 Python 读取 plugin version 并 merge `settings.json`；完全无 Python 的路径是 npm 安装器。
- **`README.md`**：补充自动检测、`--yes`，并明确 npm 路径现在支持全部 target。

## [Unreleased] — feat/structured-failure-handling 分支

### 新增

## [1.5.3] — feat/structured-failure-handling branch

### 变更

- **`format_version "1.5"`**：新增能力层，覆盖 `retry_strategy` 和程序化 retry branching。全部 14 个写 history 的 Orchestrator（13 个 domain + infrastructure）首次写入时升级到 1.5；包括原本从 1.3 起步的 compiler/firmware/infrastructure。旧版本继续可读，缺失 `retry_strategy` 时可从 `failure_class` 推导。
- **全部 14 个 Orchestrator + `pipeline-orchestrator.md`**：Stage Agent Output Format 与 `history[]` schema 增加 `retry_strategy`（现在 10 字段）；per-stage trace 行为规则要求正确填写该值；format_version upgrade 同步更新。
- **CI（`validate.yml`）**：`VALID_FORMAT_VERSIONS` 加入 1.5；新增 `VALID_RETRY_STRATEGY`、`RETRY_STRATEGY_MAP` 和 `check_retry_strategy`，验证 1.5 history entry 中 `retry_strategy` 是否同时与合法值及对应 `failure_class` 映射一致；两份 fixture 都会检查。
- **`memory/README.md`**：在 history 字段说明中增加 `retry_strategy`，并补充 format_version 1.4 / 1.5 层级。

## [Unreleased] — feat/infrastructure-memory 分支

### 新增

## [1.5.3] — feat/infrastructure-memory branch

### 变更

- **`memory/README.md`**：Directory Layout 新增 `infrastructure/`；Domain key_metrics 表增加 infrastructure 行；新增 “Infrastructure memory (opt-in, environment-keyed)” 章节，说明激活条件和按环境分键的 record。
- **`infrastructure-orchestrator.md`**：新增 Behaviour Rule 8 和 “Infrastructure Memory” 章节，定义 activation gate、session-start read、`environment_validation` 后 upsert，以及 environment-keyed schema。

## [Unreleased] — feat/central-constraint-handling 分支

### 新增

## [1.5.2] — feat/central-constraint-handling branch

### 变更

- **`format_version "1.4"`**：新增 constraint object、stage-entry validation 和 `pending_approval.type:"constraint_gap"`。全部 15 个 Orchestrator 首次写入时升级到 1.4；旧版仍兼容：没有 constraints 时使用 optional default，缺失 pending_approval.type 时视为 escalation。
- **Architecture Orchestrator**：constraints stub 从扁平 `{clk_mhz, area_um2, power_mw}` 扩展为完整 nested schema；新增 Behaviour Rule 8（`spec_analysis` 阶段填充 constraint）和 Rule 9（required key 仍为 null 时 hard-fail）。
- **全部 11 个 domain Skill**：QoR Metric 和使用约束的 Domain Rule 改为引用 `design_state.constraints.<key>`，并保留旧 literal 作为 documented default；每个文件新增 `## Constraint Validation`，列出 required/optional key。
- **`formal`、`dft` Orchestrator**：Design State Read 增加 `constraints`。
- **CI**：无需新增 schema-validation 逻辑，修改对象均已由现有 Markdown/JSON 检查覆盖。

---

## [1.5.1] — feat/approval-gates-traceability branch

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

## [1.5.0] — feat/rtl-verify-feedback-loop branch

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

## [1.4.4] — agent-scope-review branch

### 新增
- **运行前上下文（Pre-run Context）**：全部 13 个领域 SKILL.md 每次调用均读取 knowledge.md 与 run_state.md，不仅限于编排会话开始。
- **运行状态跟踪**：全部 13 个领域 Skill 和 PD 编排器在执行工具前先写入 `memory/<domain>/run_state.md`，每阶段后更新 last_stage，使唤醒提示可正确恢复。
- **逐阶段经验写入**：PD 编排器及全部领域 Skill 每阶段后按 run_id 更新 experiences.jsonl，中断时也保存部分运行。
- **可选 claude-mem 集成**：13 个领域 Skill 与 memory-keeper 在 MCP 可用时向 `mcp__plugin_ecc_memory__add_observations` 写入已应用修复；不可用时静默跳过，JSONL 保持权威记录。
- **时钟门控机会分析**：architecture 的 power_area_estimation 按活动因子 α 分类时钟域，生成 clock_power_budget 交接表（域、频率、α、估算时钟功耗、门控类别），新增 QoR 门控：可门控域至少覆盖 70% 寄存器位。
- **电源意图与 ICG 插入规则**：rtl_coding 读取架构交接的 clock_power_budget，对高/中等门控机会域插入 ICG，要求 clock_gating_coverage ≥60%。
- MASTER_INDEX 的 Architecture → RTL 合约增加 clock_power_budget。
- memory/README 补充 run_state.md、逐阶段写入、run_id 字段及可选 claude-mem 索引方式。
- 架构和 RTL 流程文档同步上述门控分析与 ICG 规则。
- OpenROAD MCP 配置注释明确安装时必须替换的两个占位值。

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
