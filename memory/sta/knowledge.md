# STA Domain Knowledge（STA 领域知识）

## Known Failure Patterns

- **OpenSTA hold 必须 set_propagated_clock**：否则 ideal zero-skew 会产生假 clean hold。
- **Multi-corner hold closure**：Sky130 常需 50–100 ps hold margin，具体以项目/library 为准。
- **ECO cell >2%**：通常说明 floorplan/CTS 上游问题，应升级而不是继续堆 ECO。
- **先进节点 hold 对 RCX 精度敏感**：不要用粗略 estimator 做 sign-off。
- **PrimeTime X-2025.06 的 `read_sdc`**：遇到首个 unsupported command 后会停止读取后续 constraint，但 session 不一定失败。Innovus-exported SDC 曾因此产生看似合理但无效的 slack；修语法、diff 派生版，并要求 setup/hold WNS 都非空。
- **Tool-written SDC 是不同实验**：ICC2 可能加入 I/O `set_clock_latency`，Innovus latency 分散在 per-view `latency.sdc`；跨 flow 排名必须使用同一 shared SDC，并记录每个 SDC **md5**。
- TT-only implementation 拿到 SS/FF judge 会暴露巨大的结构 margin 差异，不能用这种比较评判工具优劣。

## Successful Tool Flags

- `sta -exit <script.tcl>`。
- `report_timing -path_type full_clock_expanded -delay_type max -nworst 10`。
- `report_slack_histogram -num_bins 20`。
- PrimeTime judge：每 (library corner, RC corner) 独立 `pt_shell`，`read_parasitics -format spef`，SDC/SPEF/netlist md5，随后 `report_annotated_parasitics` annotation gate。
- `set_app_var report_default_significant_digits 4`，避免很小负 slack 被默认精度隐藏。
- PrimePower 做公平比较时统一 vectorless activity；必要时对 `[all_registers -output_pins]` 显式设置 switching activity。

## PDK / Tool Quirks

- PrimeTime POCV 需要 PDK coefficient；有 POCV 时通常比 AOCV 更准确。
- Tempus MMMC 每个 mode/corner 都需完整 constraint_mode + delay_corner，缺组合会造成假 all-clear。

## Notes

- 全 corner setup/hold WNS/TNS 同时达标才可 sign-off。
- _Last distilled: 2026-11-07 from measured PrimeTime/PrimePower judge runs._
