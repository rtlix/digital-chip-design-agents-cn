# Physical Design Domain Knowledge（物理设计领域知识）

## Known Failure Patterns

- **ORFS density >65% → routing congestion**：OpenROAD/ORFS placement density 超过 65% 经常与 routing-stage DRC violation 强相关。Retry 前把 floorplan target density 降到 60–65%；未做人工 congestion 分析前不要推到 70% 以上。
- **sky130 500 MHz CTS target skew**：建议 50 ps。<30 ps 的目标在 OpenROAD CTS 通常不可达，会导致 CTS 无限 loop。
- **Post-route timing closure ECO rounds**：通常需要 2–3 轮。3 轮后 WNS 仍不收敛，应升级到 floorplan revision；placement congestion 根因靠 incremental ECO 很难关闭。
- **LVS 失败来自 substrate tie-off**：sky130 常见是 n-well/substrate tie-off 缺失。确保 PDK standard-cell library 有 tie cell，并按规定 pitch 插入。

## Successful Tool Flags

- `make DESIGN_CONFIG=... finish`（ORFS）：读 `reports/.../metrics.json` 前先让 full flow 完成，partial run 可能留下 stale metrics。
- `klayout -rd input=<gds> -r <drc_script.rb> -zz`：batch DRC；`-zz` 关闭 GUI，适合 CI。
- `openroad -no_init` + `read_lef/read_def/report_checks`：可对 routed design 做一次性 timing query，无需重新加载完整 ORFS database。

## PDK / Tool Quirks

- **sky130 antenna rule 较严**：routing 后开启 OpenROAD `repair_antennas`；典型设计可能有 5–15% net 需要 repair。
- **Global routing clean ≠ detailed routing clean**：global overflow 为 0 不能代表 detailed DRC clean；必须跑 `detailed_route` 并看 metrics 的 `drc_count`。

## Notes

- Sign-off 时 `core_area_util_pct >85%` 属于 hard stop；sky130 + OpenROAD 在该密度以上 routing/ECO closure 会非常困难。
