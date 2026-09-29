---
name: fpga-emulation
description: >
  FPGA 原型验证（FPGA emulation）——ASIC 到 FPGA 的 RTL 适配、多 FPGA partition、FPGA 综合与时序收敛、
  硬件 bring-up，以及在原型机上的软件验证。适用于把 ASIC 设计移植到 Xilinx/Intel FPGA，
  用于流片前软件开发与硬件验证。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill: FPGA Emulation & Prototyping（FPGA 原型验证）

## Invocation
- **用户直接调用** FPGA prototyping 任务：立即启动
  `digital-chip-design-agents:fpga-orchestrator`，传入完整请求及上下文，不直接执行 stage。
- **由 fpga-orchestrator 中途调用**：不要再启动新 Agent；本文件作为只读规则库提供
  stage rule、sign-off criteria 和 loop-back guidance。

## Pre-run Context
任何 stage 前，如存在则先读取：
1. `memory/fpga/knowledge.md`
2. `memory/fpga/run_state.md`
将历史 failure pattern、有效 tool flag 和 run state 应用于当前决策。

## Purpose
把 ASIC 设计移植到 FPGA prototype，支持流片前 HW/SW 协同开发。
FPGA prototype 不一定 cycle-accurate，但可以在硅片回来数月之前进行功能和架构验证。

---

## Supported EDA Tools
### Open-Source
- **Yosys**（`yosys`）—— Xilinx/Intel/Lattice 综合
- **nextpnr**（`nextpnr-xilinx`、`nextpnr-ice40`、`nextpnr-ecp5`）—— P&R
- **OpenFPGALoader** —— 通用 FPGA programmer
- **Project IceStorm** —— iCE40 toolchain
- **Project X-Ray** —— Xilinx 7-series bitstream documentation

### Proprietary
- **Xilinx Vivado**（`vivado`）
- **Intel Quartus**（`quartus_sh`）
- **Microchip Libero**（`libero`）
- **Synopsys Synplify**

---

## Stage: rtl_adaptation

### ASIC → FPGA Substitutions
| ASIC Element | FPGA 替代 |
|---|---|
| SRAM macro | Xilinx BRAM/URAM 或 Intel M20K |
| Analog PLL | Xilinx MMCM 或 Intel ALTPLL |
| IO pad cell | FPGA IOB + IOBUF primitive |
| Analog/mixed-signal | Stub model 或移除 |
| DFT scan logic | 移除，prototype 不需要 |
| Power-management cell | 移除，由 FPGA 内部处理 |

### Memory Replacement Rules
1. Port configuration 必须一致（single/dual port）。
2. BRAM 通常有 1-cycle read latency，确认 RTL 能处理。
3. Memory 超过内部 BRAM 容量时，使用 MIG/HBM controller 连接 external DDR。
4. Xilinx 优先使用 `XPM_MEMORY` 或可移植等价 macro。

### Clock Replacement Rules
1. ASIC PLL 替换为 MMCM/ALTPLL。
2. 全部 clock 缩放到 prototype frequency，常见 50–100 MHz，而 ASIC 可能 ≥1 GHz。
3. 不同 clock domain 的频率比例尽量保持。
4. Global clock 必须走 BUFG/专用 clock network，不能走 data fabric。

### QoR Metrics to Evaluate
- 适配 RTL 中不再残留 ASIC-specific primitive
- Memory 全部映射 BRAM 或 external DDR
- Adapted RTL lint：0 error
- Functional sim 与原 ASIC RTL 输出一致

### Output Required
- Adapted RTL file set
- Substitution log
- BRAM/MMCM resource estimate

---

## Stage: partitioning

### Domain Rules
1. 每片 FPGA LUT utilization < `constraints.fpga.lut_util_pct_max`%，默认 70%，预留 ILA 空间。
2. 尽量减少 inter-FPGA signal，物理连接 pin 是硬限制。
3. Timing-critical path 不得跨 partition boundary。
4. 完整 clock domain 尽量放在同一 FPGA。
5. 高速 inter-FPGA 使用 Aurora/GTH SERDES；慢 control 可用 GPIO。

### QoR Metrics to Evaluate
- LUT < target（默认 70%）
- BRAM < `bram_util_pct_max`（默认 80%）
- DSP < `dsp_util_pct_max`（默认 80%）
- Inter-FPGA signal 不超过 connector pin budget
- Clock domain split 必须有显式 bridge

### Output Required
- Block → FPGA partition plan
- Inter-FPGA signal list
- Connector pin assignment

---

## Stage: fpga_synthesis

### Domain Rules
1. 完整 flow：synth → opt → place → route → phys_opt → bitstream。
2. Prototype frequency 下 WNS ≥ `constraints.timing.wns_ns_target`，默认 0。
3. WNS <0 时优先降低 frequency，其次再增加 pipeline register。
4. Utilization 必须满足 LUT/BRAM/DSP limit。

### Debug Infrastructure
Bitstream 前加入：
- ILA：观察关键 signal/FSM，error trigger
- VIO：PC 端驱动/采样 control/status
- JTAG-to-AXI：无需重综合即可做 register access

### Timing Closure Techniques
| 技术 | 适用场景 |
|---|---|
| 降低 clock frequency | 首选，接受较慢 prototype |
| 增加 pipeline register | 可定位路径且允许增加 latency |
| Pblock | 将 logic 靠近 BRAM/DSP |
| High-fanout net 使用 BUFG | 缩短高扇出长路由 |
| `phys_opt -directive AggressiveExplore` | 最后手段 |

### QoR Metrics to Evaluate
- WNS ≥ target
- LUT/BRAM/DSP < 对应 constraint
- Bitstream 无 critical DRC
- ILA 已连接关键 debug signal

### Output Required
- `.bit` / `.sof`
- Timing summary
- Utilization report
- ILA probe definition

---

## Stage: bring_up

### Bring-up Sequence
必须按顺序：
1. Power-on：测量 rail/current
2. JTAG/SPI flash 加载 bitstream
3. 示波器/ILA 验证 clock frequency 和稳定性
4. Toggle reset，确认 status 正确释放
5. JTAG-to-AXI 读取 chip-ID register
6. BRAM/external DDR write-readback
7. UART console 出现 CPU boot message
8. Minimal bare-metal firmware 执行并打印 PASS

### Common Failures
| 现象 | 可能原因 | 修复 |
|---|---|---|
| MMCM 不 lock | 输入频率超范围 | 检查 MMCM config |
| CPU 无 UART 输出 | reset vector/memory map 错 | 检查 linker script |
| Register 总读 0 | SW base address 错 | 对比 memory_map.h 与 HW |
| 读出 0xDEADBEEF | 越界访问/DECERR | 修正 address |
| 偶发数据损坏 | Adapted RTL CDC 问题 | 检查 crossing |

### QoR Metrics to Evaluate
- 所有 clock 实测正确
- CPU 到达 UART prompt
- Peripheral register 可通过 JTAG R/W
- DDR memory test PASS（如存在）

### Output Required
- Bring-up log
- Failure ILA capture
- SW team known-issues list

---

## Stage: sw_validation

### Domain Rules
1. 在 FPGA prototype 上运行 embedded-firmware Skill 的 validation suite。
2. 所有 timeout 按 FPGA:ASIC frequency ratio 缩放。
3. Performance measurement 必须注明 prototype frequency 与 scale factor。

### HW Bug vs SW Bug Triage
1. 可 deterministic reproduce → 更可能 HW bug
2. RTL simulation 同样失败 → RTL bug
3. 与 RTL sim 不同 → FPGA adaptation 问题
4. Intermittent → 优先检查 CDC/timing margin

### Validation Tiers
| Test | Pass Criteria |
|---|---|
| BSP | 全 peripheral accessible |
| Driver unit | 100% per driver |
| System | 与 golden output 一致 |
| Long-run（4 h） | 0 lockup / unexpected reset |

### QoR Metrics to Evaluate
- Driver test 全 PASS
- Application 与 golden 一致
- Stress run 无 lockup/reset
- 已记录 prototype-frequency performance baseline

### Output Required
- SW validation report
- 标明 prototype frequency 的 performance baseline
- HW/SW 分类 bug list
- 投影到 silicon frequency 的 performance estimate

---

## Stage: proto_signoff

### Sign-off Checklist
- [ ] Clock frequency 全部实测正确
- [ ] CPU boot 并运行 application
- [ ] 所有 peripheral register accessible
- [ ] Driver test 全部通过
- [ ] Application 输出正确
- [ ] 4-hour stress clean
- [ ] HW bug 均带 ILA evidence 提交 RTL team
- [ ] Performance baseline 已记录

### Output Required
- Prototype sign-off report
- RTL team HW bug report
- Performance baseline
- SW team prototype user guide

---

## Constraint Validation
进入 `rtl_adaptation` 时必须有 `constraints.clock.clk_mhz`，用于计算 ASIC→FPGA
frequency scale-down ratio。Optional constraint：
`timing.wns_ns_target` 默认 0，
`fpga.lut_util_pct_max` 默认 70，
`bram_util_pct_max` / `dsp_util_pct_max` 默认 80。

---

## Memory

### Write on stage completion
每 stage 完成后按 `run_id` upsert `memory/fpga/experiences.jsonl`，key_metrics 使用
`lut_count/fmax_mhz/timing_met`。
`run_id = fpga_<YYYYMMDD>_<HHMMSS>_<6-char-random>`，后缀必须是一次生成并全程复用的
6 位小写十六进制。最终 sign-off 前 `signoff_achieved:false`。

### Run state
工具前第一步写：
```markdown
run_id:        fpga_<YYYYMMDD>_<HHMMSS>_<6-char-random>
design_name:   <design>
tool:          <primary tool>
start_time:    <ISO-8601>
last_stage:    null
current_stage: <first stage name>
```
stage 开始时更新 `current_stage`，成功后写 `last_stage` 并清空 current_stage。

### Optional: claude-mem index
如 `mcp__plugin_ecc_memory__add_observations` 可用，将 applied fix 写入
`chip-design-fpga-fixes`；否则跳过，JSONL 为 canonical record。
