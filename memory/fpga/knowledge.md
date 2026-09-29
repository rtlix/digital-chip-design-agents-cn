# FPGA Domain Knowledge（FPGA 领域知识）

## Known Failure Patterns

- **BRAM inference coding style**：Xilinx BRAM inference 要求 synchronous read，read-data output 注册；reset 不应直接施加在输出寄存器上。Asynchronous BRAM read 往往推成 LUT RAM，显著增加 LUT。
- **Carry-chain 阻止 DSP48 inference**：乘加树中混合 add/sub 与中间 carry-chain 会阻止 DSP48 inference。重构为完整 multiply-accumulate 落在一个 DSP48 内，可用 `(* use_dsp = "yes" *)` 强制推断。
- **Prototype frequency target**：通常把 FPGA prototype target 设为 ASIC target 的约 1/3，以补偿 fabric overhead。例如 1 GHz ASIC 可先按约 333 MHz FPGA target 规划，并在 sign-off report 显式写 scale factor。

## Successful Tool Flags

- `vivado -mode batch -source <script.tcl>`：用于可复现 batch synthesis/P&R；用 `set_property STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY none [get_runs synth_1]` 保留 debug hierarchy。
- `nextpnr-xilinx --freq <MHz>`：始终显式设置 target frequency，否则 unconstrained run 不会针对 timing 优化。
- `openFPGALoader --cable <cable> --verify`：program 后读回 bitstream，捕获 flash write failure。

## PDK / Tool Quirks

- **Vivado IP OOC synthesis**：top-level synthesis 前必须完成 IP out-of-context synthesis，否则可能静默使用 stale netlist。先 `synth_ip [get_ips *]`，再 `launch_runs synth_1`。
- **nextpnr-xilinx chip database**：必须与精确 device part number 匹配；数据库不匹配会表现为类似 DRC 的 routing failure。

## Notes

- FPGA prototype 上所有 performance 数值都必须记录 prototype frequency，并注明 ASIC scale factor；只报告 FPGA MHz 而不写 scale factor 会误导。
