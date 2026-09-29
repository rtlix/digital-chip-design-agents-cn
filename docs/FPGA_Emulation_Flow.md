# FPGA 仿真与原型验证流程 — 完整架构设计
## Orchestrator + Stage Agents + Skills

> **目的**：AI 驱动的 ASIC→FPGA 原型移植流程。用于流片前硬件/软件协同开发、性能验证和早期固件 bring-up，在硅片可用前数月提前发现问题。

---

## 1. 共享状态对象

```json
{
  "run_id": "fpga_proto_001",
  "design_name": "my_soc",
  "inputs": {
    "rtl_filelist":      "filelist.f",
    "fpga_platform":     "Xilinx VCU118 | Intel Stratix 10 | Aldec HES",
    "fpga_part":         "xcvu9p-flga2104-2L-e",
    "target_freq":       "50MHz",
    "asic_target_freq":  "1GHz",
    "memory_map":        "path/to/memory_map.md",
    "debug_requirements":["JTAG", "ILA", "UART_console"]
  },
  "stages": {
    "rtl_adaptation":    { "status": "pending", "output": {} },
    "partitioning":      { "status": "pending", "output": {} },
    "fpga_synthesis":    { "status": "pending", "output": {} },
    "bring_up":          { "status": "pending", "output": {} },
    "sw_validation":     { "status": "pending", "output": {} },
    "proto_signoff":     { "status": "pending", "output": {} }
  },
  "fpga_utilization": {},
  "timing_met": false,
  "sw_tests_passing": 0,
  "flow_status": "not_started"
}
```

---

## 2. Stage Sequence（阶段顺序）

```
[RTL Adaptation] ──► [Partitioning] ──► [FPGA Synthesis]
                                              │ timing fail
                                              ▼ pass
                       [Bring-up] ──► [SW Validation]
                              ▲              │ HW/SW bug
                              └──────────────┘
                                             │ pass
                                      [Proto Sign-off]
```

---

## 3. Skill 文件说明

### 3.1 `sv-fpga-rtl-adapt/SKILL.md`

```markdown
# Skill: FPGA — RTL Adaptation

## Purpose
修改 ASIC RTL，使其兼容 FPGA，并把 ASIC 专用元素替换为 FPGA 等价资源。

## ASIC → FPGA Substitutions
| ASIC 元素 | FPGA 替代 |
|---|---|
| SRAM memory macro | BRAM 或 URAM |
| Analog PLL | FPGA MMCM/PLL primitive |
| IO pad cell | FPGA IOB + IOBUF |
| Analog/mixed-signal | Stub model 或移除 |
| DFT scan logic | Bypass 或移除 |
| Power-management cell | 移除，由 FPGA 内部处理 |
| Custom standard cell | Generic behavioral model |

## Memory Replacement Rules
1. Single-port SRAM → simple_dual_port 或 true_dual_port BRAM
2. 匹配 port width；BRAM 有固定容量/宽度限制
3. 验证 read latency；BRAM 常见为 1-cycle read
4. 必要时注册 output，换取 timing closure
5. 大型 memory 超出 BRAM budget 时使用 MIG/DDR controller 连接外部 DRAM

## Clock Adaptation
1. ASIC PLL 替换为 Xilinx MMCM 或 Intel ALTPLL
2. 全部 clock 缩放到 prototype frequency，通常 50–100 MHz
3. Multi-clock design 尽量保持 domain 间比例
4. Global clock 走 BUFG，regional clock 走 BUFR

## QoR Metrics
- Adapted RTL 中无 ASIC-specific primitive
- Memory 全部映射到 FPGA resource
- Adapted RTL lint clean
- Behavioral simulation 与 ASIC RTL 功能一致

## Output Required
- Adapted RTL file set
- Substitution log
- BRAM utilization estimate
```

---

### 3.2 `sv-fpga-partition/SKILL.md`

```markdown
# Skill: FPGA — Multi-FPGA Partitioning

## Purpose
当设计超出单片 FPGA 容量时，将其拆分到多片 FPGA，并保证跨 FPGA 通信正确。

## Partitioning Guidelines
1. 每片 FPGA LUT utilization 目标 <70%，为 debug 预留空间
2. 尽量减少 inter-FPGA signal 数量
3. 尽量切 logic boundary，不切 timing-critical path
4. 完整 clock domain 尽量保留在同一 FPGA
5. Inter-FPGA protocol 使用 Aurora、GTH SERDES 或 GPIO + sync

## Partitioning Strategies
| 策略 | 适用场景 |
|---|---|
| Hierarchical | 设计 block boundary 清晰 |
| Functional | CPU、memory/IO 等功能天然分区 |
| Pipeline-based | 深 pipeline 有自然 stage cut |

## Inter-FPGA Interface
1. Wide bus 通过高速 SERDES 序列化
2. 每个 transaction 需要 flow-control handshake
3. Inter-FPGA latency 必须在 simulation 中建模
4. Debug status 可路由到 FPGA LED/UART

## QoR Metrics
- 每片 FPGA：LUT <70%、BRAM <80%、DSP <80%
- Inter-FPGA signal 数量不超过 connector pin budget
- 不跨 partition 切分 clock domain，除非有 CDC bridge

## Output Required
- Partition plan
- Inter-FPGA signal list
- Physical connector pin assignment
```

---

### 3.3 `sv-fpga-synthesis/SKILL.md`

```markdown
# Skill: FPGA — FPGA Synthesis and Implementation

## Purpose
针对目标 FPGA 综合和实现 adapted RTL，并在 prototype frequency 下完成 timing closure。

## FPGA Implementation Flow (Xilinx Vivado)
1. Synthesis：`vivado -mode batch -source synth.tcl`
2. Implementation：opt_design → place_design → route_design → phys_opt_design
3. Timing：report_timing_summary
4. Bitstream：write_bitstream

## Timing Closure Techniques
1. Timing fail 时优先降低 prototype clock frequency
2. Critical path 增加 pipeline register，接受额外 latency
3. 用 Pblock 把相关 logic 靠近 BRAM/DSP
4. 高扇出长线使用 BUFG/专用 clock resource
5. 最后可尝试 `phys_opt_design -directive AggressiveExplore`

## Debug Infrastructure
1. ILA：连接关键 signal
   - 单个 ILA probe 数量有限，可使用多个 core
   - Trigger：protocol error、FSM state
2. VIO：PC 端驱动/采样 test signal
3. JTAG-to-AXI：无需重综合即可访问 register

## QoR Metrics
- Prototype frequency 下 WNS ≥0
- LUT <70%、BRAM <80%、DSP <80%
- Bitstream 生成时无 DRC error
- 关键 debug signal 已接 ILA

## Output Required
- Bitstream（.bit）
- Timing summary report
- Utilization report
- ILA probe definition
```

---

### 3.4 `sv-fpga-bringup/SKILL.md`

```markdown
# Skill: FPGA — Prototype Bring-up

## Purpose
把 FPGA prototype 带到可工作的状态，并在运行软件前验证硬件。

## Bring-up Sequence
1. Power-on：确认 rail、电流
2. 通过 JTAG/flash 加载 bitstream
3. 用示波器确认 prototype clock
4. 验证 reset sequence
5. 通过 JTAG-to-AXI 读写 peripheral register
6. BRAM / external DDR memory test
7. UART console：确认 CPU boot message
8. 加载并运行最小 firmware/RTOS

## Debug Methodology
1. 从 known-good test 开始，例如读取 chip-ID register
2. 失败时依次检查 clock、reset、power、bitstream
3. 用 ILA 捕获 bus transaction
4. 用 VIO 注入 stimulus，减少重新综合
5. 用 oscilloscope 检查 IO level/timing

## Common Bring-up Issues
- MMCM 不 lock：检查 PLL/MMCM 配置和输入频率
- CPU 不 boot：检查 reset vector、memory map、linker script
- Register 恒为 0：base address 错或 bus 未连接
- 返回 0xDEADBEEF：越界访问/DECERR

## QoR Metrics
- 所有 clock 实测频率正确
- CPU 启动到 firmware shell/UART prompt
- 全部 peripheral register 可通过 JTAG 读写
- DDR memory test PASS

## Output Required
- Bring-up test log
- Failure 的 ILA capture
- Known issue 与 workaround
```

---

### 3.5 `sv-fpga-sw-validation/SKILL.md`

```markdown
# Skill: FPGA — Software Validation on Prototype

## Purpose
在 FPGA prototype 上运行 firmware/software stack，同时验证硬件与软件功能。

## Software Validation Tiers
1. BSP validation：全部 driver 在 prototype 上工作
2. RTOS validation：RTOS boot，全部 task 运行
3. Application validation：目标应用输出正确
4. Performance profiling：实测执行时间

## Performance Scaling
- FPGA 50 MHz、ASIC 1 GHz 时约慢 20×
- Timing-sensitive software 的 timeout 按频率比例缩放
- 所有性能数值必须注明 prototype frequency

## Key Validation Tests
- UART/SPI/I2C peripheral loopback
- DMA throughput
- Interrupt latency
- DDR memory bandwidth
- Application output vs golden reference

## Hardware Bug vs Software Bug Triage
1. Register map 是否正确
2. RTL simulation 与 FPGA 行为是否一致
3. FPGA timing margin 是否充足
4. Bug 是否 deterministic reproduce
5. RTL simulation 是否也失败：是→RTL bug；否→prototype/adaptation 问题

## QoR Metrics
- Driver test 全 PASS
- Application 输出正确
- 无 hard lockup/unexpected reset
- 已建立 silicon 对比用 performance baseline

## Output Required
- Software validation report
- Performance baseline
- HW/SW 分类 bug list
```

---

## 4. Orchestrator System Prompt

```
You are the FPGA Prototyping Orchestrator.

You guide the porting and bring-up of an ASIC design on an FPGA
prototype platform, enabling pre-silicon hardware/software co-development.

STAGE SEQUENCE:
  rtl_adaptation → partitioning → fpga_synthesis →
  bring_up → sw_validation → proto_signoff

LOOP-BACK RULES:
  - fpga_synthesis: timing fail (>-0.5ns WNS) → rtl_adaptation (pipeline) (max 3x)
  - fpga_synthesis: utilization > 70%          → partitioning (max 2x)
  - bring_up: peripheral not responding        → rtl_adaptation (max 2x)
  - sw_validation: HW bug found                → rtl_adaptation (fix + re-synth)
  - sw_validation: SW bug found                → sw_validation (fw fix) (unlimited)

Output: Working FPGA prototype + SW validation report +
        bug list for RTL team + performance baseline for silicon comparison.
```

> Stage 名、状态值和固定机器接口保留英文，正文含义已中文化。
