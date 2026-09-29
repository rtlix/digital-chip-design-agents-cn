# SoC IP 集成流程 — 完整架构设计
## Orchestrator + Stage Agents + Skills

> **目的**：AI 驱动的完整 SoC 组装流程，把自研 RTL、licensed hard/soft IP 和 memory macro 集成为芯片。覆盖 IP procurement、integration、bus fabric configuration 和 chip-level verification。

---

## 1. 共享状态对象

```json
{
  "run_id": "soc_integration_001",
  "soc_name": "my_soc",
  "inputs": {
    "arch_doc":        "path/to/microarch.md",
    "ip_list": [
      { "name": "ARM_Cortex_M33", "type": "hard_ip", "vendor": "ARM" },
      { "name": "USB3_PHY",       "type": "hard_ip", "vendor": "Synopsys" },
      { "name": "AXI_Interconnect","type": "soft_ip","vendor": "internal" },
      { "name": "SRAM_256K",      "type": "memory_macro", "vendor": "foundry" }
    ],
    "bus_fabric":      "AXI4 + APB3",
    "technology":      "tsmc7nm"
  },
  "stages": {
    "ip_procurement":     { "status": "pending", "output": {} },
    "ip_configuration":   { "status": "pending", "output": {} },
    "bus_fabric_setup":   { "status": "pending", "output": {} },
    "top_integration":    { "status": "pending", "output": {} },
    "chip_level_sim":     { "status": "pending", "output": {} },
    "integration_signoff":{ "status": "pending", "output": {} }
  },
  "ip_status": {},
  "connectivity_errors": [],
  "flow_status": "not_started"
}
```

---

## 2. Stage Sequence

```
[IP Procurement] ──► [IP Configuration] ──► [Bus Fabric Setup]
                                                    │
                              ▼
                       [Top Integration] ──► [Chip-Level Sim]
                              ▲                     │ connectivity errors
                              └─────────────────────┘
                                                    │ pass
                              [Integration Sign-off]
```

---

## 3. Skill 文件说明

### 3.1 `sv-soc-ip-procurement/SKILL.md`

```markdown
# Skill: SoC — IP Procurement and Quality Check

## Purpose
在集成前评估、获取并 qualification 全部第三方 IP。

## IP Qualification Checklist
- [ ] Deliverable：RTL、GDSII 或 encrypted netlist
- [ ] 已针对目标 process node 认证
- [ ] SS/TT/FF timing lib 可用
- [ ] LEF/DEF 可用于 PD
- [ ] Verification model 可用
- [ ] UPF/power intent 已交付
- [ ] Databook 包含 register map/timing/integration guide
- [ ] DFT/scan/BIST 信息明确
- [ ] Silicon-proven 状态明确
- [ ] Support SLA 明确

## Hard IP vs Soft IP
| 方面 | Hard IP | Soft IP |
|---|---|---|
| Area | 固定 | 由综合决定 |
| Timing | Characterized lib | 可优化 |
| PD | Macro placement | 完整 PD |
| Customization | 很少 | 可参数化 |
| Verification | Behavioral model 为主 | Full RTL sim |

## Memory Macro Qualification
1. 检查 .lib/.lef/.v
2. Access time 满足 target clock
3. Retention/power-down mode 正确
4. BIST port 可供 DFT 使用

## Output Required
- Per-IP qualification report
- Deliverable checklist
- IP risk register
```

---

### 3.2 `sv-soc-bus-fabric/SKILL.md`

```markdown
# Skill: SoC — Bus Fabric Configuration

## Purpose
配置并验证连接全部 SoC IP 的片上 bus/interconnect。

## Bus Fabric Selection
| Fabric | 用途 | Bandwidth |
|---|---|---|
| AXI4 Crossbar | 高带宽 data path | High |
| AXI4-Lite | Control register | Low |
| APB3 | Peripheral register | Low |
| AHB | Legacy peripheral | Medium |
| NoC | Many-core complex topology | Very High |

## Configuration Requirements
1. Master/slave port assignment 正确
2. Address region 无 overlap
3. 需要时加入 data-width adapter
4. Multi-clock 使用 async bridge
5. Latency-sensitive master 配置 QoS
6. 设置 per-master outstanding depth
7. Out-of-range address 返回 DECERR

## Memory Map Validation
- 无 overlap
- 所需 master 都能访问对应 peripheral
- Reserved region 无 decode 时返回 DECERR
- 无意外 alias

## QoR Metrics
- Address decode 完整
- IP 接到正确 bus/width
- CDC bridge 完整
- Simulation 中全部 register 可正确 R/W

## Output Required
- Bus fabric configuration
- Final versioned memory map
- Address-decoder verification report
```

---

### 3.3 `sv-soc-top-integration/SKILL.md`

```markdown
# Skill: SoC — Top-Level Integration

## Purpose
把 IP、bus fabric、memory 和 IO 组装到 chip top-level。

## Top-Level Integration Rules
1. Top module 只做 wiring，不放功能逻辑
2. IP 不重复实例化，除非设计明确要求
3. Active signal 不得悬空
4. PLL/clock mux 放 top 或 near-top
5. 每个 clock domain 有对应 reset synchronizer
6. IO ring/pad 全部连接
7. Floating input 使用 tie cell

## Integration Checklist
- [ ] Module name/parameter 正确
- [ ] Required port 全连接
- [ ] Clock 接到正确 domain
- [ ] Reset domain/polarity 正确
- [ ] Power/ground 正确
- [ ] Scan chain SI/SO 正确
- [ ] JTAG TDI/TDO 正确串接

## Common Integration Bugs
- 错 clock domain → metastability
- Reset polarity 反 → block 永不出 reset
- valid/enable 未连接
- AXI address offset 错误

## QoR Metrics
- Lint unconnected active port =0
- Top-level CDC 无新增 violation
- IP 在正确 address 响应
- Smoke test 全部 IP 可访问

## Output Required
- soc_top.sv
- Integration lint report
- IP connectivity summary
```

---

### 3.4 `sv-soc-chip-sim/SKILL.md`

```markdown
# Skill: SoC — Chip-Level Simulation and Verification

## Purpose
通过 chip-level simulation 验证整颗 SoC 中各 IP 能正确协同。

## Chip-Level Simulation Strategy
1. CPU boot/reset-vector test
2. 全 peripheral register R/W
3. DMA between memory region
4. 每 peripheral interrupt
5. Multi-master concurrent bus access
6. Clock switching
7. Sleep/deep-sleep enter/exit
8. Warm/cold/per-domain reset

## Simulation Infrastructure
1. Chip-level testbench 模拟 board environment
2. External DRAM/Flash model
3. USB/Ethernet/SERDES PHY model 或 transactor
4. 全 bus protocol checker
5. Firmware 通过 UART model 报 PASS/FAIL

## Regression Structure
| Test | Scope | Run time |
|---|---|---:|
| Smoke | Boot + register access | <1h |
| Full regression | 全 peripheral | <24h |
| Long-run | Throughput/IRQ stress | 48h |

## QoR Metrics
- Peripheral register test 全 PASS
- CPU 到 application code
- DMA 数据与地址正确
- AXI protocol violation =0
- Reset 后关键 output 无 X

## Output Required
- Chip-level simulation report
- Per-test pass/fail log
- Protocol-checker clean report
```

---

## 4. Orchestrator System Prompt

```
You are the SoC Integration Orchestrator.

You manage the assembly and verification of a complete SoC from
individual IP blocks through chip-level simulation sign-off.

STAGE SEQUENCE:
  ip_procurement → ip_configuration → bus_fabric_setup →
  top_integration → chip_level_sim → integration_signoff

LOOP-BACK RULES:
  - ip_configuration: timing/interface error    → ip_procurement (max 2x)
  - top_integration: connectivity errors        → top_integration (max 3x)
  - chip_level_sim: peripheral test fail        → top_integration (max 3x)
  - chip_level_sim: bus protocol violation      → bus_fabric_setup (max 2x)

Track ip_status{} and connectivity_errors[] in state.
Block progression if any IP has unresolved qualification issues.
Output: Integration-complete SoC RTL package ready for synthesis.
```

> 固定 stage 名和机器接口保留英文。
