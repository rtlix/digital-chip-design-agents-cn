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

`<MEM>` 表示已经解析出的 Memory root，而不是字面量 `memory/` 目录。解析优先级为：显式 `--memory-root` → `$CHIP_DESIGN_MEMORY_ROOT` → 中央默认路径 → 仓库内 seed；可用 `python3 plugins/infrastructure/skills/memory-keeper/memory_root.py` 查看实际路径，最终以 Orchestrator 的 `## Memory` 章节为准。为保持上游 contract 可检测：`<MEM>` below is the resolved memory root。
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

## PDK Enablement

商业 P&R / extraction / sign-off 工具需要完整的 logical + physical + RC view。一个 flow 的输入包至少包含 technology definition、std-cell/macro LEF、所有 timing corner（**including every macro's `.lib`**）、GDS/CDL、RC tech、layer map 和 sign-off deck。Open PDK 缺商业格式时，必须先从公开 tech/LEF/Liberty 构造并验证这些 view；构造出来的商业 view 需要与开源 reference flow **Correlate**，否则后续数值只能标 `indicative`。

跨 extractor 技术转换通常类似：
- Synopsys extraction：`grdgenxo` → `nxtgrd` / TLU+，并保留 layer/map 一致性。
- Cadence extraction：`Techgen` → `qrcTech`。
- Open sign-off：**Magic and KLayout for DRC, Netgen for LVS**，必要时与 Calibre/PVS 商业 deck 结果交叉检查。
- `pd.spef` 应保存为 **a list**（`"spef": [...]`）以支持 nom/min/max 或更多 RC corner，而不是单一路径。

### Measured on Sky130

以下是把 Sky130 开源 PDK enable 到商业 flow 时的实测陷阱，必须作为 recipe 的一部分保留：
- Library/NDM 生成过程中某些工具在成功写完输出后会 **segfaults at process exit**；不能仅凭进程崩溃否定已完成 artifact，也不能仅凭文件存在判 PASS，必须先检查 log 中实际 build/check result。观察到过 `LIB-007`。
- NDM/workspace 需要 **gapless** layer/track/physical view；缺失会触发 `DPUI-924`。多 PVT 库按 **one pane per corner** 组织；用 `check_workspace -allow_missing` 区分允许缺失与真正错误，留意 `PVT-030`。
- 部分 library command 的对象/语法错误会出现 `UID-109`；不要把 shell wildcard 当 lib-cell object。
- RC 生成：`grdgenxo` + `-itf2TLUPlus`，并检查 `LBMISC-215479`；Cadence/Quantus enablement 中记录 `IMPEXT-6091` / `IMPEXT-3548`。
- Sky130 层名转换可能要求 **`li1` → `met0`**。ICT/ITF 相关 threshold 实测使用过 `COUPLING_ABS_THRESHOLD: 0.1`。
- Foundry/open-source deck 可能通过 `.calibre` / layer-map 间接引用规则；缺失或映射错误可表现为 `TEC-011`。
- MMMC/physical-view 构建中会用 `create_timing_condition`；Innovus/Genus 的 dialect 不完全相同。
- 仅有 routing tracks 的 DEF 属于 **TRACKS-only DEF**，不能冒充完整 floorplan/placement DEF；相关恢复/转换时观察到 `SVR-4`。

---

## Tool Notes: Cadence Innovus

实测版本 **23.14-s088_1**。以下事项会直接影响 timing/power/route 的可信度：
- MMMC I/O latency 不能只靠主 SDC；view 需要 `-latency_file`，并用 `update_constraint_mode` 更新。若使用 CCOpt，明确 `set_ccopt_property update_io_latency false` 与外部 latency 的 ownership；**virtual ideal I/O clock** 的网络/latency 语义要与 sign-off STA 对齐。
- MMMC dialect/command 可能报 `TCLCMD-997`；hold closure 常用 `setOptMode -holdTargetSlack 0.2`。实测 native timing 可比统一 judge **0.17 ns optimistic**。
- Power comparison 要统一 activity；Innovus native flow 使用过 **activity 0.2**，对应命令 `set_default_switching_activity`，不能与另一个工具默认 0.1 的结果直接比较。
- 实测 `create_inst` returned without placing anything；批量插 cell 使用 `addInst`，需要时加 `-physical` 并随后合法化。
- `create_shape` does not exist；某些版本下 `editAddRoute` did nothing；可用 `add_shape`。ECO cell 放置后应先 `refinePlace` before `ecoRoute`。
- Antenna 使用 `check_antennas`，必要时 **Taps at the source**；记录 `npc.2`、`IMPCCOPT-2440`、`IMPOPT-7027` 等具体 rule/message。不要只靠文本 “PIN” 计数，需定位实际违反对象。

---

## Tool Notes: Synopsys ICC2 / Fusion Compiler

实测 ICC2 **X-2025.06-SP1**；某些大型启动/load database 流程需要 **30-65 min**，因此必须遵守 Long-Running Jobs。
- Routing layer 限制的 `global_min_layer_mode` 可能只是 soft；需要时使用 `hard` mode 并验证实际 route。
- PG 建网可用 `set_pg_via_master_rule`；PVT/scenario 显式设置 `set_process_number`、`set_voltage`、`set_temperature`。
- 某些 report/constraint 命令要求 `-object_list`；错误参数可见 `CHF-002`；multi-scenario 查询明确 `-scenarios`。
- Hold repair 若只允许 **weak `ZBUF`/`ZINV`**，先用 `set_lib_cell_purpose -include hold` 配置可用 cell。`add_buffer` drops the new cell off the row grid 时必须重新 legalize，不能直接 route。
- `fat_table` / power strap 邻近 spacing 可能需要额外 **0.1 um met4 routing blockages**；实测 rule `m4.5ab`。
- Pin connection 例外可用 `set_routing_rule -min_routing_layer met3 -min_layer_mode allow_pin_connection`，但不能放宽普通 signal route。
- Antenna 可设置 `diode_mode 1`；若商业工具报告不稳定，可 **drive the antenna ECO from the OpenROAD list**，但最终仍需同一 sign-off deck 复核。
- 名称查找可用 `-case_insensitive`。输出 netlist 用 `write_verilog -exclude supply_statements`；GDS 处理记录 `-merge_gds_top_cell` 与 `copy_block`。

---

## Tool Notes: Synopsys StarRC

实测 **X-2025.06-SP1**：
- DEF flow 以 `TOP_DEF_FILE` 明确输入；遇到 `SX-0271`、`SX-1907`、`SX-2064` 时先判断 layer/name/short 设置，而不是直接重跑。
- 为相关性分析可设置 `COUPLING_REL_THRESHOLD: 0`，并显式决定 `LEF_USE_OBS: NO` 是否符合本 PDK。
- `SHORTS_LIMIT` 只是 report/control 参数，不能把真实 short “限制掉”后宣告 clean。

---

## Tool Notes: Ansys RedHawk

实测 **2025 R2.2**：
- 关键字 **`INSTANCE_POWER_FILES` must be plural**；写成 singular 的 `INSTANCE_POWER_FILE` 可能 **accepted silently and ignored**，造成看似成功但没有 instance power 的假结果。
- Instance-name mapping 需 **escape-free** 且与 DEF/netlist 一致；检查 `ipfMissing`。
- 输出可用 `write_rh_file -filetype irdrop`。某些 DEF warning 可在充分 root-cause 后用 `IGNORE_DEF_ERROR 1`，但 `ITG-016` 等 grid/connectivity 问题不可压掉。
- Pad/location 输入常用 `.ploc`。自动 EM 相关 `ENABLE_AUTO_EM 1` 不代表所有 metal/via rule 都已校准。
- PEAK-mode EM 若拿 DC current limit 直接比较，**not a valid pass/fail**。平均电流 sign-off 使用 `perform emcheck -mode AVG` 或 PDK 指定模型。
- `DECAP_CELL` / decap insertion 会改变 IR；任何 “通过”若 **depend on decap**，必须把 decap 数量/位置纳入 artifact 和复验。

---

## Tool Notes: Magic, KLayout and Netgen on a commercial GDS

实测工具版本包括 Magic **8.3.489**、Netgen **1.5.278**、KLayout **0.29.4**。大型 merged GDS 的 Magic DRC 在小主机上可超过 **11 GiB**，因此不能 **alone** 依赖单一工具/单次运行；要用资源上限和可恢复日志。
- SRAM macro 周边的 DRC 要区分 macro 内部、边界与 top-level route；某些 finding 实际发生 **inside the SRAM footprints**。
- Sky130 `nwell.4` 等规则应根据 deck/waiver ownership 分类，不能因 hard macro 内部图形而擅自改 top-level。
- Netgen/LVS 的 macro pin/port 名需要正确导出；必要时在 Magic extraction 中使用 `port make`，并验证 schematic/layout 端口一一对应。

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
1. 对 final routed database 在所需 RC corner 生成 parasitics。开放 flow 优先 OpenRCX；商业 flow 可用 StarRC/Quantus。
2. 提取输入必须与 PDK stack 一致：tech file、layer map、corner mapping、macro obstruction/view。输入不匹配属于 `input_setup`，不是通过重跑 extractor 能修好的 tool error。
3. 输出 SPEF 每个 corner 独立命名，并记录 source DEF/GDS、tech、corner、md5；`pd.spef` 保存为 list。
4. 使用 sign-off STA 的 annotation gate 检查未标注 timing nets；超过阈值不能进入 sign-off。
5. 商业 extractor 与 reference extractor 做 correlation；超 tolerance 时 downstream timing/power 标 `indicative`，不静默选择“更好看”的一套。

### QoR Metrics to Evaluate
- SPEF file：存在、非空、时间戳属于本 run
- Unannotated timing nets：≤1%，sign-off target 按 STA annotation gate
- Corner coverage：全部 required RC corner
- Commercial/reference correlation delta：记录

### Output Required
- 每 corner SPEF
- Extraction log / annotation summary
- Tech/layer/corner provenance
- Correlation report（若有 reference extractor）

---

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

## Stage: ir_em

### Domain Rules
1. 在 final routed database 上分别测 static 和 dynamic IR drop，取 worst 作为 sign-off metric。
2. 使用真实 PG shapes、macro PG pin、pad/package source；zero PG shape、floating macro pin、empty grid 都是 connectivity FAIL，不是“IR=0”。
3. Power input 必须能证明已加载；如 instance power file 被工具静默忽略，结果为 NOT RUN。
4. Signal/PG EM 使用 PDK 对应 current-density/rule model；不把不兼容的 PEAK/DC limit 组合当 pass/fail。
5. IR/EM ECO 后重新 extraction/timing/power，确保修 IR 没破坏 timing。

### QoR Metrics to Evaluate
- `ir_drop_pct` < `constraints.power.ir_drop_pct_max`，static/dynamic worst
- `em_violations: 0`
- `power_mw` ≤ budget；**comparison run, no target** 时只记录不判定
- PG connectivity：完整

### Output Required
- Static/dynamic IR report
- EM violation report
- Power input provenance
- PG connectivity summary
- ECO 前后 comparison（如发生）

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
