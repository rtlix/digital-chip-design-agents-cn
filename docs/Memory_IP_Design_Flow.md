# Memory IP 设计流程

嵌入式 Memory IP 设计——SRAM、Register File 与 ROM。覆盖需求捕获、macro 选择、
array architecture、冗余与修复、view 生成/QA，以及集成交付。

**Plugin：** `chip-design-memory-ip`  
**Skill：** `plugins/memory-ip/skills/memory-ip-design/SKILL.md`  
**Orchestrator：** `plugins/memory-ip/agents/memory-ip-orchestrator.md`

---

## 架构总览

本 domain 把 memory 本身视为一个需要被设计和 qualification 的“产品”，而不是黑盒。
流水线其他部分只是消费 memory：PD 负责 placement，synthesis 对其 `dont_touch`，
DFT 负责测试，SoC 负责 view/integration qualification，FPGA 则用 BRAM 替换。
本流程负责真正产出这些 memory 及其下游所需 view。

### Scope boundary（职责边界）

| 本域不负责 | Owner |
|---|---|
| MBIST insertion、March pattern、MBIST fault coverage、ATPG | `chip-design-dft` |
| Floorplan、macro placement、macro 上方 power grid | `chip-design-pd` |
| Timing sign-off、multi-corner STA、ECO closure | `chip-design-sta` |
| Address/memory map assignment、bus fabric attachment | `chip-design-soc` |
| Cache hierarchy 与 DDR controller architecture | `chip-design-architecture` |

本流程会**生成这些 domain 要消费的输入**：
DFT 所需 memory inventory/repair-register map；
PD 所需 placement constraint；
STA 所需 `.lib` 和 derate；
verification 所需 behavioral model。

---

## 共享状态对象

写入 `design_state.json` 的 `memory_ip`：

```json
{
  "memory_ip": {
    "instances": [
      { "name": "", "type": "sram | rf | rom", "depth": 0, "width": 0,
        "ports": "1rw | 1r1w | 2rw", "macro": "", "banks": 0 }
    ],
    "total_area_um2": null,
    "views": { "lib": [], "lef": [], "db": [], "verilog": [], "gds": [], "cdl": [] },
    "repair": { "scheme": "row | column | both | none", "spare_rows": 0,
                "spare_cols": 0, "repair_reg_bits": 0, "efuse_map": null },
    "placement_constraints": [
      { "instance": "", "orientation": "", "halo_um": 0, "channel_um": 0, "group": "" }
    ],
    "ecc": { "scheme": "none | parity | secded", "data_bits": null, "check_bits": null },
    "power_modes": [],
    "signoff": false
  }
}
```

---

## Stage Sequence 与 Loop-Back

```text
memory_requirements → macro_selection → array_architecture → redundancy_repair →
view_generation → integration_prep → memory_signoff
```

| 失败 stage | 条件 | 回退到 | 最大次数 |
|---|---|---|---:|
| `macro_selection` | 无候选满足 access time | `memory_requirements` | 2× |
| `array_architecture` | area >120% budget | `macro_selection` | 3× |
| `array_architecture` | bandwidth < target | `memory_requirements` | 1× |
| `redundancy_repair` | projected yield < target | `array_architecture` | 2× |
| `view_generation` | view QA error >0 | `macro_selection` | 2× |
| `integration_prep` | placement/channel 不可行 | `array_architecture` | 2× |
| `memory_signoff` | Vmin margin 不足 | `array_architecture` | 1× |

### Sign-off criteria（机器可检查 gate）

- `view_qa_errors: 0`
- `all_corners_characterized: true`
- `redundancy_allocated: true`
- `mbist_ports_exposed: true`
- 每 instance slow corner `worst_access_time_margin_ns > 0`
- `projected_repair_yield_pct >= constraints.memory_ip.repair_yield_pct_min`
- `vmin_margin_mv >= constraints.memory_ip.vmin_margin_mv`
- `placement_constraints_complete: true`

完整人工 checklist（area/bandwidth budget、ECC read-path latency、
repair-register handoff、collision-policy 一致性、`set_dont_touch`）
位于 Skill 的 `memory_signoff` stage。

---

## Stage 摘要

完整 Domain Rule、QoR 和 output requirement 见 Skill；这里给出快速导航。

| Stage | 目的 | 关键输出 |
|---|---|---|
| `memory_requirements` | 清点所有 instance；分类 RF/SRAM/ROM；计算 bandwidth；根据 FIT 决定 ECC；枚举 power mode | Instance inventory、ECC decision table |
| `macro_selection` | Sweep column mux/bank count；按 **slow-corner** access-time margin、area、leakage 比较 | 每 instance selected macro + rejection rationale |
| `array_architecture` | Banking vs true multi-port；port arrangement/collision policy；wrapper/ECC/scrub/Vmin | Bank/port architecture、wrapper spec、ECC scheme |
| `redundancy_repair` | 根据 defect density 计算 spare；选择 repair；计算 repair register；efuse map | Repair architecture + projected yield |
| `view_generation` | 生成 `.lib/.lef/.db/.v/.gds/.cdl`；检查 pin/timing arc/corner/obstruction | Complete view set + QA report |
| `integration_prep` | 给 PD/DFT/STA/verification 输出 handoff | Handoff package |
| `memory_signoff` | 对上述所有结果做最终检查 | Signed-off Memory IP package |

---

## Constraints

**进入 `memory_requirements` 时必填：**

- `constraints.clock.clk_mhz` —— 决定 access-time budget

**Optional（使用默认值）：**

| Key | 默认 | 含义 |
|---|---:|---|
| `memory_ip.vmin_margin_mv` | 50 | Minimum Vmin margin |
| `memory_ip.repair_yield_pct_min` | 99 | Post-repair projected yield 下限 |
| `memory_ip.ecc_required` | false | true 时无论 FIT 计算如何，最低必须 SECDED |
| `memory_ip.fit_target_fit_per_mb` | 100 | Soft-error budget（FIT/Mb） |
| `memory_ip.max_aspect_ratio` | 4.0 | Macro aspect-ratio 上限 |
| `memory_ip.retention_required` | true | 仅作为未声明 per-instance retention 的默认值 |

`memory_requirements` 强制两条优先规则：

1. `design_state.rtl` 对 port/width/depth 的实现事实优先于
   `design_state.architecture`；二者冲突时不能静默选一个，
   而是升级为 `constraint_gap`。
2. ECC scheme 必须根据 `raw_FIT` 与 `budgeted_FIT`
   使用确定性决策表，而不是主观选择。

`constraints.pvt_corners` **不能用默认 typical corner 替代**。
缺失或 `voltage_v/temp_c` 为空时，`view_generation`
必须升级 `constraint_gap`，而不是只做 typical characterization。

`constraints.dft.mbist_coverage_pct` 在本域只读，owner 是 `chip-design-dft`。

---

## 支持的 EDA 工具

**开源：**

- OpenRAM：SRAM compiler
- CACTI：早期 area/power/access estimate
- sky130/gf180mcu SRAM macro set
- Magic：macro DRC/LVS
- KLayout：GDS QA
- OpenSTA：`.lib` sanity check

**商业：**

- ARM Artisan memory compiler
- Synopsys memory compiler + SiliconSmart
- Cadence Liberate
- Siemens Tessent MBIST/BISR（这里只作 repair/BISR 架构参考；真正插入属于 DFT）

---

## Memory

- Knowledge：`memory/memory-ip/knowledge.md`
- Experiences：`<MEM>/memory-ip/experiences.jsonl`
- `key_metrics`：
  `memory_instances`、`total_memory_area_um2`、
  `worst_access_time_ns`、`view_qa_errors`、
  `projected_repair_yield_pct`
