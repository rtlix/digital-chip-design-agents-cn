# Pipeline Orchestration — Domain Knowledge（流水线编排领域知识）

## Cross-Domain Loop Patterns（跨域循环模式）

### Common verification flap signatures
- **Address 计算 off-by-one**：AXI burst test 中常表现为 `wrap_addr` / `incr_addr` mismatch；通常只需修改 address-generation logic 的 2–5 行。
- **Reset-domain crossing 漏检**：RTL lint 通过，但 reset-active transaction 仿真失败；需要 synchronizer 或 reset qualification。
- **State-machine dead state**：directed test 进入不可恢复状态；通常要补 default branch 或 recovery transition。
- **Signed/unsigned boundary width mismatch**：表现为 sign-extension artifact；通常用显式 cast 修复。

### Iteration-cap heuristics
- 若 `cross_domain_iteration_count=2` 且还没有任何 `status=fixed`，`suspected_rtl` 位置很可能判断错。批准第 3 次 dispatch 前应重新检查 `waveform_path`。
- 新 fix_request 与之前 `status=fixed` 条目有相同 `summary` 时，说明修复没 hold；检查 simulation 前 RTL 文件是否真正提交/生效。
- 同一 session 达到 `cross_domain_iteration_count=3`，常见根因是 `suspected_rtl.module` 误诊；escalation 应建议重新分析 waveform。

### Escalation message templates

**达到 cap（3 iterations）**：
```
Pipeline loop exceeded 3 cross-domain iterations for fix_request <id>.
Bug summary: <summary>
Last RTL fix attempted: <rtl_response.diff_summary>
Waveform at: <waveform_path>

需要操作：请复查 waveform 并重新确认 root cause，
然后清空 pending_approval，将 cross_domain_iteration_count 重置为 0，
再调用 /chip-design-meta:pipeline-orchestration。
```

**RTL 未修复即 abandoned**：
```
RTL orchestrator terminated without closing fix_request <id> (status stayed claimed).
Bug summary: <summary>
可能原因：RTL coding 达到 max turns；设计过复杂，无法自动修复。

需要操作：手工修复 <suspected_rtl.file> 的 <line_range> 附近，
把 fix_request status 更新为 "fixed" 并填充 rtl_response，
然后重新调用 /chip-design-verification:functional-verification。
```

## RTL Fix-Request Idioms

- `failure_class=formal_cex` 时，CEX trace 往往能精确到 failing cycle；提醒 RTL Orchestrator 修改 RTL 前先在 simulation tool 中加载 trace。
- `coverage_gap` 不一定代表 RTL bug，可能是 testbench stimulus 不足；改 RTL 前先确认是否真的缺行为。
- 始终检查 `suspected_rtl.line_range`。如果是 `[0,0]`，说明位置未知，RTL Orchestrator 应先 replay lint+simulation 再修改代码。
