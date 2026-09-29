# Architecture Domain Knowledge（架构领域知识）

## Known Failure Patterns（已知失败模式）

- **Spec 不完整 → risk_assessment 为 HIGH**：如果 `risk_assessment` 对 schedule 给出 HIGH，通常说明输入 spec 缺少 corner-case requirement。继续 `arch_exploration` 往往无法消除这种由规格不足导致的 schedule risk，应先要求澄清 spec。
- **McPAT area estimate**：没有 technology calibration 时误差可达 ±30%。最终 area budget 不应直接采用原始 McPAT 数值；应使用已知 tape-out 数据或设计者输入的 technology scaling factor。
- **gem5 OOO branch predictor**：Out-of-order gem5 model 通常需要调 branch predictor，才能把 IPC 控制在距 silicon 15% 内。默认 LTAGE 参数经常不适合 deeply embedded workload；报告 throughput 前先调 `BTBEntries`、`RASSize` 和 `numThreads`。

## Successful Tool Flags（有效工具参数）

- `gem5` 的 in-order model（`MinorCPU`）对 in-order pipeline 通常无需 branch-predictor tuning，就能把 silicon 偏差控制在约 15%。
- `mcpat --inorder` 对 in-order design 的 area estimate 通常比默认 out-of-order configuration 更准确。
- `cacti -cache_size <N> -block_size <B> -associativity <A>`：三个参数都应显式指定，避免 CACTI 使用与设计不匹配的默认值。

## PDK / Tool Quirks（PDK / 工具特性）

- **Platform Architect**：启动时需要 license server 可达。如果 `spec_analysis` 卡住，重试前检查 `LM_LICENSE_FILE` 并运行 `lmstat -a`。
- **VSP (Cadence)**：如果导入的 TLM model `.so` 与 VSP runtime 使用不同 GCC ABI，导入可能静默失败；应使用匹配 ABI 的 `--std=c++14` 与对应 `-fabi-version` 重新编译。

## Notes（备注）

- Microarchitecture 文档中使用 McPAT/CACTI estimate 时，应显式给出 uncertainty bound；不要把数值四舍五入成“漂亮数字”而忽略 model error。
