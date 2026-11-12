---
name: dft
description: >
  可测性设计（Design for Test）——包括扫描架构规划、扫描链插入（scan insertion）、ATPG 测试向量生成、
  嵌入式存储器 MBIST，以及 JTAG 边界扫描（JTAG boundary scan）。适用于规划 DFT 策略、插入 scan、
  生成测试 pattern，或验证芯片在量产制造阶段是否具备可测试性。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill：可测性设计（DFT）

## 调用方式

- **如果由用户直接调用**并给出 DFT 任务：立即启动
  `digital-chip-design-agents:dft-orchestrator` Agent，并将用户完整请求和所有可用上下文传递给它。
  不要直接执行各 stage。
- **如果由 `dft-orchestrator` 在流程中调用**：不要再次创建 Agent。
  将本文件视为只读参考，仅返回调用方所需的阶段规则、sign-off 标准或 loop-back 指南。

在已经运行的 Orchestrator 内再次启动自身会造成递归委派，必须禁止。

## 运行前上下文

在执行或建议**任何** stage 前，如果以下文件存在，应先读取：

1. `<MEM>/dft/knowledge.md` —— 已知失败模式、有效工具参数、PDK/工具特殊行为。
   每个 stage 的决策都应吸收其中经验；若不存在则继续。
2. `<MEM>/dft/run_state.md` —— 当前运行身份（`run_id`、`design_name`、`tool`、`last_stage`）。
   用于中断后的正确恢复；若不存在，表示新运行开始，Orchestrator 会在第一阶段前创建。

无论本 Skill 是由用户直接加载，还是由 Orchestrator 中途读取，都必须执行上述预读，以确保任何诊断前都已经查询历史修复经验。

## Purpose（目的）

指导完整 DFT 流程，从架构规划、ATPG pattern 生成、BIST 插入、JTAG 配置一直到 sign-off。
目标是保证制造后的芯片满足故障覆盖率和 DPPM 等质量指标。

---

## Supported EDA Tools（支持的 EDA 工具）

### Open-Source（开源）
- **Yosys DFT plugins**（`yosys`）—— 用于开源流程的基础 scan insertion
- **OpenROAD DFT utilities**（`openroad`）—— 在 OpenROAD/ORFS 流程中进行 scan insertion

### Proprietary（商业）
- **Synopsys TetraMAX ATPG** (`tmax`，命令方言 `synopsys`） — 测试向量生成、故障仿真及压缩
- **Cadence Modus Test** (`modus`，命令方言 `cadence`） — ATPG、扫描 DRC 及诊断
- **Siemens Tessent** (`tessent`，命令方言 `siemens`） — 完整 DFT 套件：扫描、ATPG、MBIST、IJTAG

---

## Tool Notes: Siemens Tessent

Tessent 现代流程以 **context** 为核心。旧式 `add_scan_groups` / `add_scan_chains` dofile 可能完整退出但实际一个 scan cell 都没插，因此 verdict 必须看 inserted-cell/chain 结果，不能只看 exit status。以下规则基于 Tessent 2025.4 的实测。

### Running it
- Batch：`tessent -shell -dofile <f>.do -log <f>.log -replace < /dev/null`。缺 `< /dev/null` 时，dofile 中止后 shell 可能继续等 stdin；缺 `-replace` 时旧 log 可能残留，看起来像本次结果。
- 每次 scan insertion 前删除旧 TSDB output，防止 stale TSDB 被重新读入。
- 每个 option 都要确认当前安装版本接受；例如 2025.4 会拒绝部分旧参数。
- 安装目录中的 algorithm library、`share/UsageExamples` 等 licensed reference 只读；需要修改时复制进项目。

### Cell library (scan insertion and ATPG)
- `read_liberty` 只提供 cell attribute；cell 行为来自 Verilog model，经 **LibComp** 编译成 `.atpglib`：`libcomp <models.v> -dofile ... < /dev/null`。再用 `read_cell_library` 读取，并结合 `read_liberty`；最终用 `write_cell_library ... -include_created_dft_cell_selections` 生成 `.tcelllib`。
- LibComp log 中任何 `// Error` 都是 FAIL。
- Cell model 使用 gate primitive；裸 `assign y = a;` 的 buffer 可能被视为 wire，进而 fail buffer check。
- 明确维护 `dft_cell_selection`；自动选择可能选中特殊低功耗 cell。Buffer、inverter、2:1 mux、lockup latch 应显式指定。

### Scan insertion and ATPG
1. `set_context dft -scan -no_rtl -design_id gate` → `read_cell_library` → read netlist → `set_current_design` → 定义 clocks → `set_scan_enable` → `set_system_mode analysis`，此处运行 Scan DRC。
2. `add_scan_mode <name> -chain_count N -si_connections ... -so_connections ...` 绑定现有 scan port，再 `analyze_scan_chains`、`insert_test_logic`、`write_design -tsdb`。如果 port binding fail 后脚本偷偷改用 tool-created port，必须报告，因为 chain 已不再使用 architecture 指定端口。
3. ATPG 新 session：`set_context patterns -scan`、`read_design <design> -design_id gate`、`import_scan_mode <name>`，再按 fault model 生成 pattern。
4. Chain count 应服从项目 DFT architecture；不要为了让工具 setup 通过擅自改链数。Contract wording：**a chain count the project's DFT architecture fixes** 必须作为硬输入。
5. 有意排除的 flop 会使 S1/S2 之类 Scan DRC rule 失败；只有 architecture 明确决定这些 flop 不进链时才能降级 severity，并记录 rule ID、instance count 与理由。**Demoting a Scan DRC rule from error to warning** 不能成为普通消错手段。

### MemoryBIST
1. `set_context dft -rtl -design_id rtl1`；读取 RTL 和每个 memory macro 的 TCD（`tcd_memory`）描述。
2. `check_design_rules` → `create_dft_specification` → 必要时 `set_config_value` → `process_dft_specification`。
3. `extract_icl` → `create_patterns_specification` → `process_patterns_specification`。
4. `run_testbench_simulations -simulator vcs`（或实际 simulator）。
5. 算法定义/示例优先参考安装目录 `lib/tools/etv/membistipg_algos/`、`share/UsageExamples/*.tgz`。
6. TCD `LogicalPorts` 顺序为 read、write、read-write；没有 column address bit 时 `BitGrouping` 可能被强制。
7. `DFT_C1-1`：memory clock 必须可从 primary input 追踪；手工实例化的 clock-gate 若模型未读入会被当 black box。
8. 插入时只读 memory interface；若 simulation 又额外读 behavioral model，避免 duplicate module。
9. Fault proof 使用 plusarg 注入 fault，并让每种 fault 的 run 使用独立 simulation 目录，避免结果混用。

---

## Stage: dft_architecture

### Domain Rules（领域规则）
1. Scan 架构：ASIC 优先 full-scan，尽可能覆盖全部 sequential element
2. Scan chain 数量：经验值可取总 flip-flop 数的平方根，在 ATE 测试时间与布线之间权衡
3. Chain length 平衡：所有 chain 相对目标长度偏差控制在 ±5%
4. Compression：设计超过 1M FF 时使用 EDT/OPMISR，降低 ATE test time
5. MBIST：相同 width/depth 类别的 memory group 使用一个 controller
6. JTAG：采用 IEEE 1149.1 TAP controller；所有 IO pin 使用 boundary scan
7. At-speed test：选择 LOC（launch-on-capture）或 LOS（launch-on-shift），并与 test team 确认
8. Test mode：`scan_mode`、`mbist_mode`、`jtag_mode` 必须互斥
9. Power domain：scan 结构必须遵守 UPF power-domain 边界
10. 规划扫描链前对输入设计执行下方扫描就绪审查。在此发现阻碍只需修改 RTL，等到 Scan DRC 才发现则浪费一次插入迭代。

11. 以 RTL 交付而非工具插入的 DFT 逻辑（TAP 控制器、BIST 控制器、测试模式 mux、Wrapper）属于可综合 RTL；遵守 rtl-design Skill 编码规则，集成前 lint 必须为 0 错误。

### Scan-Readiness Audit (before insertion)
插入前检查 RTL 或 DFT 前网表中阻碍扫描测试的结构。这些问题由 RTL 流程负责，扫描链插入无法代为修复：
- RTL 生成的时钟（`assign gclk = clk & en;`）：其后的触发器在扫描模式下不可达
- 时钟门控单元的使能未与测试使能（`test_en` / `scan_en`）进行 OR 合并
- 内部逻辑驱动的异步置位/复位缺少测试模式旁路：扫描移位时无法保持无效
- 非有意设计的锁存器（lockup latch 与时钟门控单元内部锁存器除外）
- 组合反馈环：ATPG 无法建模
- 片上三态总线：争用无法测试
- 既无旁路路径也无 BIST Wrapper 的存储器（FIFO 的存储阵列也属于存储器）
- 未定义测试模式行为的黑盒与模拟接口

每项发现都必须指出实例及违反的上述规则。插入可修复的发现（测试点、工具插入的复位或时钟 mux）纳入 `scan_insertion`；需要修改 RTL 的发现交回 RTL 流程，不得在此修改 RTL。

### 必需的 DFT IO 信号
- `scan_en`（SE）：primary input，ATE 必须可控
- `scan_in[]`（SDI）：每条 chain 一个
- `scan_out[]`（SDO）：每条 chain 一个
- `test_clk`：独立于 functional clock，或使用其 gated 版本

### QoR Metrics to Evaluate（QoR 指标）
- DFT spec 完整：insertion 前已定义全部元素
- 扫描就绪审查：需要修改 RTL 的未关闭发现为 0
- 预计 fault coverage：解析估算 ≥ 目标
- 预计 test time：不超过 ATE budget

### Output Required（必须输出）
- DFT architecture 文档
- 扫描就绪审查报告（发现、实例、责任方：插入或 RTL）
- Scan chain 规划（数量、预计长度、IO）
- Test mode 定义

---

## Stage: scan_insertion

### Domain Rules（领域规则）
1. 用 scan-equivalent cell 替换标准 FF（SDFF、SDFFRQ 等）。
2. Scan exclusion 只用于明确对象，例如 memory-mapped register、MBIST controller、JTAG cell。
3. 不在 clock-gating enable、未经 care cell 处理的 async set/reset path 上盲目插 scan。
4. >100K FF 时考虑 EDT compressor/decompressor。
5. 跨 clock-domain chain 插 lockup latch。
6. Placement-aware reorder 降低 scan wirelength。
7. 对低 coverage net 可增加 controllability/observability test point。
8. 每个 Scan DRC error 先按 owner 分类再 retry。Insertion 能修的 chain connection/test point/tool-inserted reset/clock mux/lockup latch 留在本阶段；由设计本身导致的 generated clock、不可控 async reset、意外 latch、combinational loop 不会靠重跑 insertion 变好，应停止并交回 RTL flow，附 instance 和 rule。
9. 不得用“排除 offending flop”换 clean Scan DRC，也不得把 fault 改成 untestable 来抬 coverage；所有 exclusion 必须有明确设计理由。
10. Severity 同理：**Demoting a Scan DRC rule from error to warning** 只允许 architecture 有意把某些 flop 留在 chain 外（如 TAP-clocked domain、BIST controller）时使用；报告 decision、rule ID、instance count，其他被该降级隐藏的 instance 仍算 open finding。

### Scan DRC Rules (all must pass before ATPG)
- Scan data path 不得被 clock signal 驱动
- Scan 中不得有 combinational feedback loop
- Functional mode 的 scan enable 必须 glitch-free
- 所有 scan FF 的 SI/SE connection 正确

### QoR Metrics to Evaluate
- Scan FF count：全部 sequential element 减显式批准 exclusion
- Chain count/length：按 architecture spec（约 ±5%）
- Scan DRC：0 error

### Output Required
- Scan-inserted netlist
- Scan chain definition（.scandef）
- Scan DRC report

---

## Stage: atpg

### Fault Model 目标
| Fault Model | Target Coverage |
|---|---:|
| Stuck-at (SAF) | ≥ `design_state.constraints.dft.saf_coverage_pct`%（默认 99%） |
| Transition Delay | ≥ `dft.transition_coverage_pct`%（默认 95%） |
| Cell-Aware | ≥ `dft.cell_aware_coverage_pct`%（默认 95%） |
| Bridging | ≥ `dft.bridging_coverage_pct`%（默认 90%） |
| Path Delay | 仅 critical path |

### Domain Rules（领域规则）
1. Transition ATPG 至少覆盖 slow/fast capture clock。
2. 使用 X-bounding 提高 pattern quality。
3. Untestable fault 分类为 Redundant 或 ATPG-Untestable，并完整记录。
4. EDT 设计使用 compressed pattern。
5. At-speed pattern 在 sign-off 前经 STA 验证 capture timing。
6. Good-machine simulation 跑实际 pattern 集，0 failure；只跑 subset 时明确写 “20 of 1574”，不得冒充 full set。
7. **Prove the pattern testbench can fail.** 至少一次在 broken scan link 的 netlist（或故意翻转一个 pattern bit）上重跑，确认 testbench 报 mismatch。若 broken netlist 也 PASS，则 good-machine PASS 是 unverified。
8. ATPG cell model 与 pattern simulation cell model 若都由同一来源派生（例如只有 Liberty、没有独立 vendor Verilog），必须说明两者并非独立证据，可能共享同一解析错误。

### QoR Metrics to Evaluate
- SAF coverage ≥ target
- Transition coverage ≥ target
- Pattern count 尽量小（影响 ATE time/cost）
- Good-machine simulation：0 failure，且 negative control 能 fail

### Output Required
- STIL/WGL pattern
- 各 fault model coverage report
- Untestable fault list + classification

---

## Stage: bist_insertion

### MBIST 规则
1. 相同 width/depth class 的 memory 可共享一个 MBIST controller。
2. March algorithm 使用 MATS+、March-C 或质量规范要求的算法。
3. BIST 期间 memory 与 functional logic 隔离。
4. 全 memory 同时 BIST 时验证 IR drop。
5. 访问通过 JTAG TAP 或 dedicated BIST port。
6. **Prove detection per fault class, not by a passing run.** 对算法宣称覆盖的每类 fault 分别注入：每 bit/per-address-bit stuck-at、transition、coupling、write-mask/byte-enable stuck、address decoder，并与独立 golden model 的 expected verdict 对比；按 class 报 detected/injected。Fault-free memory PASS 只能证明“不 false-fail”，不能证明能抓 fault。
7. Fault proof 必须覆盖 full address space。Tessent 等 generated MBIST pattern 可能默认打开 `reduced_address_count` 加速仿真；该模式的 fault proof 会漏掉 reduced range 之外的 fault。
8. 对比 tool-generated MBIST 与现有 in-house MBIST 时，使用同一组 memory/fault，比较 per-class detection、algorithm cycle、area；multi-port memory 若每 logical port 单独跑一遍，cycle count 必须按相同口径统计。

### LBIST 规则（如需要）
1. STUMPS：PRPG + MISR + scan chains
2. Alias probability < 1e-10
3. LBIST clock 与 functional clock 分离，通常分频

### QoR Metrics to Evaluate
- MBIST 覆盖全部 memory instance
- MBIST fault coverage ≥ `dft.mbist_coverage_pct`（默认 99%）
- BIST power 满足 IR-drop budget
- LBIST alias probability 达标

### Output Required
- BIST-inserted netlist
- BIST controller connection report
- MBIST fault coverage report
- BIST power estimate

---

## Stage: jtag_setup

### Domain Rules（领域规则）
1. TAP pin：TCK、TMS、TDI、TDO、TRST_N，需要专用 pad
2. Boundary scan cell：所有 digital IO pin 都必须有 BSR cell
3. 必需 instruction：BYPASS、IDCODE、SAMPLE/PRELOAD、EXTEST
4. IDCODE register：32 bit，每个 device 唯一，符合 IEEE 1149.1
5. Core 处于 reset 时 TAP 仍应可访问
6. Security：量产芯片提供基于 OTP/fuse 的 JTAG lockout 机制

### QoR Metrics to Evaluate（QoR 指标）
- TAP DRC：全部必需 instruction 已实现
- Boundary scan chain：所有 IO 均已包含
- JTAG connectivity simulation：PASS
- IDCODE：唯一且格式正确

### Output Required（必须输出）
- JTAG-inserted netlist
- BSDL file
- TAP connectivity report

---

## Stage: dft_signoff

### Sign-off Checklist
- [ ] Scan DRC：0 error
- [ ] SAF coverage：≥ `design_state.constraints.dft.saf_coverage_pct`%（默认 99%）
- [ ] Transition coverage：≥ `design_state.constraints.dft.transition_coverage_pct`%（默认 95%）
- [ ] Good-machine simulation：0 failure
- [ ] MBIST：全部 memory 被覆盖；coverage ≥ `design_state.constraints.dft.mbist_coverage_pct`%（默认 99%）
- [ ] JTAG：BSDL 已生成并验证
- [ ] DFT netlist：与 pre-DFT netlist 做 LEC，结果 EQUIVALENT

### Output Required（必须输出）
- DFT sign-off report
- 最终 test pattern files
- BSDL file
- DFT netlist（提供给 PD）

---

## Constraint Validation

权威 schema 和 stage-entry 校验规则见
`plugins/meta/skills/pipeline-orchestration/SKILL.md` 的 Constraints Schema。

**DFT 没有必填 constraint key**，本域所有约束都有 schema 默认值。

**可选 constraint：**
- `constraints.dft.saf_coverage_pct`（默认 99）—— stuck-at fault coverage 目标
- `constraints.dft.transition_coverage_pct`（默认 95）—— transition-delay coverage 目标
- `constraints.dft.cell_aware_coverage_pct`（默认 95）—— cell-aware fault coverage 目标
- `constraints.dft.bridging_coverage_pct`（默认 90）—— bridging fault coverage 目标
- `constraints.dft.mbist_coverage_pct`（默认 99）—— MBIST memory fault coverage 目标
- `constraints.dft.chain_balance_pct`（默认 5）—— chain length 最大偏差百分比

用这些值评估 QoR 时，应在 history 中设置对应 `constraint_ref`，例如
`"dft.saf_coverage_pct"`。

---

## Memory

### Stage 完成后写入

每个 stage 完成后，无论当前是否运行完整 Orchestrator，都在
`<MEM>/dft/experiences.jsonl` 中以 `run_id` 为键写入或覆盖一条 JSON 记录。
即使流程被中断或只调用单独 stage，也能持久保存结果。

`run_id` 使用 `dft_<YYYYMMDD>_<HHMMSS>`，在流程开始时只生成一次，后续 stage 复用。
每条 JSON record 都必须包含顶层 `"run_id"` 字段且与该键一致；如果缺失，写入前必须拒绝或重新生成。
最终 sign-off 完成前，`signoff_achieved` 必须为 false。

### Run state

启动任何工具前，第一件事写入 `<MEM>/dft/run_state.md`：

```markdown
run_id:      dft_<YYYYMMDD>_<HHMMSS>
design_name: <design>
tool:        <primary tool>
start_time:  <ISO-8601>
last_stage:  null
```

仅在某个 stage 成功完成后，才把 `last_stage` 更新为该 stage 名。
该文件用于 wakeup-loop 和恢复会话，不依赖模型内存。
文件或父目录不存在时创建。

### 可选：claude-mem index

如果当前会话存在 `mcp__plugin_ecc_memory__add_observations`，在写入
`experiences.jsonl` 后，将每个 applied fix 作为 observation 写入实体
`chip-design-dft-fixes`。工具不存在则静默跳过；JSONL 是权威记录。
