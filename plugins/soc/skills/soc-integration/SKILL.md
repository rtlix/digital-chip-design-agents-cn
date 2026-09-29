---
name: soc-integration
description: >
  SoC IP 集成——IP 获取与 qualification、IP 配置、bus fabric、top-level RTL 集成和
  chip-level simulation。适用于由多个 IP 组装 SoC、配置 AXI interconnect、
  集成 memory macro 或运行芯片级集成测试。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill: SoC IP Integration（SoC IP 集成）

## Invocation
用户提出 SoC integration 任务时，**不要直接执行 stage**。立即启动
`digital-chip-design-agents:soc-integration-orchestrator` 并传入完整请求与上下文。
只有 Orchestrator 中途读取本 Skill，或用户只问局部参考问题时才直接使用这里的规则。

## Pre-run Context
任何 stage 前如存在则读取：
1. `memory/soc/knowledge.md`
2. `memory/soc/run_state.md`
把历史 failure pattern、有效 tool flag、PDK/tool quirk 用于 stage 决策。

## Purpose
将自研 RTL、licensed hard/soft IP 和 memory macro 组装为完整 SoC，
覆盖 IP procurement、bus fabric 配置、top integration 和 chip-level simulation sign-off。

---

## Supported EDA Tools
### Open-Source
- Verilator (`verilator`) — integrated top-level 快速仿真
- cocotb — Python bus/peripheral co-simulation
- FuseSoC (`fusesoc`) — IP package/build system
- Edalize — FuseSoC 的 EDA abstraction layer

### Proprietary
- Synopsys VCS (`vcs`)
- Cadence Xcelium (`xrun`)
- Siemens Questa (`vsim`)

---

## Stage: ip_procurement

### IP Qualification Checklist
- [ ] Deliverable 是 RTL、GDSII 还是 encrypted netlist
- [ ] 已针对目标 process node 认证
- [ ] SS/TT/FF timing library 可用
- [ ] LEF/DEF 可供 PD 使用
- [ ] Behavioral/RTL simulation model 可用
- [ ] UPF/power intent 已交付
- [ ] Databook 包含 register map、timing diagram、integration guide
- [ ] DFT/scan/BIST 信息明确
- [ ] Silicon-proven 状态与工艺节点明确
- [ ] Support SLA / bug-fix commitment 明确

### Hard IP vs Soft IP
| 方面 | Hard IP (GDSII) | Soft IP (RTL) |
|---|---|---|
| Area | 固定 | 取决于综合 |
| Timing | 只能使用 characterized lib | 可优化 |
| PD effort | 作为 macro 放置 | 完整 PD |
| Customization | 基本无 | 可参数化 |

### Memory Macro Qualification
1. 检查 compiler 生成的 `.lib/.lef/.v`。
2. Access time 必须满足目标 clock。
3. 验证 read/write port、byte-enable、sleep/retention pin。
4. Simulation model 与 synthesized blackbox port 必须一致。
5. MBIST/BISR interface 交给 DFT 使用。

### QoR Metrics to Evaluate
- Unqualified IP = 0
- 每个 IP 的 view/guide/license/support 信息齐全
- 所有 timing/interface requirement 与 `constraints.clock.clk_mhz` 兼容

### Output Required
- IP inventory
- Qualification matrix
- Missing deliverable / risk list

---

## Stage: ip_configuration

### Domain Rules
1. 每个 configurable IP 的 parameter 要冻结并记录。
2. Width、ID、burst、clock/reset mode 必须与系统 spec 一致。
3. Register address 与 interrupt number 不得冲突。
4. Clock/reset domain 必须明确，并记录同步/异步关系。
5. Hard IP wrapper 的 polarity/width/unused pin 必须显式处理。
6. 生成 config snapshot，后续 synthesis/verification 可复现。
7. 任何 IP option 改变都必须重新进行 interface/timing qualification。

### QoR Metrics to Evaluate
- 参数未决项 = 0
- Address/IRQ conflict = 0
- Clock/reset definition complete

### Output Required
- Per-IP configuration record
- Register/interrupt allocation table
- Clock/reset domain table

---

## Stage: bus_fabric_setup

### Domain Rules
1. 根据 bandwidth/latency/masters/slaves 选择 bus/crossbar/NoC。
2. AXI address map 必须无 overlap；每个 slave region 对齐并覆盖合法范围。
3. ID width 必须支持所需 outstanding transaction，不能在桥接处静默截断。
4. Data-width converter、clock converter、protocol converter 要明确 latency/ordering impact。
5. Back-pressure、burst、narrow transfer、outstanding、out-of-order response 都必须验证。
6. Decode error 应返回合法 DECERR/SLVERR，不允许永久 hang。
7. CDC crossing 使用 approved bridge/async FIFO。

### QoR Metrics to Evaluate
- Address-map conflict = 0
- Protocol violation = 0
- Bandwidth ≥ system target
- 所有 master→slave 路径可达

### Output Required
- Bus topology diagram
- Memory/address map
- Connectivity matrix
- Bridge/converter list

---

## Stage: top_integration

### Domain Rules
1. Top-level 只做结构连接，不放功能逻辑。
2. 每个 IP port 必须显式连接或显式 tie-off。
3. Clock/reset/power/test signal 命名和 polarity 一致。
4. 对全部 interface 做 width/type/connectivity static check。
5. Interrupt 汇总、DMA request、debug/JTAG 路径必须完整。
6. Memory macro 使用 Memory-IP qualification view，不重新定义。
7. 对 unused output/optional feature 做明确 waiver，不能靠 warning 淹没。

### QoR Metrics to Evaluate
- Unconnected required port = 0
- Width mismatch = 0
- Multiple driver = 0
- Connectivity error = 0

### Output Required
- Integrated top RTL
- File list / compile order
- Connectivity report
- Top-level interface document

---

## Stage: chip_level_sim

### Domain Rules
1. 先跑 boot/smoke，再跑 peripheral、bus stress 和 error injection。
2. 每个 IP 至少一个基本功能 test。
3. AXI/APB 等 bus protocol checker 全程启用。
4. 测试 multi-master contention、back-pressure、maximum outstanding。
5. Reset during traffic、clock-domain reset sequence 必须测试。
6. 所有 memory region 做 read/write/alias test。
7. 对 CPU-based SoC，执行 minimal firmware boot 与 interrupt test。
8. Scoreboard/assertion mismatch 必须分类，不能只靠最终软件输出判断。

### QoR Metrics to Evaluate
- Chip-level test pass rate = 100%
- AXI/protocol violation = 0
- Memory-map conflict/alias = 0
- Unhandled interrupt/error = 0

### Output Required
- Chip-level regression report
- Protocol-checker report
- Memory-map test report
- Failure waveform/log

---

## Stage: integration_signoff

### Sign-off Checklist
- [ ] 所有 IP qualified
- [ ] 所有 IP configuration frozen
- [ ] Address/interrupt map 无冲突
- [ ] Clock/reset domain 已文档化
- [ ] Top-level connectivity clean
- [ ] Chip-level regression 100% PASS
- [ ] Protocol violation = 0
- [ ] Memory access test PASS
- [ ] P0/P1 integration bug 全关闭

### Output Required
- Integrated SoC RTL package
- Final memory map
- IP/configuration manifest
- Chip-level sign-off report

---

## Constraint Validation
进入 `ip_procurement` 必须有 `constraints.clock.clk_mhz`。
其他 optional constraint 缺失时采用 Pipeline schema default，并在 history reason 中说明 fallback。
评估 frequency/timing QoR 时使用 `constraint_ref:"clock.clk_mhz"`。

---

## Memory

### Write on stage completion
每 stage 完成后按 `run_id` upsert `memory/soc/experiences.jsonl`。
`run_id = soc_<YYYYMMDD>_<HHMMSS>`，流程开始时生成一次并复用。
最终 signoff 前保持 `signoff_achieved:false`。

### Run state
任何工具前第一步写 `memory/soc/run_state.md`，记录 run_id/design_name/tool/start_time/last_stage。

### Optional: claude-mem index
如果 observation 工具可用，把 applied fix 写入 `chip-design-soc-fixes`；否则跳过。
