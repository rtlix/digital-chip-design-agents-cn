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
