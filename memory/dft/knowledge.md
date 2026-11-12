# DFT Domain Knowledge（DFT 领域知识）

## Known Failure Patterns

- **Clock-gating cell Scan DRC**：ICG 缺 test-enable/control 是常见原因；scan insertion 前确认 TE 进入 scan-enable network。
- **ATPG coverage <95%**：常见于 power domain 未供电或 unused input 未 tie-off；先审查这些结构问题。
- **BIST MISR alias**：自研 MISR 使用与 register width 对应的 primitive polynomial。

## Successful Tool Flags

- TetraMAX 可显式控制 chain length，避免过长 scan chain。
- Modus full-fault mode 可同时跟踪 SAF/TDF。
- Tessent batch 使用 `tessent -shell -dofile <script.do> -replace < /dev/null`，防 stale log 与 abort 后等 stdin。

## PDK / Tool Quirks

- OpenROAD DFT 更适合简单设计；SoC 级 hierarchy stitching 需更完整工具。
- Yosys flatten 可帮助 chain stitching，但大型设计 runtime 增长明显。
- **Tessent 2025.4**：旧 `add_scan_groups/add_scan_chains` 路径曾“clean exit 但插入 0 个 cell”；使用 Skill 中 context flow，并检查 inserted-cell count。
- **Tessent cell library**：Liberty 只给属性；cell 行为用 gate-primitive Verilog 经 **LibComp** 编译，维护明确的 `dft_cell_selection`，避免自动选到特殊 lpflow cell。
- **Tessent MemoryBIST**：fault-injection proof 关闭 `reduced_address_count`，否则 full-address fault 可能被漏掉；multi-port controller 可能每 logical port 单独跑一遍，cycle count 比较要统一口径。

## Notes

- JTAG boundary-scan 在 silicon 前用 BSDL checker 验证。
