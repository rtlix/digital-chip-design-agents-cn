---
name: compiler-toolchain
description: >
  面向自定义处理器 ISA 的编译器工具链开发——包括 LLVM/GCC backend、assembler、
  linker script、runtime library 和 regression validation。适用于自定义 RISC-V
  扩展、私有 ISA，或现有 toolchain 无法正确支持的处理器。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill: Compiler Toolchain Development（编译器工具链开发）

## Invocation

当本 Skill 被加载且用户提出 compiler/ISA 任务时，**不要直接执行 stage**。
立即启动 `digital-chip-design-agents:compiler-orchestrator`，并传入完整用户请求及所有可用上下文。
Orchestrator 负责强制执行下文定义的 stage sequence、loop-back 和 sign-off criteria。

只有当 Orchestrator 在流程中读取本 Skill 获取阶段规则，或用户只是询问局部参考问题时，
才直接使用本文件的 domain rule。

## Pre-run Context

执行或建议**任何** stage 前，如存在则先读取：

1. `memory/compiler/knowledge.md` —— 已知 failure pattern、有效 tool flag、PDK/tool quirks。
2. `memory/compiler/run_state.md` —— 当前 `run_id`、`design_name`、`tool`、`last_stage`，用于中断后恢复。

无论由用户还是 Orchestrator 加载，都要先读取这些文件。

## Purpose

为自定义处理器 ISA 构建并验证完整 compiler toolchain（LLVM 或 GCC）。
它连接硬件与软件；没有正确的工具链，软件就无法在所设计芯片上运行。

---

## Supported EDA Tools

### Open-Source
- **LLVM/Clang**（`clang`、`llc`、`llvm-mc`、`llvm-objdump`）—— 新 ISA backend 的主要工具链
- **GCC + GNU Binutils**（`gcc`、`as`、`ld`、`objdump`）—— 另一种 backend，RISC-V extension 生态成熟
- **QEMU**（`qemu-system-*`）—— 无硬件时用于 toolchain validation 的 instruction-accurate ISA emulation

### Proprietary
- **Green Hills MULTI** —— 面向安全关键应用的 compiler/debugger IDE
- **IAR Embedded Workbench** —— ARM/RISC-V 认证编译器
- **Arm Compiler 6**（`armcc`）—— 基于 LLVM 的 Arm compiler

---

## Stage: isa_analysis

### ISA Feature → Toolchain Component Mapping

| ISA Feature | Toolchain Component |
|---|---|
| Instruction encoding | Assembler、disassembler |
| Register file | Register allocator、ABI |
| Calling convention | ABI、function-call lowering |
| Branch/jump | Control flow、delay-slot handling |
| Load/store addressing | Memory access pattern |
| SIMD/vector | Auto-vectorisation、intrinsics |
| Atomics | Memory model、concurrency |
| Multiply/divide | Integer arithmetic lowering |
| FPU presence | FP ABI（hard-float / soft-float） |
| Custom instruction | Intrinsic、builtin function |

### ABI Requirements

任何 backend code 开始前，必须先定义：

1. Argument passing：使用哪些 register，stack spill 规则
2. Return-value register
3. Callee-saved / caller-saved register 分类
4. Stack alignment（8 或 16 byte）
5. Data type size/alignment
6. Struct layout（padding/packing）
7. Thread-local storage model（若目标包含 RTOS）

### Output Required
- ISA → toolchain mapping table
- ABI specification
- 需要新建/修改的 LLVM/GCC backend file list
- Target triple：`<arch>-<vendor>-<os>`

---

## Stage: backend_dev

### LLVM Backend — 实现顺序

1. `RegisterInfo.td`：register class、alias、reserved register
2. `InstrInfo.td`：全部 instruction definition 与 encoding
3. `CallingConv.td`：argument/return register 规则
4. `SchedModel.td`：各 instruction class latency/throughput
5. `TargetMachine.cpp`：entry point、subtarget selection
6. `ISelDAGToDAG.cpp`：SelectionDAG → machine instruction lowering
7. `FrameLowering.cpp`：stack frame、prologue/epilogue
8. `AsmPrinter.cpp`：assembly text emission

### Testing per Component
- TableGen：`llvm-tblgen` 编译 .td 必须 0 error
- Codegen：`llc` 编译 C snippet，并人工检查 .s
- MC layer：`llvm-mc --show-encoding` 验证 instruction encoding

### QoR Metrics to Evaluate
- 所有 ISA instruction class 均可从 LLVM IR lower
- Calling convention function-call round trip 通过
- Generated assembly 中无 illegal instruction
- 基础 integer test program 可 compile/link，并在 ISS 正确执行

### Common Issues & Fixes
| Issue | Fix |
|---|---|
| TableGen pattern 不匹配 | 添加 operand type 匹配的显式 `Pat<>` |
| Stack corruption | 检查 prologue 是否保存全部 callee-saved register |
| Calling convention mismatch | 对照 ABI spec 检查 CCAssignToReg |

### Output Required
- 完整 LLVM backend source tree
- Regression test（llc lit test）
- Build instruction（CMake）

---

## Stage: assembler_dev

### Domain Rules
1. LLVM MC layer 通过 .td instruction definition 提供 assembler。
2. 每条 instruction 都做 encode/decode round-trip test。
3. 定义所有 ELF relocation type：`R_<ARCH>_*`。
4. `.section`、`.global`、`.type`、`.size`、`.align` 等 directive 必须可用。
5. 验证 C function 能生成 `.debug_info`，确保 GDB 所需 DWARF 存在。
6. 验证 forward/backward branch 的 PC-relative encoding。
7. 在 instruction 边界验证 immediate range、truncation、sign extension。

### QoR Metrics to Evaluate
- 所有 instruction encode/decode round-trip PASS
- 所有 relocation type 已定义并测试
- ELF 可被 `readelf -a` 正常读取
- 基础 DWARF debug info 正确生成

### Output Required
- 集成到 LLVM MC 的 assembler
- 每种 instruction format 的 encoding test
- Relocation definition table

---

## Stage: linker_config

### Linker Script Template

```ld
MEMORY {
  FLASH (rx)  : ORIGIN = 0x00000000, LENGTH = 512K
  RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 128K
}
ENTRY(_start)
SECTIONS {
  .text   : { *(.text.reset) *(.text*) *(.rodata*) } > FLASH
  .data   : { *(.data*) }  > RAM AT > FLASH
  .bss    : { *(.bss*) *(COMMON); PROVIDE(__bss_end = .); } > RAM
  .stack  : { . = ALIGN(16); PROVIDE(__stack_top = .); . += STACK_SIZE; } > RAM
}
```

### Domain Rules
1. Memory region 必须与芯片 memory map 完全一致。
2. Startup code（`crt0.S`）：复制 `.data` LMA→VMA、清零 `.bss`、调用 `main()`。
3. Stack 通过 linker symbol `__stack_top` 定义，size 可在 link 时配置。
4. Assembler stage 定义的所有 relocation type 都必须被支持。
5. Bare-metal binary 必须可 link、load，并从 reset vector 执行。

### QoR Metrics to Evaluate
- Link 时无 undefined symbol
- Runtime 下 `.data` 初始化正确
- Startup 时 `.bss` 清零
- Entry 时 stack pointer 正确

### Output Required
- 每种 memory configuration 的 linker script
- Startup code（crt0.S）
- Linker configuration 文档

---

## Stage: runtime_libs

### Required Libraries
| Library | 内容 | 来源 |
|---|---|---|
| compiler-rt | Integer multiply/divide、soft-float | LLVM |
| newlib/picolibc | Bare-metal C standard library | Port |
| libstdc++/libc++ | C++ standard library | LLVM/GCC |
| libm | Math library | newlib |

### Porting newlib
1. 实现 syscall stub：`_write`、`_read`、`_sbrk`、`_exit`、`_close`
2. `_sbrk`：基于 `__heap_start` / `__heap_end` linker symbol 管理 heap
3. `_write`：调试时输出到 UART 或 semihosting
4. C++ global constructor：在 linker script 加 `.init_array`

### QoR Metrics to Evaluate
- `printf`、`malloc`、`memcpy`、`strlen` 正常
- 无 HW FPU 时，soft-float 与 IEEE 754 bit-exact
- Stress allocation/free 下 heap 无 corruption
- C++ constructor 在 `main()` 前调用

### Output Required
- 已移植并编译的 runtime library
- Syscall stub
- Library test result

---

## Stage: toolchain_validation

### Validation Tiers
| Tier | Pass Criteria |
|---|---|
| Smoke（hello world） | 100% |
| Unit（逐 instruction asm test） | 100% |
| Compiler（C feature test） | ≥99% |
| Runtime（C library test） | ≥99% |
| Application（代表性 workload） | 输出正确 |
| Performance | 与 target 相差 ≤10% |

### QoR Metrics to Evaluate
- Compiler regression ≥99%
- Runtime test ≥99%
- Application workload 与 golden output 一致
- Miscompilation 数量为 0；wrong output 属于 P0 blocker

### Output Required
- 按 tier 的 regression pass/fail report
- 任一 miscompilation 的 root cause
- 与 target 的 performance comparison

---

## Stage: toolchain_signoff

### Sign-off Checklist
- [ ] Compiler 可为 custom ISA 生成正确代码
- [ ] Assembler 可正确 encode 所有 instruction
- [ ] Linker 对全部 memory configuration 有正确 script
- [ ] libgcc/compiler-rt、newlib、libm 全部通过
- [ ] objdump、readelf、nm、objcopy 支持 target
- [ ] GDB 或 LLDB target support 可用
- [ ] 有可用 ISS
- [ ] 全部 regression tier PASS
- [ ] ABI spec、getting-started guide、known issues 文档齐全

### Output Required
- Toolchain release package
- Validation report
- 最终 ABI specification
- Known issues list

---

## Memory

### Write on stage completion
每个 stage 完成后，以 `run_id` 为键写入/覆盖
`memory/compiler/experiences.jsonl` 中的一条 JSON record。
即使流程中断或单独调用 stage，也能持久化。

`run_id = compiler_<YYYYMMDD>_<HHMMSS>`，流程开始时生成一次并复用。
每条 JSON record 顶层都必须包含匹配的 `run_id`，最终 sign-off 前保持
`signoff_achieved:false`。

### Run state
启动任何工具前第一步写
`memory/compiler/run_state.md`：

```markdown
run_id:      compiler_<YYYYMMDD>_<HHMMSS>
design_name: <design>
tool:        <primary tool>
start_time:  <ISO-8601>
last_stage:  <first stage name>
```

每个 stage 完成后更新 `last_stage`。文件或父目录不存在时创建。

### Optional: claude-mem index
如果当前 session 提供 `mcp__plugin_ecc_memory__add_observations`，
在写 experiences 后把 applied fix 作为 observation 写入
`chip-design-compiler-fixes`。工具不存在时静默跳过，JSONL 是 canonical record。
