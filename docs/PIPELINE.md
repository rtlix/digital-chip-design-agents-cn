# Orchestrator 流程与端到端流水线

本文说明各领域 Orchestrator 如何组织阶段，以及 14 个设计领域如何连接为完整的芯片设计流水线。各领域更详细的流程请参见 [`MASTER_INDEX.md`](MASTER_INDEX.md)。

## Orchestrator 流程

每个 Orchestrator 都强制执行严格的阶段顺序，并定义明确的 loop-back 规则。

**物理设计（示例）：**

```
floorplan → placement → CTS → routing →
timing_opt → power_opt → area_opt → signoff
```

全部 14 个领域编排器采用相同模式，具体阶段和标准因领域而异。上方规则仅为示例；各流程的阶段顺序和回退规则以 `plugins/<domain>/agents/*-orchestrator.md` 为准。

## 端到端流水线

14 个设计领域（加上 Meta Pipeline Orchestrator）共同组成完整的芯片设计流水线：

```
[Specification / 规格]
      │
      ▼
[1. Architecture Evaluation / 架构评估] ──► microarch doc
      │
      ├──► [2. RTL Design / RTL设计] ──► [3. HLS]（算法模块）
      │           │
      │           │           ├──► [4. Functional Verification / 功能验证] ◄──┐
      │           └──► [5. Formal Verification / 形式验证]   ◄──┤
      │                       │（发现 bug）                    │ fix_request 闭环
      │                       │                          [Meta / Pipeline Orch.]
      │                       ▼                              │
      │              [6. Logic Synthesis / 逻辑综合]       ────┘
      │                       │
      │           ┌───────────┼───────────┐
      │           ▼           ▼           ▼
      │      [7. DFT]   [8. Physical   [9. STA]
      │                    Design]
      │                       │
      │                   [Tape-out]
      │
      ├──► [10. SoC IP Integration / SoC IP 集成]（SoC 级任务）
      ├──► [11. Memory IP Design / Memory IP 设计] ──► macros + views ──► DFT / PD / STA
      ├──► [12. Compiler Toolchain / 编译器工具链]（自定义 CPU 时）
      ├──► [13. Embedded Firmware / 嵌入式固件]
      └──► [14. FPGA Emulation / FPGA 原型验证]（流片前软件开发）
```
