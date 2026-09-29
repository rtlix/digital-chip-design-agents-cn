# STA Domain Knowledge（STA 领域知识）

## Known Failure Patterns

- **OpenSTA hold analysis 缺 `set_propagated_clock`**：hold check 前必须 `set_propagated_clock [all_clocks]`。否则使用 ideal clock（zero skew），可能得到假 “clean hold”，silicon 才失败。
- **Multi-corner hold closure 的 hold margin**：sky130 在 slow-slow + RCMAX 下通常需要 target liberty hold margin；0 ps 往往不够，建议根据项目加 50–100 ps margin。
- **ECO cell >2% → 上游问题**：`eco_guidance` 中 ECO cell 超过总 cell 2% 往往是 floorplan/CTS 根因，不是 exception 问题；应升级给 PD。
- **28nm 及以下 hold 对 RCX 精度敏感**：OpenROAD `estimate_parasitics` 不足以做严谨 hold sign-off，应使用 Calibre xRC、StarRC 或 calibrated OpenRCX 生成 SPEF。

## Successful Tool Flags

- `sta -exit <script.tcl>`：保证 OpenSTA clean exit 并返回 code，适合 CI。
- `report_timing -path_type full_clock_expanded -delay_type max -nworst 10`：完整显示 clock network，便于分析 skew 对 WNS 的贡献。
- `report_slack_histogram -num_bins 20`：在 detailed path analysis 前快速判断 violation 是广泛还是集中。

## PDK / Tool Quirks

- **PrimeTime POCV vs AOCV**：先进节点有 POCV coefficient 时，POCV 通常比 AOCV 更准确、更少 pessimism。
- **Tempus MMMC**：每个 mode/corner 组合都需要 `constraint_mode` 与 `delay_corner`；缺组合可能出现错误的“all clear”。

## Notes

- STA sign-off 要求所有 corner 同时满足 setup WNS/TNS 与 hold WNS/TNS 目标；任一 corner fail 都阻止 tape-out。
