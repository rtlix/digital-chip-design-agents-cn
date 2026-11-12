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

`<MEM>` 表示已经解析出的 Memory root，而不是字面量 `memory/` 目录。解析优先级为：显式 `--memory-root` → `$CHIP_DESIGN_MEMORY_ROOT` → 中央默认路径 → 仓库内 seed；可用 `python3 plugins/infrastructure/skills/memory-keeper/memory_root.py` 查看实际路径，最终以 Orchestrator 的 `## Memory` 章节为准。
任何 stage 前如存在则读取：
1. `<MEM>/soc/knowledge.md`
2. `<MEM>/soc/run_state.md`
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
- **Synopsys VCS** (`vcs`，命令方言 `synopsys`） — 含覆盖率统计的芯片级仿真
- **Cadence Xcelium** (`xrun`，命令方言 `cadence`） — 多语言芯片级仿真
- **Siemens Questa** (`vsim`，命令方言 `siemens`） — 芯片级仿真与协议检查

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
1. 先跑 boot/smoke，再跑 peripheral、bus stress 和 error injection。
2. 每个 IP 至少一个基本功能 test。
3. AXI/APB 等 bus protocol checker 全程启用。
4. 测试 multi-master contention、back-pressure、maximum outstanding。
5. Reset during traffic、clock-domain reset sequence 必须测试。
6. 所有 memory region 做 read/write/alias test。
7. 对 CPU-based SoC，执行 minimal firmware boot 与 interrupt test。
8. Scoreboard/assertion mismatch 必须分类，不能只靠最终软件输出判断。
9. 每个 IP 都使用按名称的端口连接；位置连接在 IP 修订重新排序端口后会静默误接。

10. 在完整 SoC filelist 上下文中，将整个列表作为一个单元编译并 lint `soc_top.sv`。单独 lint 时每个 IP 都是未知模块，端口位宽不匹配未被检查。

11. 有意黑盒化的 IP（硬宏、模拟模块、加密 IP）为 stub；其输出上的未驱动网络发现不属于连接错误。将其记为信息并指出 stub，避免真正未连接端口淹没其中。必须能指出它代表的宏/IP 才可认为无害；本仓库有自有 RTL 定义的未知模块属于缺失 filelist 条目（规则 12）。

12. 每个工具源列表都能看到 IP/模块才算集成完成。仿真、lint、综合、PD、形式验证通常读取独立列表，常存于 Makefile 变量；缺少模块时，sv2v/yosys 可能无错误地黑盒化，而读取其他列表的芯片级回归仍通过。枚举全部列表，确认每个新增文件均在其中，或注明未加入理由。`.f` 列表运行 `plugins/rtl-design/skills/rtl-design/check_design_inputs.py <filelist.f> --rtl-dir <rtl> --list <name>=<file> ...`。

13. 下游综合前转换 RTL（sv2v、Surelog/UHDM）时，对 SoC filelist 转换并使用消费工具解析输出（`sv2v <files> > out.v && yosys -q -p 'read_verilog out.v; hierarchy -check -top soc_top'`）。SystemVerilog 合法而 Verilog-2005 非法的结构会通过 lint 和芯片级仿真，仅在此失败。

### Integration Checklist (per IP)
- [ ] Correct module name and parameters
- [ ] All active ports connected
- [ ] Clock: correct domain
- [ ] Reset: correct domain and polarity
- [ ] Power ports: correct UPF domain
- [ ] Scan: SI/SO connected
- [ ] 源文件已注册到每个工具源列表（仿真、lint、综合、PD、形式验证）

### Common Integration Bugs
| Bug | Consequence |
|-----|------------|
| 错误时钟域 | 芯片中出现亚稳态 |
| 复位极性反转 | 模块始终无法退出复位 |
| valid/enable 未连接 | 模块失控运行或始终不运行 |
| AXI 地址偏移错误 | 外设位于错误基地址 |
| 模块缺少于综合或 PD 源列表 | 静默黑盒化：仿真回归通过但网表错误 |
| 转换器无法降低的 SV 结构 | 综合/PD 前端语法错误，lint/仿真无法发现 |

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
- [ ] 每个模块对每个工具源列表可见，豁免注明理由
- [ ] 转换后 RTL 在各下游前端解析通过，或检查报告 NOT RUN

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
每 stage 完成后按 `run_id` upsert `<MEM>/soc/experiences.jsonl`。
`run_id = soc_<YYYYMMDD>_<HHMMSS>`，流程开始时生成一次并复用。
最终 signoff 前保持 `signoff_achieved:false`。

### Run state
任何工具前第一步写 `<MEM>/soc/run_state.md`，记录 run_id/design_name/tool/start_time/last_stage。

### Optional: claude-mem index
如果 observation 工具可用，把 applied fix 写入 `chip-design-soc-fixes`；否则跳过。
