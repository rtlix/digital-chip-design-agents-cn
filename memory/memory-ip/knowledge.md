# Memory IP Design Domain Knowledge（Memory IP 设计领域知识）

## Known Failure Patterns

- **`.lib/.lef/.v` pin-name drift**：compiler-generated view 在 wrapper 手工修改后可能出现 `CLK` vs `clk`、`WEN` vs `WEB` 等差异，生成时不报错，直到 PD unconnected port 或 LEC mismatch 才暴露。宣告 `view_generation` clean 前必须 diff 三类 view 的 pin list。
- **按 typical corner 选 macro**：typical access-time 通过并不代表 slow corner 有 margin，sense-amp path 在 slow corner 退化更明显，是晚期 STA loop-back 的常见根因。Macro selection 必须基于 slow-corner margin。
- **过于宽松的 behavioural model 掩盖 collision bug**：真实 macro 在 write-during-read collision 返回 X，而 `.v` model 返回 old data 时，testbench 会假通过、silicon 才失败。Model 必须对 macro 未定义的 collision 情况准确传播 X。
- **把 ECC 当作 redundancy 替代**：ECC 修 soft error，redundancy 修制造 hard defect。把 ECC 算入 post-repair yield 会高估良率，应完全分开计算。

## Successful Tool Flags

- `cacti -infile cache.cfg` 配合 `-cache_size/-block_size/-associativity`：在 `memory_requirements` 做第一轮 area/power estimate；结果应视为 uncertainty band，不是精确点值。
- `sta -exit lib_check.tcl` + 每 corner `read_liberty <macro>.lib`：比等完整 STA 更快发现 missing timing arc 或 malformed Liberty。
- `klayout -b -r gds_qa.py -rd gds=<macro>.gds`：批量 GDS boundary/obstruction QA。
- `magic -dnull -noconsole -rcfile <pdk>.magicrc` + `drc check` / `extract`：OpenRAM layout 的 macro-level DRC/LVS；vendor pre-hardened macro 可跳过。

## PDK / Tool Quirks

- **OpenRAM vs vendor compiler**：OpenRAM 能生成完整 view set，但支持的 mux/port configuration 较窄。把 configuration 纳入候选前先确认可生成，避免浪费 selection round。
- **sky130 pre-hardened SRAM**：只有固定 depth/width，需求介于可选 size 之间时必须 round up；在 `macro_selection` 显式记录 area over-provisioning。

## Notes

- 每个 losing macro candidate 都要记录 rejection rationale，re-spin 时这是最有价值的历史。
- Repair-register width 是 DFT `bist_insertion` 的硬 handoff；DFT 建好 BISR chain 后再改 spare count 会强制 DFT loop-back，应在 `redundancy_repair` 冻结。
