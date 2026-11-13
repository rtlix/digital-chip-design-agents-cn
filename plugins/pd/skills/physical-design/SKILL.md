---
name: physical-design
description: >
  完整 Physical Design 流程——floorplan、placement、CTS、routing、timing/power/area
  optimization 和 tape-out sign-off。适用于把 gate-level netlist 实现到 GDS-II，
  做 timing/power closure，或分析任意单个 PD stage。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill: Physical Design（物理设计）

## Invocation
- 用户直接提出 PD 任务：立即启动 `digital-chip-design-agents:physical-design-orchestrator`，
  传入完整请求与上下文，不直接执行 stage。
- 由 physical-design-orchestrator 中途调用：不要再次启动 Agent；本文件只作为规则库。

## Pre-run Context

`<MEM>` below is the resolved memory root（以下 `<MEM>` 表示已经解析出的 Memory 根目录），never the literal `memory/` directory。解析优先级为显式 `--memory-root` → `$CHIP_DESIGN_MEMORY_ROOT` → 中央默认路径 → 仓库 seed；可运行 `python3 plugins/infrastructure/skills/memory-keeper/memory_root.py` 查看实际路径。
任何 stage 前，如存在则读取：
1. `<MEM>/pd/knowledge.md`
2. `<MEM>/pd/run_state.md`
并应用已知 failure pattern、tool flag、PDK quirk 和 run state。

## Purpose
指导从 gate-level netlist 到 tape-out-ready GDS-II 的完整物理实现流程。
八个 stage 都有明确 QoR gate 与 loop-back criteria，由 Orchestrator 强制执行。

---

## Supported EDA Tools
### Open-Source
- **OpenROAD / ORFS**：完整 PD pipeline
- **LibreLane / OpenLane2**：基于 OpenROAD 的 sequential pipeline
- **KLayout**：DRC/LVS/GDS viewer/editor

### Proprietary
- **Cadence Innovus** (`innovus`，命令方言 `cadence`） — 从布局规划到签核，支持交互及批处理模式
- **Synopsys IC Compiler 2** (`icc2_shell`，命令方言 `synopsys`） — 使用 Fusion 技术的层次化物理设计
- **Siemens Aprisa** （命令方言 `siemens`） — 先进工艺节点的物理实现

### Sequential Flow Log Review
ORFS/LibreLane 一次 invocation 会顺序跑完整 pipeline，中途不会等待 Agent。
运行结束或中途失败后，Agent 必须读取 per-stage log 再判断 QoR/loop-back。

**ORFS log：**
```
logs/<platform>/<design>/
  1_1_yosys.log
  2_1_floorplan.log
  3_1_place.log
  3_4_resizer.log
  4_1_cts.log
  5_1_route.log
  5_3_fillcell.log
  6_1_finishing.log
```
启动：`make DESIGN_CONFIG=./designs/<platform>/<design>/config.mk`
从 stage 恢复：`make do-<stage>`

**LibreLane log：**
```
runs/<design>/<run_tag>/logs/
  synthesis/
  floorplan/
  placement/
  cts/
  routing/
  signoff/
```
启动：`openlane <config.json>`
恢复：`openlane --from <step_name> <config.json>`

Agent 流程：
1. 根据 log timestamp/exit code 找最后成功 stage
2. 读取每个完成 stage 的 log，提取 WNS、DRC、congestion、IR drop 等 QoR
3. 应用本 Skill loop-back，修 config/constraint
4. 从失败 stage 重新启动

---

## Stage: floorplan

### Domain Rules
1. Core utilization target = `constraints.area.utilization_pct_target`%，默认 75%。
2. Macro 放 die edge/corner 并留 halo，常见 5–10 μm。
3. IO pad 均匀分布并匹配 package pin assignment。
4. Power grid strap 间距按工艺节点规则。
5. Analog/RF macro 周围设置 hard blockage。
6. 除非 package 限制，aspect ratio 尽量接近 1:1。
7. Voltage island boundary 对齐 row boundary。

### QoR Metrics to Evaluate
- H/V congestion >80% 告警
- Floorplan-stage WNS <−2 ns 告警
- IR drop > 2× `power.ir_drop_pct_max` 告警，默认阈值 10% VDD

### Output Required
- floorplan.def
- Power-grid DEF/script
- Macro placement report
- Congestion map

---

## Stage: placement

### Domain Rules
1. global → legalise → detailed → pre-CTS optimization。
2. Pre-CTS 使用 ideal clock，uncertainty = skew + jitter estimate。
3. 每 partition utilization 不超过 80%。
4. High-fanout net 在 placement 前 buffer 或加 constraint。
5. Timing-critical cell 尽量 co-locate。
6. Scan chain placement 后 reorder 降低 wirelength。

### QoR Metrics to Evaluate
- Pre-CTS WNS > −0.3 ns；最终 target 由 `timing.wns_ns_target` 决定
- Density hotspot >90% 告警
- Utilization > `area.utilization_pct_max`（默认 85%）告警
- Routing congestion overflow >1% 告警

### Output Required
- Placed DEF
- Pre-CTS setup/hold report
- Density/congestion report

---

## Stage: cts

### Domain Rules
1. Target skew < `timing.skew_ps_max`，默认 100 ps。
2. Clock max transition ≤ `transition_ps_max`，默认 200 ps。
3. Clock-buffer fanout ≤ `fanout_max`，默认 16–32。
4. Useful skew 只有 sign-off 明确批准时使用。
5. Clock gating 与 CTS 集成并检查 enable timing。
6. 多 clock domain 独立处理，CTS 后重新检查 CDC。

### QoR Metrics to Evaluate
- Global skew >1.5× target 告警
- Insertion delay > `insertion_delay_ps_max`（默认 500 ps）告警
- Post-CTS setup WNS <−0.2 ns 告警
- Routing 前 hold slack 必须 ≥0

### Output Required
- Post-CTS DEF
- Clock tree skew/insertion report
- Post-CTS setup/hold report

---

## Stage: routing

### Domain Rules
1. global → track assignment → detailed → search-and-repair。
2. 遵循 foundry DRC deck。
3. Critical clock/analog net shield。
4. Upper metal 优先 power，lower metal 主要 signal。
5. Antenna violation 用 diode/jump-via 处理。
6. 先进节点处理 double/multi-patterning color violation。

### QoR Metrics to Evaluate
- Sign-off DRC = 0
- LVS error = 0
- Post-route WNS <0 告警
- Routing overflow = 0

### Output Required
- Routed DEF
- DRC/LVS report
- Post-route timing report

---


## Stage: extraction

### Domain Rules
1. 最终 routed DEF/GDS 使用独立 extractor 生成 sign-off parasitics；实现工具自己的 RC 只作为 native 诊断值。
2. 每个 PVT/RC corner 都记录 extractor、版本、tech file、layer map、netlist/DEF md5。
3. Sign-off library 必须完整，**including every macro's `.lib`**；SRAM/macro 缺 view 属于 `input_setup`，不能靠重跑 extraction 修复。
4. Commercial extractor tech 必须与 open/reference extractor 相关性验证。StarRC 常见路径为 **`grdgenxo` → `nxtgrd`**；Quantus 为 **`Techgen` → `qrcTech`**。
5. **Correlate** commercial vs reference extractor 的 total C、coupling C、critical-net R/C。超过约定 tolerance 时继续只能标记 **`indicative`**，不得静默选一个。
6. SPEF 缺失、空、stale 属于 tool result failure；layer/tech/corner 映射错误属于 input_setup。
7. Open PDK sign-off 可使用 OpenRCX/Magic extraction；商业工具没有 foundry deck 时不能伪称 foundry sign-off。

### QoR Metrics to Evaluate
- 每个 required RC corner 均有非空 SPEF
- Clock/timing nets annotation 完整
- Commercial/reference RC correlation 在约定 tolerance 内，或明确标记 indicative
- SPEF provenance/md5 完整

### Output Required
- 每 corner SPEF
- extractor/tech/corner mapping report
- correlation report
- `pd.spef` (a list of extracted parasitic files, one per RC corner)

---

## Stage: ir_em

### Domain Rules
1. 在最终 routed database 与最终 power grid 上运行 static IR；有 activity/vector 时再跑 dynamic IR。
2. 最坏 IR drop 必须低于 `constraints.power.ir_drop_pct_max`。
3. Signal/PG EM violation 都必须为 0；没有正确 EM rule/current model 时结果只能 NOT RUN。
4. Power grid 为空、macro PG pin floating、strap/via 缺失属于 connectivity/floorplan 问题，不是 power-optimization 数字调参问题。
5. Power sign-off 与 timing 一样使用 extracted parasitics 和统一 activity assumptions。
6. RedHawk/Voltus 结果必须能追溯到 grid、power file、tech rule 和 activity source。

### QoR Metrics to Evaluate
- static_ir_drop_pct < target
- dynamic_ir_drop_pct < target（若运行）
- em_violations = 0
- power_mw 已记录

### Output Required
- Static/dynamic IR report
- EM report
- power-grid connectivity evidence
- per-domain power summary

---

## PDK Enablement

商业工具使用 open PDK 时，很多 view 需要自己构建，不能假设 PDK 原生提供 NDM、TLU+、nxtgrd、qrcTech、Calibre deck。

### Measured on Sky130
- Liberty Compiler 在部分库构建结束时 **segfaults at process exit**，但在此前已经写出有效 DB；必须验证输出而不是只看进程退出。缺失 cell/pin 可见 **LIB-007**。
- NDM workspace 需要 gapless site/row 定义；不完整 physical view 可能触发 **DPUI-924**。Timing library 建议 **one pane per corner**，并运行 `check_workspace -allow_missing`；PVT metadata 问题可出现 **PVT-030**。
- Tech/import 过程中遇到单位或 attribute 问题可见 **UID-109**。
- StarRC：用 **grdgenxo** 和 `-itf2TLUPlus` 生成 TLU+/nxtgrd；实测需处理 **LBMISC-215479**。
- Quantus/Techgen：实测碰到 **IMPEXT-6091**、**IMPEXT-3548**；Sky130 layer 名需把 **`li1` → `met0`** 映射。相关 extraction threshold 使用 `COUPLING_ABS_THRESHOLD: 0.1`。
- Calibre 不一定有 foundry deck；仅有 `.calibre` 环境文件不能等价于 sign-off deck。
- Innovus tech import 可能出现 **TEC-011**；MMMC 构造使用 `create_timing_condition`。
- ICC2 导入 floorplan 时可先使用 **TRACKS-only DEF**；server/feature 问题可能出现 **SVR-4**。
- Open PDK sign-off 主路径仍是 **Magic and KLayout for DRC, Netgen for LVS**，除非确实拿到商业 foundry deck。

## Tool Notes: Cadence Innovus

以下为 **23.14-s088_1** 实测要点：
- Analysis view 要带 `-latency_file`，修改 view 后运行 `update_constraint_mode`；使用 `set_ccopt_property update_io_latency false` 时注意 **virtual ideal I/O clock** 的语义。
- 部分命令/对象错误可见 **TCLCMD-997**。Hold closure 实测使用 `setOptMode -holdTargetSlack 0.2`；native timing 曾比统一 judge **0.17 ns optimistic**。
- Power comparison 必须统一 activity；实测 Innovus 默认/设置 **activity 0.2**，可用 `set_default_switching_activity`。
- **`create_inst` returned without placing anything** 的场景改用 `addInst`，并按需要 `-physical`。
- **`create_shape` does not exist**；某些版本里 **`editAddRoute` did nothing**，PG/metal shape 使用 `add_shape` 等实际支持命令。
- ECO 后先 **`refinePlace` before `ecoRoute`**。Antenna 运行 `check_antennas`，修复策略包括 **Taps at the source**。
- 常见 rule/message：**npc.2**、**IMPCCOPT-2440**、**IMPOPT-7027**、**PIN**。

## Tool Notes: Synopsys ICC2 / Fusion Compiler

以下为 **X-2025.06-SP1** 实测：
- 首次启动/载入复杂库可能 **30-65 min**。Layer policy 使用 `global_min_layer_mode`；必要约束应设为 **`hard`**，不能依赖 soft preference。
- PG via 定义用 `set_pg_via_master_rule`；scenario PVT 用 `set_process_number`、`set_voltage`、`set_temperature`。
- 多对象命令注意 `-object_list`；错误用法可触发 **CHF-002**；STA/power 报告按 `-scenarios`。
- Hold repair 避免只用 weak **`ZBUF`/`ZINV`**；通过 `set_lib_cell_purpose -include hold` 明确可用 cell。**`add_buffer` drops the new cell off the row grid** 时必须合法化。
- Fat wire 使用 **fat_table**；实测为避免 strap spacing DRC，需要 **0.1 um met4 routing blockages**；相关 rule 如 **m4.5ab**。
- Pin access 可用 `set_routing_rule -min_routing_layer met3 -min_layer_mode allow_pin_connection`。
- Antenna ECO：`diode_mode 1`，可 **drive the antenna ECO from the OpenROAD list**，但需重新 DRC。
- 名称匹配可能需 `-case_insensitive`；sign-off netlist 可用 `write_verilog -exclude supply_statements`。
- GDS merge 使用 `-merge_gds_top_cell`；block/version 管理可用 `copy_block`。

## Tool Notes: Synopsys StarRC

**X-2025.06-SP1** 实测：
- DEF 输入用 `TOP_DEF_FILE`；常见诊断 **SX-0271**、**SX-1907**、**SX-2064**。
- 为和 reference extractor 做可比 correlation，可设置 `COUPLING_REL_THRESHOLD: 0`；必要时 `LEF_USE_OBS: NO`。
- 大量短路报告要设置合理 `SHORTS_LIMIT`，但不能用 limit 掩盖真实 extraction setup 问题。

## Tool Notes: Ansys RedHawk

**2025 R2.2** 实测：
- **`INSTANCE_POWER_FILES` must be plural**；单数形式可能被 **accepted silently and ignored**。
- Instance naming/input 建议 **escape-free**；缺 power mapping 可在报告中看到 **ipfMissing**。
- IR 输出可用 `write_rh_file -filetype irdrop`；DEF 容错可见 `IGNORE_DEF_ERROR 1`，但 **ITG-016** 等连接错误必须 root-cause。
- Pad/location 文件常为 **`.ploc`**；自动 EM 可配置 `ENABLE_AUTO_EM 1`。
- 以 PEAK current 对 DC limit 跑出的 EM 数字 **not a valid pass/fail**；sign-off 应 `perform emcheck -mode AVG` 或按 foundry rule 对应 mode。
- `DECAP_CELL` 列表与 power-grid 结果会 **depend on decap** 配置，比较时必须一致。

## Tool Notes: Magic, KLayout and Netgen on a commercial GDS

实测版本包括 Magic **8.3.489**、KLayout **0.29.4**、Netgen **1.5.278**。
- Full-chip Magic DRC 可能需要 **11 GiB** 以上内存；不要只凭某一个工具 **alone** 宣告 clean。
- Open-PDK macro/black-box 边界的 DRC 要特别确认 **inside the SRAM footprints** 是否由 macro deck/waiver 正确处理。
- Sky130 常见 well rule 如 **`nwell.4`**；LVS/抽取时端口必要时通过 `port make` 明确化。

## Stage: timing_optimization

### Domain Rules
1. Multi-corner：SS setup、FF hold、TT typical。
2. Setup：driver upsize、repeater、retiming。
3. Hold：插入 HVT delay buffer。
4. Vt swapping：critical path 用 SVT/LVT；非 critical 可 HVT。
5. ECO：formal ECO → reserved site placement → reroute ECO net。
6. 未经 DFT 批准不得改 scan-chain order。
7. 按 foundry sign-off agreement 应用 POCV/AOCV。

### QoR Metrics to Evaluate
- 所有 corner WNS ≥ `wns_ns_target`
- TNS = `tns_ns_target`，默认 0
- Hold slack ≥0
- ECO cell >2% 总 cell 时告警

### Output Required
- All-corner timing closure report
- ECO list
- SPEF
- Post-ECO routed DEF

---

## Stage: power_optimization

### Domain Rules
1. Dynamic：clock gating、operand isolation、multi-Vt。
2. Leakage：非 critical cell 换 HVT，每批后重查 timing。
3. Power domain：验证 UPF isolation/level shifter/retention。
4. Voltage island：逐域检查 IR drop。
5. Always-on logic 使用正确 library cell。
6. Power gating：修改 routing 前验证 wakeup/shutdown sequence。

### QoR Metrics to Evaluate
- Total power ≤ `power.power_mw`
- Leakage ≤ `leakage_pct_max`%，默认 15%
- IR drop < `ir_drop_pct_max`% VDD，默认 5%
- Post-opt WNS ≥ target

### Output Required
- Dynamic/static per-domain power report
- IR-drop report
- Post-power-opt DEF
- UPF compliance report

---

## Stage: area_optimization

### Domain Rules
1. 删除冗余 buffer/inverter pair。
2. 非 critical cell downsize。
3. 回收 unused standard-cell site。
4. WNS margin 不低于 50 ps buffer。
5. Area ECO 后重跑 DRC。

### QoR Metrics to Evaluate
- Core utilization target 默认 75%，hard limit 默认 85%
- WNS ≥ target
- DRC 保持 clean

### Output Required
- Pre/post area report
- Updated DEF
- Cell-count breakdown

---

## Stage: signoff

### Sign-off Pass Criteria
| Check | Criterion |
|---|---|
| Setup WNS | ≥ `timing.wns_ns_target`，所有 corner |
| Setup TNS | = `timing.tns_ns_target`，所有 corner |
| Hold WNS | ≥ target，所有 corner |
| DRC | 0 |
| LVS | 0 |
| Antenna | 0 |
| IR drop | < `power.ir_drop_pct_max`% VDD |
| Metal density | Foundry window 内 |

### Domain Rules
1. STA sign-off 跑全部 required PVT + POCV/AOCV。
2. 使用 foundry-approved DRC deck，0 violation。
3. LVS netlist vs layout，0 error。
4. ERC 做 EM/IR sign-off。
5. Final GDS merge 全 layer、seal ring、chip-level DRC。

### Failure Escalation
- Timing fail → timing_optimization
- DRC/LVS fail → routing
- Power/EM fail → power_optimization

### Output Required
- All-corner sign-off STA
- DRC clean report
- LVS clean report
- Final GDS-II
- Tape-out checklist

---

## Constraint Validation
进入 `floorplan` 必须有：
- `clock.clk_mhz`
- `area.area_um2`
- `power.power_mw`
- 至少一个有效 V/T 的 `pvt_corners`

Optional timing/area/power threshold 使用 schema default。

---

## Memory

### Run state
任何工具前第一步写 `<MEM>/pd/run_state.md`，包含 run_id/design_name/pdk/tool/start_time/last_stage。

### Write on stage completion
每 stage 完成后按 `run_id` upsert `<MEM>/pd/experiences.jsonl`，
不得同一 run 追加第二行。最终 sign-off 前 `signoff_achieved:false`。
Record 必须在 JSON object 内包含顶层 `run_id`。

### Optional: claude-mem index
如 memory observation 工具可用，把新 fix 写到 `chip-design-pd-fixes`；否则跳过。
