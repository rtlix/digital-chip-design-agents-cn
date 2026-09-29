---
name: memory-ip-design
description: >
  嵌入式 Memory IP（SRAM / Register File / ROM）设计——从需求捕获、macro 选择、
  array/bank/ECC 架构、冗余修复、view 生成到集成交付。
  适用于选择或生成 memory macro、设计 banking/ECC wrapper、规划 spare row/column，
  或生成可交付 DFT/PD/STA 的完整 memory view package。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill: Memory IP Design（Memory IP 设计）

## Invocation
用户提出 Memory IP 任务时，立即启动
`digital-chip-design-agents:memory-ip-orchestrator` 并传入完整请求和上下文；
不要直接执行 stage。被 Orchestrator 中途调用时，本文件只作为只读规则库使用。

## Pre-run Context
任何 stage 前，如存在则读取：
1. `memory/memory-ip/knowledge.md`
2. `memory/memory-ip/run_state.md`
利用历史 failure pattern、tool flag、PDK/compiler quirks 与当前 run state。

## Purpose
把 memory 当作独立产品进行设计和 qualification：从 architecture/RTL 中提取需求，
选择或生成 macro，确定 banking/port/ECC、repair/yield 策略，生成各 PVT view，
并给 DFT、PD、STA、verification、SoC 提供完整 handoff。

### Scope boundary
本域**不**负责：
| 不属于本域 | Owner |
|---|---|
| MBIST controller、March pattern、MBIST coverage、ATPG | `chip-design-dft` |
| Floorplan、实际 macro placement、power grid | `chip-design-pd` |
| Timing sign-off / multi-corner STA / ECO closure | `chip-design-sta` |
| Address map / bus fabric attachment | `chip-design-soc` |
| Cache hierarchy / DDR controller architecture | `chip-design-architecture` |

本域生产下游需要的 memory inventory、repair-register map、placement constraint、
Liberty view、behavioral model 等。

---

## Supported EDA Tools
### Open-Source
- **OpenRAM** (`openram`) — SRAM compiler，生成 GDS/LEF/Liberty/Verilog
- **CACTI** (`cacti`) — early access-time/area/power estimate
- **sky130 / gf180mcu SRAM macro** — PDK hardened macro
- **Magic** (`magic`) — macro DRC/LVS
- **KLayout** (`klayout`) — GDS/view QA
- **OpenSTA** (`sta`) — `.lib` load/timing arc sanity check

### Proprietary
- ARM Artisan memory compiler
- Synopsys memory compiler + SiliconSmart
- Cadence Liberate
- Siemens Tessent MBIST/BISR（只作为 repair/BISR 架构参考，插入属于 DFT）

---

## Stage: memory_requirements

### Domain Rules
1. 对每个 memory instance 收集 depth × width × port count，优先级：
   1. `design_state.rtl`：实现事实，port/width/depth 权威
   2. `design_state.architecture`：RTL 未给出时的 intent/sizing
   3. inference：两者都缺失时才允许，且记录为待确认 assumption
2. RTL 与 architecture 对同一 instance 的 type/port/depth/width 冲突时，**不得静默选一个**；
   立即以 `constraint_gap` 升级并同时列出两个值。
3. 按 `constraints.clock.clk_mhz` 计算 read/write bandwidth，bandwidth shortage 在本 stage 解决。
4. ECC 使用确定性策略：
   - `ecc_required:true` → 至少 SECDED；只有 spec 明确允许 detect-only 才可 parity
   - `raw_FIT ≤ budgeted_FIT` → none
   - 超 budget 且系统可 detect-and-retry → parity
   - 超 budget 且无系统 retry → SECDED
   - SECDED + scrubbing 仍超 budget → escalate
   其中 `budgeted_FIT = fit_target_fit_per_mb × instance_Mb`。
   记录 raw_FIT、budgeted_FIT、PDK SER source 与最终 scheme。
5. 每 instance 解析 active/light sleep/deep sleep/shutdown。
   Per-instance retention 要求优先于全局 `retention_required`；全局仅是未明确 instance 的默认值。
6. 记录 array/periphery 是否需要 dual rail。
7. Multi-port 需求优先评估 banking，避免直接使用面积更大的 true multi-port bitcell。

### QoR Metrics to Evaluate
- 总 memory bit / instance count
- Aggregate bandwidth 与 target frequency 可提供 bandwidth
- Memory 预估占 die area budget 的比例

### Output Required
- Memory inventory
- Bandwidth/ECC decision table
- Per-instance power mode/retention requirement

---

## Stage: macro_selection

### Domain Rules
1. 先确认目标 PDK/compiler family 真正支持哪些 configuration。
2. Sweep column mux（4/8/16），平衡 aspect ratio 与 access time。
3. Sweep bank count，权衡 bitline length、access time 与 duplicated periphery area。
4. 候选比较使用 **slow corner** access-time margin，不只看 typical。
5. 在 `max_aspect_ratio` 限制内，优先更少、更大的 macro 以摊薄 periphery overhead。
6. 根据 Vmin 选择 bitcell：6T 密度高，8T read stability/Vmin 更好。
7. 每个淘汰 candidate 记录失败理由，供 re-spin/knowledge 复用。

### QoR Metrics to Evaluate
- 每 instance slow-corner access-time margin > 0
- Area、leakage、active power
- Aspect ratio ≤ `constraints.memory_ip.max_aspect_ratio`

### Output Required
- Per-instance selected macro/compiler config
- Candidate comparison + rejection rationale
- Slow-corner timing margin report

---

## Stage: array_architecture

### Domain Rules
1. 为 bandwidth 优先 banking，而不是 true multi-port bitcell。
2. 固化 port arrangement（1RW / 1R1W / 2RW）及 write-during-read policy：
   read-old / read-new / X；behavioral model 必须一致。
3. Wrapper 只承担 byte enable、output pipeline/register、clock gating 等必要职责。
4. ECC wrapper 必须计入 pipeline boundary 和 latency。SECDED check bits 取满足
   `2^c ≥ data_bits + c + 1` 的最小 c。
5. ECC 使用时定义 scrub interval，保证同一 word 累积第二个 bit flip 的概率满足 FIT target。
6. 定义 Vmin 与 read/write assist requirement。
7. 最终 architecture 重新核对 memory_requirements 阶段 bandwidth。

### QoR Metrics to Evaluate
- Bandwidth achieved vs target
- Total memory area vs budget，>120% FAIL
- ECC decode latency
- Vmin margin ≥ `constraints.memory_ip.vmin_margin_mv`

### Output Required
- Bank/port architecture diagram
- Wrapper specification
- ECC data/check width、latency、scrub policy

---

## Stage: redundancy_repair

### Domain Rules
1. Spare row/column 必须从 defect density × array size 推导，不能固定拍数。
2. Row/column/both repair scheme 根据 projected-yield target 和 defect 类型选择。
3. Repair-register width ≈ spare-row × log2(rows) + spare-col × log2(cols) + enable bits，
   这是 DFT BISR chain 的硬 handoff 数据。
4. 明确 soft repair 与 hard repair（efuse/OTP）的 boot/programming 约束。
5. 建立 efuse/OTP map，并预留 post-silicon re-repair capacity。
6. ECC 与 redundancy 不能互相替代：前者处理 field soft error，后者处理制造 hard defect。
7. Recompute projected yield；低于 `repair_yield_pct_min` 时 loop back。

### QoR Metrics to Evaluate
- Projected post-repair yield
- Spare row/column 与 area overhead
- Repair-register width
- Efuse/OTP bits consumed

### Output Required
- Per-instance repair scheme
- Repair-register map/width
- Efuse/OTP allocation
- Yield calculation/defect-density assumptions

---

## Stage: view_generation

### Domain Rules
1. 每 instance 生成完整 view：全部 required PVT 的 `.lib`、`.lef`、`.db`、`.v`、`.gds`、`.cdl`。
2. QA `.lib/.lef/.v` pin-name consistency。
3. 所有 port 的 setup/hold、clock-to-Q timing arc 必须完整。
4. Corner 数量必须与 required PVT list 一致；只有 typical 不可 sign-off。
5. LEF obstruction layer 必须完整。
6. Behavioral model timing check 与 collision policy 必须和 timing model/array_architecture 一致。
7. 对实际生成 layout 的 flow 运行 macro DRC/LVS；vendor pre-hardened macro 可跳过。

### QoR Metrics to Evaluate
- View QA error = 0
- Characterized corner 数 = required corner 数
- Macro DRC/LVS clean
- Pin consistency mismatch = 0

### Output Required
- Complete view set + path
- View QA report
- DRC/LVS report（适用时）

---

## Stage: integration_prep

### Domain Rules
1. 给 PD 输出 placement constraint，不负责实际 placement：orientation、halo、channel width、bank grouping。
2. 给 DFT 输出 memory inventory + repair map，按 width/depth class 分组。
3. 每 instance 必须暴露可达 BIST port；连接由 DFT 负责。
4. 给 STA 输出 `.lib` set 与 memory-specific derate note。
5. 给 verification 输出 behavioral model path + collision policy。
6. 对 memory macro 确认 `set_dont_touch` 并从 scan insertion 中排除。
7. 对照 SoC memory map 与实际 macro depth；冲突必须在这里发现。

### QoR Metrics to Evaluate
- Placement constraint complete ratio
- BIST port exposure complete ratio
- Memory-map conflict = 0

### Output Required
- PD placement constraint
- DFT memory/repair handoff
- STA Liberty/derate handoff
- Verification model/collision handoff

---

## Stage: memory_signoff

### Sign-off Checklist
- [ ] 所有 instance 有 selected macro 且 slow-corner timing margin >0
- [ ] Total memory area 在 budget 内
- [ ] `constraints.clock.clk_mhz` 下 bandwidth 达标
- [ ] 必需 ECC 已实现，latency 已计入 read path
- [ ] Vmin margin 达标
- [ ] Repair yield ≥ target
- [ ] Repair-register map 已交付 DFT
- [ ] 每 instance 全 corner view 完整且 QA error=0
- [ ] Behavioral model collision policy 一致
- [ ] PD placement constraint 已输出
- [ ] 每 instance BIST port 已暴露
- [ ] Synthesis `set_dont_touch` 已确认

### Output Required
- Signed-off Memory IP package
- 带 evidence 的 sign-off report
- `design_state.json.memory_ip.signoff=true`

---

## Constraint Validation
进入 `memory_requirements` 必须有 `constraints.clock.clk_mhz`。
Optional：
- `memory_ip.vmin_margin_mv` 默认 50
- `repair_yield_pct_min` 默认 99
- `ecc_required` 默认 false；true 强制至少 SECDED
- `fit_target_fit_per_mb` 默认 100
- `max_aspect_ratio` 默认 4.0
- `retention_required` 默认 true，但仅作用于无 per-instance requirement 的 instance
- `pvt_corners` 不可用 typical 代替；无有效 V/T corner 时在 view_generation 以 `constraint_gap` 升级
- `dft.mbist_coverage_pct` 只读，由 DFT 拥有

---

## Memory

### Write on stage completion
每 stage 后按 `run_id` upsert `memory/memory-ip/experiences.jsonl`。
`run_id = memory-ip_<YYYYMMDD>_<HHMMSS>`，流程开始时生成一次并复用。
最终 sign-off 前 `signoff_achieved:false`。

### Run state
工具前第一步写 `memory/memory-ip/run_state.md`；成功完成 stage 后才更新 `last_stage`。

### Optional: claude-mem index
如 `mcp__plugin_ecc_memory__add_observations` 可用，把 applied fix 写入
`chip-design-memory-ip-fixes`；否则跳过，JSONL 为 canonical record。
