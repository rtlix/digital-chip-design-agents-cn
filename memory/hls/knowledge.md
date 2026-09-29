# HLS Domain Knowledge（HLS 领域知识）

## Known Failure Patterns

- **Memory-bound loop 的 PIPELINE II=1 失败**：Vitis HLS 对 memory-bound loop 使用 `PIPELINE II=1` 常因 array access resource conflict 失败。可用 `#pragma HLS ARRAY_PARTITION variable=<arr> cyclic factor=<N>`，或在重构 access pattern 前暂用 `PIPELINE II=2`。
- **DATAFLOW 要求 producer/consumer channel**：`#pragma HLS DATAFLOW` 要求 task 间用 stream 或 ping-pong buffer。用普通 array 直接连接时，HLS 可能静默忽略 pragma；必须用 dataflow viewer 验证。
- **Latency miss**：通常通过 loop unroll 或 array partition 解决，而不是单纯提 clock。优先尝试 array partition，area overhead 常低于 full unroll。

## Successful Tool Flags

- `vitis_hls -f <script.tcl>` + `config_compile -pipeline_loops 0`：关闭自动 loop pipelining，适合希望完全手工控制 `PIPELINE` directive 的场景。
- `bambu --target-file=<xml> --top-fname=<func> --simulate`：建议始终带 `--simulate`，在 RTL QC 前先捕获 HLS-level output mismatch。
- `circt-opt --lower-calyx-to-fsm`：用于查看 Calyx IR 生成的 FSM 结构。

## PDK / Tool Quirks

- **Catapult reset inference**：Catapult 可从 C++ variable initialization 推断 reset。仿真中碰巧为 0 的未初始化变量，在 RTL 中可能没有 reset logic；对依赖 reset 的变量显式初始化。
- **Bambu vs Vitis floating point**：Bambu 原生生成 IEEE-754 compliant FP unit；Vitis HLS FP 使用 Xilinx FP IP，对 NaN/infinity 行为可能不同。若 FP edge case 重要，Bambu 更便于 portability。

## Notes

- Co-simulation output mismatch 永远是 blocker。Retry 前先做 root-cause，不能假设它只是 simulation artifact。
