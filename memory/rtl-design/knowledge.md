# RTL Design Domain Knowledge（RTL 设计领域知识）

## Known Failure Patterns

- **Verilator -Wall 捕获 implicit wire**：`-Wall` 能发现 SpyGlass/DC 可能静默接受的 implicit wire。建议先跑 Verilator lint，提前暴露会影响正确综合的问题。
- **Multi-bit CDC violation**：多 bit signal 跨 clock domain 不能只用 2-FF synchronizer，还要采用 Gray encoding / handshake / async FIFO 等一致性机制；否则 intermediate state 会产生间歇性功能错误。
- **Async reset flop 需要 reset-removal SDC**：异步 reset deassertion 需要明确 removal timing constraint，例如 reset deassertion 到首级 flop clock edge 的 `set_max_delay -datapath_only`。缺失会造成假 violation 或漏检 metastability window。

## Successful Tool Flags

- `verilator --lint-only -Wall -Wno-DECLFILENAME <files>`：只屏蔽 file/module name mismatch 这类常见 false positive，保留其他 `-Wall`。
- `slang --allow-use-before-declare --strict-driver-checking <files>`：`--strict-driver-checking` 可发现部分 Verilator 漏掉的 multi-driver。
- `sv2v --top <module> <files> > out.v && iverilog -Wall out.v`：用于发现不完整 SystemVerilog support 工具下的 elaboration issue。

## PDK / Tool Quirks

- **SpyGlass CDC vs JasperGold CDC**：SpyGlass 对 Gray bus false positive 更多，但 structural coverage 更全；建议先用 SpyGlass，再带理由 waive false positive。
- **Yosys synth_check with sky130**：复杂 parameter override 的 SystemVerilog elaboration 通常需要 Surelog；Yosys native SV support 不完整。

## Notes

- RTL sign-off package 的 `filelist.f` 必须用 relative path。Absolute path 会破坏从不同 working directory 运行的 downstream synthesis flow。
