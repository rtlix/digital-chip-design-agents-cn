# Physical Design Domain Knowledge（物理设计领域知识）

## Known Failure Patterns

- **ORFS density >65% 与 routing congestion 强相关**：先降到约 60–65%，不要盲推到 70% 以上。
- **Sky130 500 MHz CTS skew**：过紧的 <30 ps target 往往不可达；50 ps 是常见起点。
- **Post-route ECO 2–3 轮仍不收敛**：应回到 floorplan/placement，而不是无限 incremental ECO。
- **Sky130 LVS tie-off**：常见缺 nwell/substrate tie，必须按 PDK pitch 插入正确 tie cell。
- **ICC2 li1 ban 可能是 soft**：仅 `set_ignored_layers -min_routing_layer met1` 不足，检查 `global_min_layer_mode`，需要时设 hard。
- **ICC2 met4 signal-to-wide-PG spacing**：routing/check_routes 可能漏掉 fat-table 约束，KLayout `m4.5ab` 会发现；对 >3 um strap 周围可增加 0.1 um met4 blockage。
- **TT-only hold repair** 会生成弱 ZBUF/ZINV chain 并带来 transition 问题；用 FF+TT hold scenario，并通过 `set_lib_cell_purpose -include hold` 限定 hold cell。
- **Innovus view 丢 I/O latency**：每 analysis view 配 `-latency_file`，`update_constraint_mode` 后复核。
- **Innovus 某些 primitive 静默失败**：`create_inst` 无实例时用 `addInst -physical`；`create_shape` 不存在、`editAddRoute` 无效时用 `add_shape`；diode ECO 后 `refinePlace` 再 `ecoRoute`。
- **Commercial antenna check 可能偏宽松**：Sky130 上可用 OpenROAD `check_antennas` 列表驱动 diode ECO，再由最终 sign-off deck 复核。

## Successful Tool Flags

- ORFS：`make DESIGN_CONFIG=... finish` 后再读 metrics。
- KLayout batch DRC：`klayout -rd input=<gds> -r <drc_script.rb> -zz`。
- OpenROAD one-shot timing：`openroad -no_init` + read_lef/read_def/report_checks。
- ICC2 library workspace：多 corner NDM 要 one pane per corner；`check_workspace -allow_missing` 后 commit。
- ICC2 Netgen/LVS export：名称规则使用 `-case_insensitive`，`write_verilog -exclude supply_statements`。
- Innovus hold：`setOptMode -holdTargetSlack 0.2`，与统一 PrimeTime/StarRC judge 对照。
- RedHawk 2025 R2.2：**`INSTANCE_POWER_FILES`** 必须是 plural；singular 可能被接受但忽略。EM 按 PDK 语义使用 AVG/RMS，PEAK 对 DC limit 不可直接当 pass/fail。

## PDK / Tool Quirks

- Sky130 antenna rule 较严，OpenROAD routing 后常需 repair。
- Global routing overflow=0 不等于 detailed DRC clean。
- **Sky130 commercial view**：lc_shell 可能在成功写库后 exit segfault；ICC2 NDM 需要由 tech LEF 派生 .tf；Innovus cap table 可能需要 layer rename。
- StarRC 与 OpenRCX correlation 依赖 coupling threshold、LEF obstruction 与 via-name map；输入不一致属于 setup 问题。
- Magic DRC 读取含真实 SRAM GDS 的 macro 可需要约 **11 GiB**，应独占运行；大量 finding 可能位于 hard-macro footprint 内，先按 footprint 分类。

## Notes

- Core utilization >85% 是 hard stop。
- _Last distilled: 2026-11-07 from measured commercial Sky130 comparison records._
