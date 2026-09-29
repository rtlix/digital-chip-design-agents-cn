# SoC Integration Domain Knowledge（SoC 集成领域知识）

## Known Failure Patterns

- **AXI4 memory-map conflict → chip_level_sim failure**：这是最常见的 SoC 集成问题。进入 `top_integration` 前汇总全部 IP address range，确认无 overlap。FuseSoC 可用 `fusesoc gen --target sim <core>` 辅助验证。
- **FuseSoC IP version pinning**：未 pin 版本时，registry 中新增不兼容版本可能导致 dependency resolution 静默变化。在 `<design>.core` 中使用 `=` 精确 pin，不要用 `^` compatible range。
- **Bus fabric address decoder**：lint 无法发现 decoder 边界错误。在 `top_integration` 前用 directed simulation 遍历 base、base+1、top-1、top。

## Successful Tool Flags

- `fusesoc --cores-root <path> run --target sim <core>`：integration 阶段指向本地 IP copy。
- `verilator --sc --exe --build -Wno-UNOPTFLAT <files>`：`--sc` 生成 SystemC output；`-Wno-UNOPTFLAT` 抑制 AXI combinational-loop 类预期 warning。
- `edalize build --tool <tool>`：优先于手写 Makefile，提高 simulator portability。

## PDK / Tool Quirks

- **Verilator AXI4 burst**：Verilator 本身不等于 protocol VIP；需要 cocotb/VIP 做 protocol-level interleaving/compliance 验证。单用 Verilator 更适合 functional correctness。
- **FuseSoC VLNV**：Vendor:Library:Name:Version 必须全 registry 唯一；重复 VLNV 会静默使用第一个匹配项，可能拿错版本。

## Notes

- `unqualified_ips:0` 是 hard sign-off gate。不要带未 qualification IP 进入 synthesis，否则后续发现问题会迫使整套 integration 重跑。
