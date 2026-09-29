---
name: logic-synthesis
description: >
  从 RTL 到 gate-level netlist 的逻辑综合——SDC constraint validation、compile/optimization
  策略、netlist quality check 和 LEC equivalence verification。
  适用于 ASIC RTL 综合、时序约束设置、timing/area/power 优化或 post-synthesis netlist 验证。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill: Logic Synthesis（逻辑综合）

## Invocation
- **用户直接提出 synthesis 任务**：立即启动
  `digital-chip-design-agents:synthesis-orchestrator`，传入完整请求和上下文，不直接执行 stage。
- **由 synthesis-orchestrator 中途调用**：不要再次启动 Agent；本文件只作为规则库，
  返回所需 stage rule、sign-off criteria 或 loop-back guidance。

在 active Orchestrator 内再次启动自身会造成 recursive delegation，必须禁止。

## Pre-run Context
任何 stage 前，如存在则读取：
1. `memory/synthesis/knowledge.md`
2. `memory/synthesis/run_state.md`
应用历史 failure pattern、有效 tool flag、PDK/tool quirk 与 run state。

## Purpose
从 RTL 生成 timing-clean、area-efficient、LEC-verified 的 gate-level netlist，
覆盖 constraint setup、综合策略和 PD handoff 前的质量检查。

---

## Supported EDA Tools
### Open-Source
- **Yosys** (`yosys`) —— 开源综合；顺序执行 pass pipeline
- **Surelog** (`surelog`) —— Yosys 的 SystemVerilog front-end
- **ABC** —— logic optimization 与 technology mapping

### Proprietary
- **Synopsys Design Compiler** (`dc_shell`)
- **Cadence Genus** (`genus`)
- **Synopsys Fusion Compiler** (`fc_shell`)

### Sequential Flow Log Review (Yosys)
Yosys 的 synthesis script（`yosys -c synth.ys` 或 `yosys -p "synth_*"`）
按 read_verilog → synth → opt → techmap → abc → write_verilog 顺序执行；
前面 pass 的 error/warning 会影响后续结果。

Yosys run 后必须：
1. 读取 log，检查每 pass 的 `Warning:` / `Error:`
2. 读取 final statistics：cell、wire、logic depth
3. 搜索 output netlist 中 `$` 前缀 cell，发现 unmapped primitive
4. 确认 `synth_netlist.v` 存在且非空
5. 使用 ABC timing mode 时解析 area/timing report

ORFS/LibreLane 中典型 Yosys log：
`logs/<platform>/<design>/1_1_yosys.log`

---

## Stage: constraint_setup

### Domain Rules
1. `create_clock`：所有 primary clock，明确 period/waveform/source/name。
2. `create_generated_clock`：所有 derived/divided clock，source 与 ratio 正确。
3. `set_clock_uncertainty`：setup = skew + jitter；若
   `constraints.timing.clk_uncertainty_ps` 已设置则使用该值，否则 pre-CTS 用 200–500 ps rule-of-thumb。
4. `set_input_delay/set_output_delay`：所有 primary IO 都有约束。
5. `set_false_path`：只用于真实 async crossing/test mode/reset 等设计意图。
6. `set_multicycle_path`：必须同时有 setup 与 hold 修正。
7. `set_dont_touch`：hard IP、memory macro、手工 cell。
8. `set_max_fanout`：来自 `constraints.timing.fanout_max`，默认 32。
9. `set_max_transition`：遵循 technology DRC rule。
10. Operating condition 必须显式设置，不能依赖工具默认 corner。

### Common SDC Mistakes
| 错误 | 后果 |
|---|---|
| Generated clock 缺失 | Path unconstrained |
| MCP 无 hold correction | 引入 hold violation |
| False path 过宽 | 掩盖真实时序问题 |
| 未设置 operating condition | 使用错误 library corner |

### QoR Metrics to Evaluate
- `report_clocks`：所有 clock 定义完整
- `report_port -verbose`：所有 IO constrained
- `report_timing -unconstrained`：unconstrained path = 0

### Output Required
- Validated SDC
- Clock summary
- Constraint QA report

---

## Stage: compile_explore

### Domain Rules
1. 使用 worst-case timing corner（SS/low-V/high-T）。
2. 先进行快速 exploration，找更好的 logic structure。
3. 比较 retiming on/off、datapath architecture 等多个方案。
4. Final compile 前人工查看关键 path。
5. 对比 microarchitecture area estimate。

### Optimisation Strategy by Priority
| Priority | Approach |
|---|---|
| Timing | compile_ultra、path_group weighting、retiming |
| Area | high area effort、resource sharing |
| Power | clock gating insertion、power-aware compile |
| Balanced | compile_ultra -no_autoungroup + incremental |

### Output Required
- Exploration timing/area/power report
- Critical path list
- Final compile strategy recommendation

---

## Stage: compile_final

### Domain Rules
1. 工具支持时用 multi-scenario 同时考虑 setup/hold。
2. 启用 clock-gating synthesis。
3. 有 placement intent 的 block 保留 hierarchy。
4. 小 module 可 ungroup，增加跨边界优化机会。
5. Critical path 无法 closure 时，必须回到 RTL restructuring，而不是无限堆 ECO。
6. 初次 compile 后可做 incremental compile 收敛余下 violation。

### QoR Metrics to Evaluate
- WNS ≥ `constraints.timing.wns_ns_target`
- TNS = `constraints.timing.tns_ns_target`
- Area ≤ `constraints.area.area_um2`
- Power ≤ `constraints.power.power_mw`
- Unmapped cell = 0

### Output Required
- Gate-level netlist
- Setup/hold timing report
- Area report
- Power report
- Synthesis log

---

## Stage: netlist_qc

### Checks Required
1. Netlist 中不存在 blackbox/undefined module。
2. 无 combinational loop。
3. DFT-enabled flow 中 scan chain integrity 正确。
4. Tie cell、well tie 等 power/ground connection 正确。
5. RTL vs netlist LEC 必须 PASS。

### LEC Requirements
- Golden：post-lint、post-CDC-clean RTL
- Revised：gate-level netlist
- 所有 compare point 必须 EQUIVALENT
- 任一 UNMATCHED point 在进入 PD 前必须解决

### QoR Metrics to Evaluate
- LEC 100% EQUIVALENT
- Blackbox = 0
- Combinational loop = 0
- Scan-chain integrity verified

### Output Required
- LEC report
- Netlist QC checklist
- Final gate netlist
- Back-annotated SDC for PD

---

## Stage: synthesis_signoff

### Sign-off Checklist
- [ ] Required corner WNS ≥ `timing.wns_ns_target`
- [ ] TNS = `timing.tns_ns_target`
- [ ] Area 在 `area.area_um2` budget 内
- [ ] Power 在 `power.power_mw` budget 内
- [ ] LEC EQUIVALENT
- [ ] 无 blackbox
- [ ] 无 combinational loop
- [ ] DFT 场景 scan chain 已验证

### Output Required
- PD handoff package：netlist、SDC、timing/area/power report

---

## Constraint Validation
进入 `constraint_setup` 必须有：
- `constraints.clock.clk_mhz`
- `constraints.area.area_um2`
- `constraints.power.power_mw`

Optional：
- `timing.wns_ns_target` 默认 0
- `timing.tns_ns_target` 默认 0
- `timing.fanout_max` 默认 32
- `timing.clk_uncertainty_ps` null 时使用 200–500 ps rule-of-thumb

---

## Memory

### Write on stage completion
每 stage 后按 `run_id` upsert `memory/synthesis/experiences.jsonl`。
实现方式为读取全部行、删除同 run_id 旧 record、追加更新后的 record，然后原子替换。
每条 record 必须有顶层 `run_id`：
`synthesis_<YYYYMMDD>_<HHMMSS>`，一次生成全流程复用。
最终 sign-off 前保持 `signoff_achieved:false`。

### Run state
任何工具前第一步写：
```markdown
run_id:      synthesis_<YYYYMMDD>_<HHMMSS>
design_name: <design>
tool:        <primary tool>
start_time:  <ISO-8601>
last_stage:  <first stage name>
```

### Optional: claude-mem index
如 observation 工具可用，把 applied fix 写入 `chip-design-synthesis-fixes`；否则跳过。
