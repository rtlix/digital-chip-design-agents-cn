# Synthesis Domain Knowledge（综合领域知识）

## Known Failure Patterns

- **sky130 hierarchy 使用 Yosys -flatten**：层次化 design 对 sky130 综合时，`synth -flatten` 往往能避免 hierarchy boundary 阻止 technology optimization；不 flatten 可能带来约 15–20% area overhead。
- **Genus 只 set_max_area 不能关闭 WNS**：必须先正确设置 `create_clock/set_input_delay/set_output_delay`，再做 area optimization；否则 WNS 仍会违反。
- **compile_ultra 前声明 scan false path**：scan chain false path 应在 compile 前写入 SDC，例如 `set_false_path -from [get_ports scan_in] -to [get_ports scan_out]`。后补可能让工具重新优化 scan path，破坏 chain continuity 并迫使 LEC 重跑。

## Successful Tool Flags

- `yosys -p "synth -top <top> -flatten; dfflibmap -liberty <lib.lib>; abc -liberty <lib.lib> -D <period_ps>"`：sky130 常用完整 Yosys synthesis；`-D` 设置 ABC timing target。
- `dc_shell -f <script.tcl> -output_log_file <log>`：始终保留 log；`check_design` unresolved-reference warning 是综合失败的常见根因。
- `genus -legacy_ui -files <script.tcl>`：scripted flow 下 legacy UI 往往更稳定，避免 batch job 被交互 prompt 卡住。

## PDK / Tool Quirks

- **`compile_ultra` 超过 2 次 loop-back 收益很小**：继续 ultra effort 往往只改善 <1%，却增加 3–5× runtime。两次失败后应转 targeted path optimization。
- **ABC Liberty compatibility**：ABC 对带 `pg_pin` 的 liberty support 有限制。给 Yosys/ABC 前可按 flow 要求清理相关 block，例如 `sed '/pg_pin/,/^  }/d'`；否则可能静默忽略 cell。

## Notes

- 每次 netlist change 后都应运行 LEC，而不是只在 sign-off。未验证 netlist 进入 PD 后再暴露 LEC fail，会造成完整 PD 重跑。


## Commercial Flow Measured Notes
- **DC-NXT NDM topographical**：NDM flow 使用 `dcnxt_shell -topographical_mode`。传统 `dc_shell -topographical_mode` 属于 Milkyway flow，不能假设具备相同 NDM 命令。
- **SVF**：在 DC 中 `set_svf <file>` 应位于 `analyze` 前，供 Formality 解释 constant/merge 优化。
- **tt-only ripple adder risk**：仅 tt + aggressive area recovery 曾形成 ripple-carry adder，zero-wire PrimeTime 在 ss 角约 -10.5 ns；用 MCMM ss/tt setup + ff/tt hold 重新综合并 `set_fix_hold`。
- **Genus physical-aware**：`read_mmmc` + `read_physical -lef` + `syn_generic -physical` + `syn_map -physical` + `syn_opt`。缺 qrcTechFile 时 `syn_opt -spatial` 可报 PHYS-1015。
- **Command ownership**：`compile_ultra` 属于 Design Compiler；Genus 使用 `syn_*`；Fusion Compiler 使用 `compile_fusion`。
