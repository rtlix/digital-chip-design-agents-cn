# Verification Domain Knowledge（验证领域知识）

## Known Failure Patterns

- **UVM factory override → uvm_tb_build fail**：常见症状是仿真启动时 `uvm_fatal` 提示期待 X 却得到 Y。根因通常是 override 在 `run_test()` 后注册，或 type name 字符串大小写不一致。应在 `build_phase` 且 `super.build_phase()` 前完成注册。
- **Constrained-random coverage closure 卡住**：很多 uncovered corner 本身需要 >3 个事件特定顺序，随机很难命中。继续加随机 seed 前先分析 bin；如果需要明确 sequence，应写 directed test。
- **Assertion coverage 补充 functional coverage**：通过 `$rose/$fell`、SVA cover 捕获协议行为，可补充 functional coverage。把 SVA cover point 接入 coverage database，避免重复计算。

## Successful Tool Flags

- `verilator --coverage --coverage-line --coverage-toggle -Wno-UNOPTFLAT`：开启 line/toggle/user coverage，并屏蔽 UVM dynamic connection 的预期 UNOPTFLAT。
- `vcs -sverilog +vcs+lic+wait +UVM_NO_RELNOTES -cm line+cond+fsm+tgl`：`+vcs+lic+wait` 可减少 batch regression license timeout，`-cm` 开启覆盖率。
- `xrun -uvm -coverage all -covworkdir <dir>`：多 run merge 时 `-covworkdir` 必须一致。

## PDK / Tool Quirks

- **Verilator UVM library**：开源 `uvm-core` 可在 Verilator 编译，但不是所有 phasing feature 都完整支持；例如基于 timeout 的 `uvm_objection` drain time，建议使用显式 event-based drain。
- **cocotb + Verilator coverage**：cocotb 不原生输出 UCDB。可用 `verilator_coverage --write-info <info> <dat>` 转换，再生成报告。

## Notes

- `open_p0_bugs:0` 是 hard sign-off gate。任何 P0/P1 bug 未关闭都不能进入 `regression_signoff`，否则之后修 bug 还要完整重跑 regression。
