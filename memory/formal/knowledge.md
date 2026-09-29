# Formal Verification Domain Knowledge（形式验证领域知识）

## Known Failure Patterns

- **Over-constrained environment 导致 vacuous proof**：`environment_setup` 的 `assume` 让 input space 不可达时会出现 vacuous proof。每次 environment iteration 后运行 vacuity check（`sby --vacuity`）。发现 vacuity 时一次只放宽一个 constraint，不要全部删除后重建，以免丢失上下文。
- **Bound depth 不足**：SymbiYosys `--depth` 至少应为 `pipeline_depth + 2`，才能覆盖全部 pipeline stage。Bound 太浅可能让只在 pipeline 尾部触发的 property 出现假 “PASS”。
- **Synthesis 后 LEC fail**：常见原因是 clock-gating cell 缺 equivalence mapping（`set_dont_touch` 或显式 mapping script）。运行 LEC 前把 synthesis tool 的 clock-gating cell list 提供给 LEC tool。

## Successful Tool Flags

- `sby -f <task>.sby --depth <N>`：始终显式设置 `--depth`，不要依赖默认 bound。
- `sby --multiclock`：多 clock domain 必需；single-clock mode 可能静默忽略跨域路径。
- `jg -allow_empty_cex`：防止 JasperGold 把空 CEX set 误当 vacuity proof；同时配合显式 vacuity check。

## PDK / Tool Quirks

- **Z3 vs Boolector**：重 arithmetic 的 bitvector 设计 Z3 通常更快；纯 Boolean problem Boolector 常更好。Proof 超过 30 分钟无结果时可切换 solver。
- **Yosys `prep` before sby**：先运行 `yosys -p "prep -top <top>"` 可提前捕获 elaboration error，并显著减少 formal setup time。

## Notes

- P0 property 出现 CEX 是 hard blocker。暂停 formal flow，携带完整 counterexample trace 交给 RTL team；确认 RTL fix 前不要继续重试。
