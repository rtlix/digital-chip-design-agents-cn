# Synthesis Domain Knowledge（综合领域知识）

## Known Failure Patterns

- **Sky130 hierarchical design 使用 Yosys flatten**：`synth -top <top> -flatten` 能避免 hierarchy boundary 阻止 technology optimization。
- **只给 area target 不会关闭 WNS**：先正确应用 clock/I/O timing constraint，再做 area recovery。Design Compiler 使用 `compile_ultra`，Genus 使用 `syn_generic/syn_map/syn_opt`，Fusion Compiler 使用 `compile_fusion`。
- **Scan false path 必须在 compile 前声明**，否则综合会优化 scan path 并导致 LEC/chain 问题。
- **DC-NXT X-2025.06-SP3 TT-only + area recovery 会生成慢 adder**：实测 ripple-carry adder TT 达 0 slack，但 SS zero-wire 为 -10.5 ns。用 MCMM（SS+TT setup、FF+TT hold、per-scenario TLU+、hold scenario `set_fix_hold`）重综合后恢复 margin。
- **Genus iSpatial 缺 QRC tech**：`syn_opt -spatial` 无 qrcTechFile 时以 PHYS-1015 失败；使用 plain physical-aware `syn_opt` 并记录。Genus 对 `set_max_area 0` 的行为与 DC 不同。

## Successful Tool Flags

- Yosys：`yosys -p "synth -top <top> -flatten; dfflibmap -liberty <lib.lib>; abc -liberty <lib.lib> -D <period_ps>"`。
- 普通 DC wire-load/Milkyway run 可用 `dc_shell -f <script.tcl>`。
- **NDM topographical synthesis** 使用 `dcnxt_shell -topographical_mode -f <script.tcl>`；plain `dc_shell -topographical_mode` 是 Milkyway flow。
- Formality 所需 SVF：`set_svf <file>` before `analyze`，最后 `set_svf -off`。
- TLU+：`set_tlu_plus_files -max_tluplus ... -min_tluplus ... -tech2itf_map ...` + `check_tlu_plus_files`；`read_parasitic_tech` does not exist in `dcnxt_shell`。
- Genus：`genus -no_gui -overwrite -f <script.tcl>`，`read_mmmc`、`read_physical -lef`、`syn_generic -physical`、`syn_map -physical`、`syn_opt`。

## PDK / Tool Quirks

- DC 的 `compile_ultra` 连续 >2 次 loop-back 收益通常很小，应转 targeted optimization。
- ABC 对含复杂 `pg_pin` 的 Liberty 有兼容性限制，给 Yosys/ABC 前按 flow 要求清理。
- Genus/Innovus MMMC dialect 不完全一致：Genus 23.14 需要 `create_timing_condition` + `-timing_condition`；Innovus 可能以 TCLCMD-992 拒绝。
- `set_dont_use */<cell>` 在 DC/ICC2 可能报 UID-109；使用 `set_dont_use [get_lib_cells */<cell>]`。Genus 使用 `set_db ... .dont_use true`。

## Notes

- 每次 netlist change 后都跑 LEC。
- _Last distilled: 2026-11-07 from measured commercial synthesis comparison runs._
