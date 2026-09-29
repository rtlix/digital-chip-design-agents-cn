# Compiler Domain Knowledge（编译器领域知识）

## Known Failure Patterns（已知失败模式）

- **LLVM backend register allocation error**：`backend_dev` 阶段的 register allocation error 往往说明 calling convention 配错。重试 codegen 前确认 `XXXCallingConv.td` 中的 `CallingConv::ID` 与 ABI spec 一致。
- **Custom extension 缺 MC layer**：RISC-V custom extension 必须先实现 `MC`（Machine Code）layer，codegen 才能生成正确 encoding。跳过 MC 可能产生静默编码错误，直到 ATPG 或 silicon validation 才暴露。
- **Miscompilation root cause**：通常来自 instruction-selection DAG pattern。使用 `llc -debug-only=isel` 导出 legalization 前后的 SelectionDAG，并与 known-good compiler（`riscv64-unknown-elf-gcc -O0`）编译的 reference C output 比较。

## Successful Tool Flags

- `clang -target riscv32-unknown-elf -march=rv32imXcustom`：通过 custom extension string 从 Clang 到 LLC 做端到端新 instruction pattern 验证。
- `llc -verify-machineinstrs`：每个 pass 后验证 MachineInstr，可提前捕获会静默产生错误代码的 malformed instruction。
- `llvm-mc --show-encoding`：在接入 codegen 前逐条确认 custom instruction binary encoding，尽早发现 TableGen pattern mismatch。

## PDK / Tool Quirks

- **QEMU peripheral emulation gap**：QEMU 可能不实现 custom CSR 或非标准 MMIO peripheral。Runtime test 在 QEMU 通过但 silicon 失败时，应优先确认 QEMU 是否真正实现该 peripheral，并使用 RTL sim 或 FPGA prototype 复核。
- **GCC ABI for RISC-V custom extension**：如果 extension 改变 calling convention，GCC 需要 custom multilib config；否则不同 `-march` object 混合链接时会发生 ABI conflict。

## Notes

- 完整 regression 必须分别使用 `-O0`、`-O1`、`-O2`；很多 miscompilation 只在 optimization level >0 时出现。
