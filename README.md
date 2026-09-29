# digital-chip-design-agents

> Claude Code Marketplace 插件 —— 覆盖完整数字芯片设计流程。  
> 16 个插件 · 17 个 Skill 文件 · 14 个芯片设计领域 + 基础设施 + 流水线编排器 · 验证↔RTL 闭环反馈。

[![Validate](https://github.com/chuanseng-ng/digital-chip-design-agents/actions/workflows/validate.yml/badge.svg)](https://github.com/chuanseng-ng/digital-chip-design-agents/actions/workflows/validate.yml)

---

## 快速开始

安装 Node.js（≥18）后，可通过一条命令完成安装，无需 clone，也不需要 Python：

```bash
npx digital-chip-design-agents      # 自动检测已安装的 AI Agent，确认后安装
```

然后直接用自然语言描述任务：

```
为我的 AXI DMA 控制器模块运行 RTL 设计流程
分析 routed DEF 中的时序违例并给出 ECO 建议
为 FIFO 模块构建 UVM testbench
```

Claude 会在执行前自动加载正确的 Skill。

安装脚本、Marketplace 按域选择安装、其他 AI 助手
（Copilot / Gemini / OpenCode / Codex）以及完整参数说明，请参见
**[docs/INSTALL.md](docs/INSTALL.md)**。

---

## 可用插件

| 插件名 | 领域 | 适用场景 |
|-------------|--------|---------------------------|
| `chip-design-architecture` | 架构评估 | 探索微架构候选方案、估算 PPA、评估风险 |
| `chip-design-rtl` | RTL 设计（SystemVerilog） | 编写 RTL、lint、CDC 检查、综合可用性检查 |
| `chip-design-verification` | 功能验证（UVM） | 构建 testbench、编写测试、覆盖率收敛、运行 regression |
| `chip-design-formal` | 形式验证（FPV/LEC） | 属性证明、等价性检查、形式验证收敛 |
| `chip-design-synthesis` | 逻辑综合 | 配置 SDC、运行综合、使用 LEC 验证网表 |
| `chip-design-dft` | 可测性设计 | DFT 规划、scan 插入、ATPG、JTAG 配置 |
| `chip-design-sta` | 静态时序分析 | 分析时序、指导 ECO 收敛、完成时序 sign-off |
| `chip-design-hls` | 高层综合 | 将 C/C++ 转为 RTL、优化 directive、协同仿真 |
| `chip-design-pd` | 物理设计 | 完整 PD 流程：floorplan → placement → CTS → routing → sign-off |
| `chip-design-soc` | SoC IP 集成 | IP 评估、总线互联配置、芯片级仿真 |
| `chip-design-memory-ip` | Memory IP 设计 | SRAM/RF/ROM 宏选择、bank/ECC 架构、repair 规划、view 验证 |
| `chip-design-compiler` | 编译器工具链 | 为自定义 ISA 构建 LLVM/GCC backend、assembler、linker、runtime |
| `chip-design-firmware` | 嵌入式固件 | BSP、HAL 驱动、RTOS 集成、固件验证 |
| `chip-design-fpga` | FPGA 原型/仿真 | ASIC 移植到 FPGA、硬件 bring-up、原型机软件验证 |
| `chip-design-infrastructure` | 基础设施与 Memory | EDA 工具检测、wrapper 部署、MCP Server 配置、领域经验蒸馏 |
| `chip-design-meta` | 流水线编排 | 驱动验证↔RTL 闭环、管理 fix_requests、限制迭代次数 |

---

## 工作原理

每个插件安装两类核心内容：

1. **Skill**（`plugins/<domain>/skills/<domain>/SKILL.md`）—— Claude 在执行前读取的领域知识。包含逐阶段规则、QoR 指标、常见修复方式和输出要求。

2. **Orchestrator Agent**（`plugins/<domain>/agents/<domain>-orchestrator.md`）—— 管理完整多阶段流程的子 Agent。它负责阶段顺序、PASS/FAIL 判据、失败后的 loop-back 规则，以及需要人工输入时的明确升级。

当你用自然语言描述任务时，Claude 会自动加载对应 Skill。需要端到端执行完整流程时，则调用对应 Orchestrator。

每个 Orchestrator 都强制执行严格的阶段顺序与回退规则；14 个领域共同组成完整的 specification → tape-out 流水线。总流程图和 loop-back 细节见 **[docs/PIPELINE.md](docs/PIPELINE.md)**，各领域完整说明见 [docs/MASTER_INDEX.md](docs/MASTER_INDEX.md)。

---

## Memory 系统

每个领域 Orchestrator 都会从 `memory/` 下的两级持久化 Memory 中读取和写入信息：

- **`memory/<domain>/knowledge.md`** —— 已蒸馏的经验总结，例如失败模式、有效工具参数、PDK/工具特殊行为；每次会话开始时读取。
- **`memory/<domain>/experiences.jsonl`** —— 每次运行一条记录，以 `run_id` 进行 upsert；无论 sign-off、escalation 还是 abandon 都会写入。

可使用 `memory-keeper` Skill 将积累的运行记录重新蒸馏进 `knowledge.md`，并使用 `tools/qor_trends.py` 跟踪多次运行中的 QoR 趋势。完整 schema、蒸馏流程和 QoR 示例见 **[memory/README.md](memory/README.md)**。

---

## 仓库结构

```
digital-chip-design-agents/
├── .claude-plugin/marketplace.json   ← Marketplace 注册表（全部 16 个插件）
├── plugins/                          ← 每个插件独立目录（Skill + Orchestrator）
├── ides/                             ← IDE 专用配置（Copilot / Gemini / OpenCode / Codex）
├── memory/                           ← 各领域持久化两级 Memory（见 memory/README.md）
├── docs/                             ← 安装说明、流水线图、各领域流程文档
├── tools/qor_trends.py               ← QoR 趋势与回归检测
└── .github/workflows/                ← CI（validate.yml）和发布流程（release.yml）
```

---

## 贡献

参见 [CONTRIBUTING.md](CONTRIBUTING.md)。欢迎提交以下类型的 PR：

- 改进任意 `SKILL.md` 中的领域规则或 QoR 指标
- 为 Orchestrator 增加新的 loop-back 规则
- 增加新的 Skill 领域，例如封装/组装、模拟集成等

每个 PR 都会经过 CI 校验；合并前必须通过 validate workflow。

---

## License

MIT —— 参见 [LICENSE](LICENSE)。
