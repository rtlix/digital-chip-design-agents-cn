# DFT 领域知识

## 已知失败模式

- **Clock gating cell 导致的 Scan DRC 错误**：最常见原因是时钟门控单元没有测试控制逻辑。应给所有 ICG cell 增加 test-enable（`TE`）端口，并在执行 `scan_insertion` 前确认这些端口已连接到 scan enable 网络。
- **ATPG 覆盖率低于 95%**：完成 full ATPG 后覆盖率仍低于 95%，通常由未上电的逻辑域或未使用输入缺少 tie-off 引起。重新执行 ATPG 前，应检查 power-domain 边界，并确保所有 unused input 都明确 tie-high 或 tie-low。
- **BIST MISR false-pass**：MISR polynomial 的选择会直接影响 false-pass（aliasing）概率。应使用阶数与 MISR 寄存器宽度相同的 primitive polynomial。TetraMAX/Modus 的默认 MISR polynomial 通常可直接使用；自定义实现必须单独验证。

## 已验证有效的工具参数

- `tmax -scan_chain_length <N>` —— 显式设置 chain length，可避免 TetraMAX 生成过长扫描链，从而恶化 test application time。
- `modus -coverage_model full_fault` —— 可在单次运行中同时跟踪 SAF 与 TDF coverage，避免流程后续再单独执行一次 TDF。
- `tessent -shell -dofile <script.do>` —— batch 模式可避免 GUI 开销；建议配合结构化 dofile，保证流程可重复。

## PDK / 工具特性

- **OpenROAD DFT**：`openroad -dft` 可用于简单设计的 scan insertion，但目前不支持跨 IP hierarchy 的 scan-chain stitching。SoC 级 scan 建议使用 Yosys DFT plugin 或商业 DFT 工具。
- **Yosys `synth -flatten` 的影响**：scan insertion 前 flatten 可以消除阻碍 chain stitching 的 hierarchy boundary，但大型设计的运行时间会明显增加。更推荐只在 scan boundary 层级选择性 flatten。

## 备注

- JTAG boundary-scan connectivity（`jtag_setup`）应在流片前使用 BSDL checker 验证。BSDL 语法错误会导致测试设备在来料/生产测试阶段拒绝识别器件。
