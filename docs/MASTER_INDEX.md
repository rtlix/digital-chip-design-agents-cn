# 数字设计与软件流水线 — 总索引
## 芯片设计完整 Agent + Skill 架构

> **目的**：这是完整数字芯片设计流水线的总索引。它把每份流程文档映射到端到端设计流程中的位置，并定义 Orchestrator 之间如何交接，从规格一路走到 tape-out、compiler、firmware 和 FPGA 原型验证（FPGA emulation）。

---

## 全流程总览

```
                     ┌─────────────────────────────────────────────────────┐
                     │          0. INFRASTRUCTURE SETUP                    │
                     │  Tool detection、wrapper、MCP config                │
                     └────────────────────┬────────────────────────────────┘
                                          │
                     ┌────────────────────▼────────────────────────────────┐
                     │             PRODUCT SPECIFICATION                   │
                     └────────────────────┬────────────────────────────────┘
                                          │
                     ┌────────────────────▼────────────────────────────────┐
                     │  1. ARCHITECTURE EVALUATION                         │
                     │     Microarch doc、PPA estimate、risk register       │
                     └────────────────────┬────────────────────────────────┘
                                          │
               ┌──────────────────────────┼──────────────────────────┐
               ▼                          ▼                          ▼
    ┌──────────────────┐      ┌───────────────────┐      ┌──────────────────────┐
    │ 2. RTL DESIGN    │      │ 3. HLS FLOW       │      │ 14. FPGA EMULATION  │
    │ SV、lint、CDC、  │      │ C/C++ → RTL       │      │ Early SW bring-up   │
    │ synth check      │      │ algorithm block   │      │ parallel flow       │
    └────────┬─────────┘      └─────────┬─────────┘      └──────────────────────┘
             │                          │
             └──────────────────────────┘
                                        │ RTL package
               ┌────────────────────────┼────────────────────────────────┐
               ▼                        ▼                                ▼
    ┌──────────────────┐   ┌────────────────────────┐   ┌───────────────────────┐
    │ 4. FUNCTIONAL    │   │ 5. FORMAL VERIFICATION │   │ 10. SoC IP INTEGRATION│
    │ VERIFICATION     │   │ FPV + LEC              │   │ SoC-level integration │
    │ UVM/coverage/    │   │                        │   │                       │
    │ regression       │   │                        │   │                       │
    └──────────────────┘   └────────────────────────┘   └───────────────────────┘
                                                        ┌───────────────────────┐
                                                        │ 11. MEMORY IP DESIGN  │
                                                        │ Macro/bank/ECC/repair │
                                                        │ → DFT / PD / STA      │
                                                        └───────────────────────┘
                                        │ Verified RTL
                     ┌──────────────────▼──────────────────────────────────┐
                     │  6. LOGIC SYNTHESIS                                │
                     │     SDC、gate netlist、LEC                          │
                     └────────────────────┬────────────────────────────────┘
                                          │ Gate netlist
               ┌──────────────────────────┼──────────────────────────┐
               ▼                          ▼                          ▼
    ┌──────────────────┐      ┌───────────────────┐      ┌──────────────────┐
    │ 7. DFT FLOW      │      │ 8. PHYSICAL DESIGN│      │ 9. STA FLOW      │
    │ Scan/ATPG/BIST   │      │ Full PD Flow      │      │ Multi-corner     │
    │ JTAG             │      │                   │      │ timing closure   │
    └──────────────────┘      └─────────┬─────────┘      └──────────────────┘
                                        │ GDS II
                     ┌──────────────────▼──────────────────────────────────┐
                     │  TAPE-OUT                                            │
                     └────────────────────┬────────────────────────────────┘
                                          │
               ┌──────────────────────────┼──────────────────────────┐
               ▼                          ▼                          ▼
    ┌──────────────────┐      ┌───────────────────┐      ┌──────────────────┐
    │ 12. COMPILER     │      │ 13. EMBEDDED     │      │ Silicon Bring-up │
    │ TOOLCHAIN        │      │ FIRMWARE          │      │ extends FPGA flow│
    │ custom CPU       │      │ BSP/driver/RTOS   │      │                  │
    └──────────────────┘      └───────────────────┘      └──────────────────┘
```

---

## 文档索引

| # | 文档 | 说明 | 输入 | 输出 |
|---|---|---|---|---|
| 0 | `Infrastructure_Setup_Flow.md` | EDA 工具检测、Wrapper 部署、MCP 配置 | 主机环境 | tool-status.json, module-status.json, tool-manifest.json, wrappers, MCP snippets |
| 1 | `Architecture_Evaluation_Flow.md` | 微架构探索、PPA estimate、risk | Product spec | Microarch doc |
| 2 | `RTL_Design_Flow.md` | SV RTL、lint、CDC、synth check | Microarch doc | Synthesis-ready RTL |
| 3 | `HLS_Flow.md` | Algorithm C/C++ → RTL | C source + TB | Verified RTL |
| 4 | `Functional_Verification_Flow.md` | UVM TB、coverage、regression | RTL + spec | Verified RTL + sign-off |
| 5 | `Formal_Verification_Flow.md` | FPV、LEC、formal | RTL + property | Proven property + LEC |
| 6 | `Logic_Synthesis_Flow.md` | Synthesis、constraint、LEC | RTL + SDC | Gate netlist |
| 7 | `DFT_Flow.md` | Scan、ATPG、BIST、JTAG | Gate netlist | Test-ready netlist + pattern |
| 8 | `PD_Flow_Architecture.md` | 完整 Physical Design | Netlist + SDC | GDS II |
| 9 | `STA_Flow.md` | Multi-corner timing、ECO | Routed DEF + SPEF | Timing closure report |
| 10 | `SoC_IP_Integration_Flow.md` | IP procurement、SoC 组装 | IP list + arch | Integrated SoC RTL |
| 11 | `Memory_IP_Design_Flow.md` | Memory macro、array、repair、view QA | Memory requirement + PDK | Qualified Memory IP + views |
| 12 | `Compiler_Toolchain_Flow.md` | 自定义 ISA 的 LLVM/GCC backend | ISA spec | Validated toolchain |
| 13 | `Embedded_Firmware_Flow.md` | BSP、driver、RTOS、validation | Chip datasheet | Validated firmware |
| 14 | `FPGA_Emulation_Flow.md` | FPGA port、bring-up、SW validation | ASIC RTL | FPGA prototype + SW |

各流程的阶段顺序、回退规则、阶段门控及升级处理以 `plugins/<domain>/agents/*-orchestrator.md` 为准。上方流程文档介绍架构、共享状态及 Skill 内容，通过链接引用 Agent 规则，不重复这些规则；若重复，`tests/test_agent_contract.py` 会失败。

---

## Orchestrator 间 Handoff Contract

每个 Orchestrator 都输出标准化 handoff package，供下一环节消费。

### Architecture → RTL Design

```json
{
  "handoff": "arch_to_rtl",
  "from": "Architecture Evaluation Orchestrator",
  "to":   "RTL Design Orchestrator",
  "package": {
    "microarch_doc":       "path/to/microarch.md",
    "module_hierarchy":    "path/to/hierarchy.json",
    "interface_specs":     "path/to/interfaces.md",
    "memory_map":          "path/to/memory_map.md",
    "clock_domains":       ["clk_core_1GHz", "clk_peri_200MHz"],
    "clock_power_budget":  "path/to/clock_power_budget.md",
    "coding_guidelines":   "path/to/guidelines.md",
    "verification_plan":   "path/to/vplan.md"
  }
}
```

### RTL Design → Verification

```json
{
  "handoff": "rtl_to_verif",
  "from": "RTL Design Orchestrator",
  "to":   "Verification Orchestrator",
  "package": {
    "rtl_filelist":  "filelist.f",
    "lint_report":   "lint_clean.rpt",
    "cdc_report":    "cdc_clean.rpt",
    "compile_order": "compile_order.f",
    "assertions":    "assertions.sva"
  }
}
```

### RTL Design → Synthesis

```json
{
  "handoff": "rtl_to_synth",
  "from": "RTL Design Orchestrator",
  "to":   "Synthesis Orchestrator",
  "package": {
    "rtl_filelist": "filelist.f",
    "sdc":          "constraints.sdc",
    "liberty_libs": ["tt.lib", "ss.lib", "ff.lib"],
    "dont_touch":   ["memories.list"],
    "target_freq":  "1GHz"
  }
}
```

### Synthesis → DFT → PD

```json
{
  "handoff": "synth_to_dft_to_pd",
  "from": "Synthesis → DFT Orchestrators",
  "to":   "Physical Design Orchestrator",
  "package": {
    "netlist":     "dft_netlist.v",
    "sdc":         "pd_constraints.sdc",
    "scandef":     "scan_chains.scandef",
    "lef":         ["tech.lef", "cells.lef"],
    "lib":         ["tt.lib", "ss.lib", "ff.lib"],
    "upf":         "power_intent.upf"
  }
}
```

### PD → Firmware（Post Tape-out）

```json
{
  "handoff": "pd_to_firmware",
  "from": "Physical Design Orchestrator",
  "to":   "Firmware Orchestrator",
  "package": {
    "memory_map":    "final_memory_map.md",
    "register_map":  "registers.json",
    "peripheral_list": ["UART0", "SPI0", "I2C0", "GPIO", "DMA"],
    "timing_spec":   "io_timing.md",
    "errata":        "silicon_errata.md"
  }
}
```

---

## 推荐实现顺序

### Phase 1 — 核心设计 Skill（Week 1）
1. Architecture Evaluation Skill + Stage Agent
2. RTL Design Skill + Stage Agent
3. 用小型可综合 block 验证

### Phase 2 — Verification（Week 2）
4. Functional Verification（UVM）
5. Formal Verification
6. 打通 Phase 1 → Phase 2 handoff

### Phase 3 — Implementation（Week 3）
7. Logic Synthesis
8. DFT
9. Physical Design
10. STA

### Phase 4 — Software（Week 4）
11. HLS
12. Compiler Toolchain
13. Embedded Firmware
14. FPGA Emulation

### Phase 5 — Orchestrator Integration（Week 5）
15. 实现全部 Orchestrator
16. 实现跨 Orchestrator handoff
17. 使用 RISC-V core/simple SoC 做 end-to-end test

---

## 全局 Agent 配置

所有 Agent 共享以下配置：

```json
{
  "model": "claude-sonnet-4-20250514",
  "max_tokens": 4096,
  "temperature": 0.2,
  "system_prompt_prefix": "You are a specialized AI agent in a chip design pipeline. You receive a structured state object and skill document. Always return a structured JSON result. Be precise and technically rigorous.",
  "output_format": {
    "stage": "string",
    "status": "PASS | FAIL | WARN",
    "confidence": "high | medium | low",
    "failure_class": "none | functional | timing | power_area | drc_lvs | coverage_gap | connectivity | tool_error | input_setup | spec_gap | resource_limit",
    "qor": "object — metrics per skill definition",
    "issues": "array — [{severity, description, fix}]",
    "suggested_next_step": "proceed | loop_back_to:<stage> | retry_stage | escalate | abandon",
    "output": "object — stage deliverables"
  }
}
```

上述 JSON 中字段名、enum 和固定 prompt 属于机器接口，保持英文。

**`confidence`**：编排器对结果可靠性的自评：
- `high`：确定性结果，工具证据干净，无豁免或估计，全部签核标准满足。
- `medium`：结果成立，但依赖豁免、估计、假设或工具回退路径。
- `low`：依赖未经验证假设、不完整数据或工具错误，建议人工审查。

**`failure_class`** — 跨领域失败分类，status=PASS 时为 `none`；与验证/形式验证专用根因的 `fix_request.failure_class` 不同：
- `functional` — logic or behavioral incorrectness
- `timing` — setup/hold/WNS violations
- `power_area` — 功耗或面积超出预算
- `drc_lvs` — 物理验证失败（DRC、LVS、天线效应）
- `coverage_gap` — verification coverage shortfall
- `connectivity` — CDC/RDC、协议或接口不匹配
- `tool_error` — EDA 工具崩溃、许可证或基础设施问题
- `input_setup` — 工具正常运行但输入错误（filelist、include 路径、配置、生成头文件、库视图）；始终升级处理，不重试、不回退
- `spec_gap` — 规格/需求缺失或不明确
- `resource_limit` — 超出最大迭代、最大轮数或计算预算

**`suggested_next_step`** — 建议接收方操作；`loop_back_to:<stage>` 必须指向编排器 Stage Sequence 中的阶段：
- `proceed` — 前进到下一阶段或交接给下游编排器
- `loop_back_to:<stage>` — 返回之前指定的阶段
- `retry_stage` — 重新运行当前阶段（暂时性 tool_error）
- `escalate` — 停止并要求人工决策
- `abandon` — unrecoverable; terminate the flow

---

## Skill 文件目录结构

以下 tree 是早期 per-stage Skill 布局，保留用于历史参考。
当前实际实现已经改为每个 domain 一个 Skill：

```text
plugins/<domain>/skills/<skill>/SKILL.md
```

完整 domain 包括：

- architecture
- rtl-design
- verification
- formal
- synthesis
- dft
- sta
- hls
- pd
- soc
- compiler
- firmware
- fpga
- memory-ip
- infrastructure
- meta

当前仓库统计：

**16 Orchestrators | 14 Flow Documents | 17 Skill Files**
