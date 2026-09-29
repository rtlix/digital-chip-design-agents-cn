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
任何 stage 前，如存在则读取：
1. `memory/pd/knowledge.md`
2. `memory/pd/run_state.md`
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
- **Cadence Innovus**
- **Synopsys IC Compiler 2**
- **Siemens Aprisa**

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
任何工具前第一步写 `memory/pd/run_state.md`，包含 run_id/design_name/pdk/tool/start_time/last_stage。

### Write on stage completion
每 stage 完成后按 `run_id` upsert `memory/pd/experiences.jsonl`，
不得同一 run 追加第二行。最终 sign-off 前 `signoff_achieved:false`。
Record 必须在 JSON object 内包含顶层 `run_id`。

### Optional: claude-mem index
如 memory observation 工具可用，把新 fix 写到 `chip-design-pd-fixes`；否则跳过。
