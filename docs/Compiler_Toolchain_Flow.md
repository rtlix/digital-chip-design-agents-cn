# 编译器工具链开发流程 — 完整架构设计
## Orchestrator + Stage Agents + Skills

> **目的**：面向自定义处理器 ISA 或嵌入式 SoC 的 AI 驱动编译器工具链开发与验证流程。覆盖 ISA 分析、compiler backend、assembler、linker、runtime library 和 toolchain validation。这是让软件真正能够在目标芯片上运行的关键软件层。

---

## 1. 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│              COMPILER TOOLCHAIN ORCHESTRATOR                 │
│  输入：ISA spec、processor microarch、ABI requirement         │
│  输出：已验证的 compiler toolchain（GCC/LLVM）                 │
└────────────────────────┬─────────────────────────────────────┘
                         │
     ┌───────────────────┼────────────────────────────┐
     ▼                   ▼                            ▼
  ISA Spec           Backend Dev               Toolchain
  Agent              Agent                     Validation Agent
     │                   │                            │
  SKILL              SKILL                        SKILL
```

---

## 2. 共享状态对象

```json
{
  "run_id": "compiler_001",
  "processor_name": "my_cpu",
  "inputs": {
    "isa_spec":          "path/to/isa.md",
    "microarch_doc":     "path/to/microarch.md",
    "base_toolchain":    "LLVM-17 | GCC-13",
    "abi_spec":          "path/to/abi.md",
    "target_triple":     "mycpu-unknown-elf",
    "register_file":     "32x 32-bit GPR + 16x 64-bit FPR",
    "endianness":        "little",
    "word_size":         32
  },
  "stages": {
    "isa_analysis":        { "status": "pending", "output": {} },
    "backend_dev":         { "status": "pending", "output": {} },
    "assembler_dev":       { "status": "pending", "output": {} },
    "linker_config":       { "status": "pending", "output": {} },
    "runtime_libs":        { "status": "pending", "output": {} },
    "toolchain_validation":{ "status": "pending", "output": {} },
    "toolchain_signoff":   { "status": "pending", "output": {} }
  },
  "test_results": {
    "compile_tests": 0, "asm_tests": 0,
    "link_tests": 0, "runtime_tests": 0,
    "regression_pass_rate": 0.0
  },
  "flow_status": "not_started"
}
```

---

## 3. Stage Sequence（阶段顺序）

```
[ISA Analysis] ──► [Backend Dev] ──► [Assembler Dev] ──► [Linker Config]
                        ▲                                       │
                        │ codegen error                         │
                        └───────────────────────────────────────┘
                                                               │ pass
                              ▼
                       [Runtime Libraries] ──► [Toolchain Validation]
                                                      │ regression fail
                                                      └──► Backend Dev
                                                      │ pass
                                               [Toolchain Sign-off]
```

### Loop-Back Rules

| 失败条件 | 回退到 | 最大次数 |
|---|---|---:|
| Codegen 生成错误 instruction | Backend Dev | 5 |
| Assembler encoding error | Assembler Dev | 3 |
| Linker unresolved symbol | Linker Config | 3 |
| Regression pass rate <95% | Backend Dev | 3 |
| Runtime library crash | Runtime Libs | 3 |

---

## 4. Skill 文件说明

### 4.1 `sv-compiler-isa/SKILL.md`

```markdown
# Skill: Compiler — ISA Analysis

## Purpose
分析处理器 ISA，识别所有需要 compiler 支持的特性，并映射到具体 toolchain component。

## ISA Feature → Toolchain Component Mapping
| ISA Feature | 影响的组件 |
|---|---|
| Instruction encoding | Assembler、disassembler |
| Register file | Register allocator、ABI |
| Calling convention | ABI、function-call lowering |
| Branch/jump instruction | Control-flow lowering、branch delay |
| Load/store addressing | Memory access pattern |
| SIMD/vector instruction | Auto-vectorization、intrinsics |
| Atomic instruction | Memory model、concurrency support |
| Multiply/divide | Integer arithmetic lowering |
| FPU presence | Floating-point ABI（hard/soft） |
| Privileged instruction | Runtime、OS support layer |
| Custom instruction | Intrinsics、builtin function |

## ABI Requirements to Define
1. Calling convention：argument 通过 register 还是 stack
2. Return value convention：返回值 register
3. Callee-saved / caller-saved register
4. Stack alignment：8 或 16 byte
5. Data type size/alignment
6. Struct layout：padding、packing
7. Thread-local storage model

## QoR Metrics
- 所有 ISA instruction class 都映射到 toolchain component
- ABI 完整，无歧义
- Custom instruction 定义 intrinsic interface

## Output Required
- ISA→toolchain mapping table
- ABI specification
- 需要创建/修改的 LLVM/GCC backend file list
```

---

### 4.2 `sv-compiler-backend/SKILL.md`

```markdown
# Skill: Compiler — Backend Development (LLVM-based)

## Purpose
实现面向自定义 ISA 的 machine-code generation backend。

## LLVM Backend Components to Implement
1. Target description（.td）：
   - RegisterInfo.td
   - InstrInfo.td
   - CallingConv.td
   - SchedModel.td

2. C++ backend class：
   - TargetMachine
   - RegisterInfo
   - InstrInfo
   - ISelDAGToDAG
   - AsmPrinter
   - FrameLowering

3. Optimization hint：
   - Instruction scheduling model
   - Inlining/unrolling cost model
   - Pipeline hazard recognizer

## Development Order (Recommended)
1. Register file + calling convention
2. Basic integer instruction（ALU/load/store/branch）
3. Function call lowering
4. DAG selection pattern
5. FPU instruction
6. SIMD/vector instruction
7. Custom instruction/intrinsic
8. Scheduling model

## Testing per Component
- TableGen：`llvm-tblgen` 能编译 .td
- Codegen：`llc` 编译 C snippet，检查 .s
- MC layer：`llvm-mc --show-encoding` 验证 encoding

## QoR Metrics
- 所有 ISA instruction class 均可由 LLVM IR codegen
- Calling convention round-trip 正确
- 生成代码中无 illegal instruction
- LLVM basic test-suite 通过

## Output Required
- 完整 LLVM backend source tree
- Regression test file
- Build instruction
```

---

### 4.3 `sv-compiler-assembler/SKILL.md`

```markdown
# Skill: Compiler — Assembler Development

## Purpose
实现或配置目标 ISA 的 assembler，使手写 assembly 和 compiler 输出都能正确编码。

## LLVM MC Layer
1. MCInstrDesc：来自 .td 的 encoding
2. Fixup：branch target/symbol reference relocation
3. ELF object writer：生成 .o
4. Disassembler：binary → mnemonic

## Assembler Syntax Requirements
1. AT&T / Intel syntax 选择并写入 ABI
2. 支持 .section、.global、.type、.size、.align
3. Pseudo instruction：NOP、CALL
4. 定义全部 ELF relocation
5. 支持 DWARF debug info

## Encoding Validation
1. 每条 instruction 做 encode/decode round-trip
2. 检查 immediate range、truncation、sign-extension
3. 检查 PC-relative branch offset
4. Register number 与 ISA register file 一致

## QoR Metrics
- 全部 instruction round-trip PASS
- 全部 relocation 已定义并测试
- ELF 可由 readelf 正确读取

## Output Required
- LLVM MC assembler source
- Encoding test suite
- Relocation definition table
```

---

### 4.4 `sv-compiler-linker/SKILL.md`

```markdown
# Skill: Compiler — Linker Configuration

## Purpose
为目标 processor memory map 配置 GNU ld 或 LLVM lld，并生成可执行 binary。

## Linker Script Requirements
1. Memory region：FLASH、RAM，来自芯片 memory map
2. Section placement：.text/.rodata/.data/.bss/.stack/.heap
3. Entry point：reset vector / entry symbol
4. Startup code：复制 .data，清零 .bss
5. Stack/heap size 可通过 linker symbol 配置

## Example Linker Script Structure
```ld
MEMORY {
  FLASH (rx)  : ORIGIN = 0x00000000, LENGTH = 512K
  RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 128K
}
SECTIONS {
  .text   : { *(.text*) *(.rodata*) } > FLASH
  .data   : { *(.data*) } > RAM AT > FLASH
  .bss    : { *(.bss*) *(COMMON) } > RAM
  .stack  : { . = . + STACK_SIZE; } > RAM
}
```

## Relocation Support
1. Assembler 定义的 relocation 全部由 linker 处理
2. 如支持 shared library，则实现 PLT/GOT
3. Weak symbol 正确解析

## QoR Metrics
- Bare-metal hello world 可 link/run
- .data startup 初始化正确
- .bss startup 清零
- Standard library 无 undefined symbol

## Output Required
- 每种 memory configuration 的 linker script
- Startup code
- Linker configuration 文档
```

---

### 4.5 `sv-compiler-runtime/SKILL.md`

```markdown
# Skill: Compiler — Runtime Libraries

## Purpose
构建/移植编译代码运行所需的 runtime library。

## Required Libraries
| Library | 内容 | 来源 |
|---|---|---|
| libgcc/compiler-rt | Integer multiply/divide、FP soft-float | GCC/LLVM |
| newlib/picolibc | Bare-metal C standard library | newlib port |
| libstdc++/libc++ | C++ standard library | GCC/LLVM |
| crt0.o | C runtime startup | Custom |
| libm | Math library | newlib |

## Porting Steps for newlib
1. 实现 _write/_read/_sbrk/_exit 等 syscall stub
2. 实现 _sbrk 管理 heap
3. _write 连接 UART 或 semihosting
4. 使用正确 word size 和 endianness

## Soft-Float Library
1. compiler-rt/libgcc 提供 __addsf3、__mulsf3、__divdf3 等
2. 用 FP test suite 验证
3. 对性能瓶颈做 profile/optimization

## QoR Metrics
- C standard library 通过 test suite
- Soft-float 与 reference bit-exact
- Stress test 下 heap/stack 无 corruption
- C++ constructor startup 正常调用

## Output Required
- Ported runtime library
- Syscall stub
- Library test result
```

---

### 4.6 `sv-compiler-validation/SKILL.md`

```markdown
# Skill: Compiler — Toolchain Validation

## Purpose
通过 regression suite 验证 compile、assemble、link、execution 的完整工具链。

## Validation Tier Structure
| Tier | 内容 | Pass Criteria |
|---|---|---|
| Smoke | Hello world、basic arithmetic | 100% |
| Unit | Per-instruction assembly test | 100% |
| Compiler | C/C++ feature / GCC torture test | ≥99% |
| Runtime | C library test | ≥99% |
| Application | FFT/sort 等代表性 workload | 正确输出 |
| Performance | Cycle count vs target | 差异 ≤10% |

## Execution Environment Options
1. ISS：cycle-accurate，适合大量测试
2. RTL simulation：慢但精确，用于最终验证
3. FPGA prototype：比 RTL sim 快，接近 cycle-accurate
4. Silicon：最终验证

## Key Test Categories
- Integer arithmetic / overflow / zero
- Branch：forward/backward/indirect/function-call
- Load/store：全部 width/alignment/endianness
- FPU：IEEE 754
- ABI：function call、varargs、struct passing
- Atomic：memory ordering

## QoR Metrics
- Compiler regression ≥99%
- Runtime test ≥99%
- Application 无 miscompilation
- Performance 与 target 差异 ≤10%

## Output Required
- Regression report
- Miscompilation root-cause analysis
- Performance comparison
```

---

## 5. Orchestrator System Prompt

```
You are the Compiler Toolchain Orchestrator.

You guide the development and validation of a complete compiler toolchain
(LLVM or GCC based) targeting a custom processor ISA.

STAGE SEQUENCE:
  isa_analysis → backend_dev → assembler_dev → linker_config →
  runtime_libs → toolchain_validation → toolchain_signoff

LOOP-BACK RULES:
  - backend_dev: codegen errors            → backend_dev (max 5x)
  - assembler_dev: encoding error          → assembler_dev (max 3x)
  - linker_config: unresolved symbols      → linker_config (max 3x)
  - toolchain_validation: pass < 95%       → backend_dev (max 3x)
  - runtime_libs: crash/failure            → runtime_libs (max 3x)

Track test_results in state_object.test_results.
Output: Release-ready toolchain package with validation report.
```

> 固定 stage 名、状态值和机器接口保留英文，避免破坏自动化兼容性。

---

## 6. Toolchain Release Package Checklist

```markdown
## Toolchain Release Checklist
- [ ] Compiler（clang/gcc）binary：支持 custom ISA
- [ ] Assembler（llvm-as/gas）：能编码全部 ISA instruction
- [ ] Linker（lld/ld）：memory map 对应 linker script 正确
- [ ] Runtime library：libgcc/compiler-rt、newlib、libm
- [ ] Binutils：objdump、readelf、nm、objcopy
- [ ] GDB / LLDB：支持目标架构
- [ ] ISS：用于离线测试
- [ ] 文档：ABI spec、getting-started guide
- [ ] Validation report：regression pass rate
- [ ] Known issue：含 workaround
```
