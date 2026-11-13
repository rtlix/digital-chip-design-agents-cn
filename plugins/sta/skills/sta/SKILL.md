---
name: sta
description: >
  静态时序分析——多 corner 约束验证、setup/hold 分析、timing exception 审查、
  ECO closure 指导以及 tape-out timing sign-off。适用于运行 STA、分析 timing violation、
  指导 ECO，或执行最终时序签核。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill: Static Timing Analysis (STA)（静态时序分析）

## Invocation
用户提出 timing analysis 任务时，**不要直接执行 stage**。立即启动
`digital-chip-design-agents:sta-orchestrator`，传入完整请求和上下文。
仅当 Orchestrator 中途读取本 Skill 获取 stage guidance，或用户只问局部参考问题时，
才直接使用这里的规则。

## Pre-run Context

`<MEM>` below is the resolved memory root（以下 `<MEM>` 表示已经解析出的 Memory 根目录），never the literal `memory/` directory。解析优先级为显式 `--memory-root` → `$CHIP_DESIGN_MEMORY_ROOT` → 中央默认路径 → 仓库 seed；可运行 `python3 plugins/infrastructure/skills/memory-keeper/memory_root.py` 查看实际路径。
任何 stage 前，如存在则读取：
1. `<MEM>/sta/knowledge.md`
2. `<MEM>/sta/run_state.md`
应用已知 failure pattern、有效 tool flag、PDK/tool quirk 与恢复信息。

## Purpose
执行 multi-corner、multi-mode STA，审查 timing exception，指导 ECO closure，
并完成 timing sign-off。Tape-out 要求全部 required corner 满足
WNS ≥ target 且 TNS = target（通常 0）。

---

## Supported EDA Tools

### Open-Source
- **OpenSTA** (`sta`) —— standalone STA，batch TCL
- **OpenROAD STA subsystem** (`openroad -no_init`) —— OpenROAD PD flow 内的 STA

### Proprietary
- **Synopsys PrimeTime** (`pt_shell`，命令方言 `synopsys`） — 高标准多角 STA 与功耗分析
- **Cadence Tempus** (`tempus`，命令方言 `cadence`） — 并发多模式多角 STA 与 ECO 指引

### Sequential Flow Log Review (OpenSTA / OpenROAD STA)

### Sequential Flow Log Review
OpenSTA/OpenROAD STA 在 batch mode 按 TCL 命令顺序执行；没有可中途查询的交互 prompt。
完成后必须解析 log：

- `report_timing` → WNS、critical path
- `report_tns` → 各 corner TNS
- `report_clock_skew` → clock skew / insertion delay
- `check_timing` → missing constraint、unconstrained endpoint、loop

典型启动：
```bash
opensta -no_splash -exit timing_check.tcl > sta.log 2>&1
# 或
openroad -no_init -exit sta.tcl > sta.log 2>&1
```

完成后解析 `sta.log`。如果发现 setup/hold violation，按 loop-back 进入 ECO guidance。

---

## Tool Notes: Synopsys PrimeTime (multi-corner) and PrimePower

以下规则来自 **PrimeTime X-2025.06** / PrimePower 在 StarRC SPEF 上的多 corner 实测。

1. 公平比较时每个 (library corner, RC corner) 使用 **one `pt_shell` per (library corner, RC corner)**，避免状态泄漏；输入 library 包括 every macro `.db`。
2. 每个 run 在脚本内校验 **SDC md5**，然后 `read_sdc`；real clock 执行 `set_propagated_clock`，但 propagated **virtual** clock ignores its network latency。
3. RC 用 `read_parasitics -format spef <spef>`。保存 SPEF md5；Annotation gate 使用 `report_annotated_parasitics`，包括 `-pin_to_pin_nets`。PrimeTime 自己的读取摘要写入 **parasitics_command.log**；SPEF 中 net 不存在可见 **PARA-124**。
4. 更新 timing 后运行 `check_timing -verbose`、`report_global_timing`、`report_qor`。设 `report_default_significant_digits 4`，否则极小负 slack 会被舍入成 0。
5. Clean setup 时 `report_global_timing` 可能打印 **No setup violations found.**；脚本必须仍提取 **non-empty setup and hold WNS**，空 metric 不能 PASS。
6. **`read_sdc` stops at the first unsupported command**，但 shell 可能继续执行，造成看似正常却约束不完整的结果。**Innovus-exported SDC is not PT-readable** as-is；必须转换/对比并重新校验 md5。
7. ICC2 写出的 SDC 可能带 `set_clock_latency 1.77814` 等 useful-skew/I/O latency；只能作为 diagnostic variant，公平排名使用 shared SDC。
8. PrimePower vectorless：`power_default_toggle_rate 0.1`，并明确 register output activity。与 OpenSTA 的默认 register-output handling 可产生约 **15 % difference**；必要时对 `[all_registers -output_pins]` 显式设置 activity。
9. SRAM output load 超 Liberty table 范围时，不同 engine 会 **extrapolate**，必须检查 load range，不直接把 engine 差异当 implementation 差异。
10. **Annotation gate.** 超过 1% signal net 未 annotation，或任何 clock net 未 annotation，stage 直接 FAIL(`input_setup`)。**Tempus may be absent**；此时可以 PrimeTime/OpenSTA 做 judge，但必须记录 engine/version。

## Fair Cross-Tool Comparison

不同 P&R/STA 工具之间比较时，必须保证是在比较 implementation，而不是比较“裁判”：

1. **Same SDC.** 每个 flow 读取完全相同的 SDC；结果旁记录 **md5**。
2. **Same extractor and tech.** 用同一个 extractor 与同一个 tech file 对每个最终 DEF/GDS 重新提取相同 RC corner。
3. **Same STA engine.** 使用同一个 sign-off STA engine/version、同一 library/corner/derate。
4. **Same activity assumptions** 用于 power；同一 vectorless default 或同一 SAIF。
5. 工具自己的 timing/power 仍记录，但必须 **labelled `native`**，不能和其他 flow 的 judged number 直接排名。
6. 不满足 1–4 的比较只能写 **indicative**。
7. **Prove each judged run used the inputs it claims.** 每次记录 netlist/SPEF/SDC md5，并与 flow 交付物核对。
8. **Close the implementation in the corners you judge in.** 如果 implementation 只在 tt closure，却拿 ss/ff 去 judge，这测的是 corner scope 缺失，而不只是工具能力。

## Stage: constraint_validation

### Domain Rules
1. 所有 primary clock 都必须定义正确 period/waveform。
2. 所有 generated clock 的 source 与 divide/multiply 关系正确。
3. 不允许 unconstrained path，使用 `report_timing -unconstrained` 验证。
4. CDC path 使用正确的 false_path 或 max_delay。
5. Multicycle path 同时设置 `-setup N` 与 `-hold 1`。
6. Input/output delay 与系统级 timing budget 一致。
7. Timing exception 不得过宽，不能掩盖真实 violation。
8. Pre-CTS 使用 ideal clock，post-CTS 使用 propagated clock。

### Common Constraint Errors
| 错误 | 后果 |
|---|---|
| MCP 没有 hold correction | 引入 hold violation |
| False path 过宽 | 掩盖真实 timing issue |
| Generated clock 缺失 | Path unconstrained |
| Clock period 错误 | Over/under constraint |

### QoR Metrics to Evaluate
- Unconstrained path = 0
- Clock definition error = 0
- 所有 exception 已审查并有文档

### Output Required
- Constraint QA report
- Clock summary
- Exception list + justification

---

## Stage: multi_corner_analysis

### Required Corner Matrix
Corner 来自 `design_state.constraints.pvt_corners[]`。
如果未提供有效 V/T，则下表只是文档化 fallback；但当前 Orchestrator 的 required constraint
规则会在入口阻止缺少有效 PVT 的 sign-off flow。

| Mode | Setup Corner | Hold Corner |
|---|---|---|
| Functional | SS/0.9V/125°C（默认示例） | FF/1.1V/−40°C（默认示例） |
| Test (at-speed) | SS/0.9V/125°C | FF/1.1V/25°C |
| Low Power | SS/0.9V/125°C | FF/1.1V/25°C |

有 `pvt_corners` 时：
- `checks:["setup"]` 的全部 entry 用于 setup
- `checks:["hold"]` 的全部 entry 用于 hold

### POCV/AOCV Application
1. AOCV：按 logic depth 与 location derate。
2. POCV：按 foundry agreement 使用 sigma-based variation。
3. Clock uncertainty：pre-CTS ideal → post-CTS propagated。

### Annotation and engine rules
1. 每个 corner 使用与其匹配的 library 与 RC SPEF，并在报告头记录映射。
2. **Annotation gate.** timing slack 输出前检查 parasitic annotation；>1% signal net 或任一 clock net unannotated 都是 `input_setup` FAIL。
3. Tempus may be absent；可以 PrimeTime/OpenSTA 替代，但每个数字都写明 engine/version。

### Path Analysis Priority
1. 每 corner 的 WNS path
2. TNS contribution
3. 带 max_delay 的 CDC path
4. At-speed launch/capture pair

### QoR Metrics — Sign-off Targets
| Metric | Target |
|---|---|
| Setup WNS | ≥ `timing.wns_ns_target`，全部 corner |
| Setup TNS | = `timing.tns_ns_target`，全部 corner |
| Hold WNS | ≥ `timing.wns_ns_target`，全部 corner |
| Hold TNS | = `timing.tns_ns_target`，全部 corner |

### Output Required
- 每 corner setup/hold timing report
- 全 corner WNS/TNS summary
- Top 100 violating paths

---

## Stage: path_analysis

### Domain Rules
1. 按 root cause 分组：long wire、weak driver、logic depth、high-Vt。
2. Setup 与 hold violation 分开处理。
3. At-speed violation 显式检查 launch/capture pair。
4. PD 改动后重新验证全部 false path。
5. Reconvergent fanout path 要单独标记，避免 ECO 引入副作用。

### Output Required
- Failing path root-cause report
- 需要 ECO 的 path 与需要 SDC 修正的 path 分类

---

## Stage: exception_review

### Domain Rules
1. 审查每个 exception 的正确性和 scope：
   - `set_false_path`：确认路径确实非 functional
   - `set_multicycle_path`：确认 setup/hold 配套正确
   - `set_max_delay`：值与系统 timing budget 一致
2. 匹配超过全部 path 1% 的 exception 需要 architect approval。
3. 掩盖真实 violation 的 exception 立即撤销并重跑 path analysis。
4. 每个 exception 都必须记录 design intent / async crossing / test mode 等理由。
5. ECO 后新增 exception 也必须重新审查。

### Common Exception Errors
| 错误 | 后果 |
|---|---|
| Functional CDC 上 set_false_path | 掩盖 metastability 风险 |
| MCP 缺 hold correction | 静默引入 hold violation |
| Glob 过宽 | 非预期 path 被取消约束 |
| 已失效 exception | stale SDC 可能掩盖其他问题 |

### QoR Metrics to Evaluate
- 无缺 justification 的 exception
- 无未经批准的 overly broad exception
- ECO guidance 前 exception list 已 sign-off

### Output Required
- Exception audit report
- Revised SDC
- Exception sign-off record

---

## Stage: eco_guidance

### ECO Decision Tree
```
Setup violation:
  Logic depth 过大?        → Retime / add pipeline stage
  Long wire (>500 μm)?     → Buffer / upper-metal reroute
  Weak driver?             → Upsize cell
  High-Vt critical path?   → Swap SVT/LVT
  Reconvergent fanout?     → Clone cell / split net

Hold violation:
  Skew-induced post-CTS?   → Useful skew / targeted delay buffer
  Short path?              → HVT delay buffer
  New path from ECO?       → Sink-side targeted hold buffer
```

### ECO Rules
1. 以最少 cell change 修最多 violation。
2. 优先 resize，减少 routing impact。
3. ECO cell 使用 reserved ECO site/free row。
4. 每批 ECO 后重新跑 STA，不能累积 blind ECO。
5. 每批 ECO 后必须 LEC。
6. Fix setup 时不能引入新 hold，反之亦然。

### QoR Metrics to Evaluate
- ECO efficiency：每个 change 修复的 violation 数
- ECO cell count < 总 cell 的 2%，超过则视为上游问题
- Post-ECO LEC = EQUIVALENT

### Output Required
- ECO change list
- Pre/post timing comparison
- ECO LEC result

---

## Stage: sta_signoff

### Sign-off Checklist
- [ ] 所有 corner Setup WNS ≥ target
- [ ] 所有 corner Setup TNS = target
- [ ] 所有 corner Hold WNS ≥ target
- [ ] 所有 corner Hold TNS = target
- [ ] 所有 exception 合法且有文档
- [ ] POCV/AOCV 按 foundry spec 应用
- [ ] 所有 ECO 后 LEC clean

### Output Required
- All-corner/all-mode sign-off timing report
- ECO summary
- Timing sign-off record

---

## Constraint Validation
进入 `constraint_validation` 时 required：
- `constraints.clock.clk_mhz`
- 至少一个 `voltage_v/temp_c` 非 null 的 `constraints.pvt_corners`

Optional：
- `timing.wns_ns_target` 默认 0
- `timing.tns_ns_target` 默认 0
- `timing.skew_ps_max` 默认 100
- `timing.transition_ps_max` 默认 200
- `timing.insertion_delay_ps_max` 默认 500

---

## Memory

### Write on stage completion
每 stage 后按 `run_id` upsert `<MEM>/sta/experiences.jsonl`。
`run_id = sta_<YYYYMMDD>_<HHMMSS>`，流程开始时生成一次并复用；
最终 sign-off 前 `signoff_achieved:false`。

### Run state
工具前第一步写 `<MEM>/sta/run_state.md`：
```markdown
run_id:      sta_<YYYYMMDD>_<HHMMSS>
design_name: <design>
tool:        <primary tool>
start_time:  <ISO-8601>
last_stage:  <first stage name>
```
每 stage 后更新 `last_stage`。

### Optional: claude-mem index
若 observation 工具可用，将 applied fix 写入 `chip-design-sta-fixes`；否则跳过。
