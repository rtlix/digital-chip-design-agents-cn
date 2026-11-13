# Formal Verification Domain Knowledge（形式验证领域知识）

## Known Failure Patterns

- **Over-constrained environment 导致 vacuous proof**：assumption 让合法 input space 不可达时，property 会“空洞通过”。每次 environment 变化后都做独立 vacuity/reachability 检查。
- **Bound depth 不足**：SymbiYosys 的 bound/multiclock 属于 `.sby` 配置的 `[options]`，不是随意拼到 `sby` 命令行上的 flag。Bound 太浅只能算 bounded result，不能写 PROVEN。
- **Synthesis 后 LEC fail**：clock gating、constant propagation、register merge/retiming 都需要正确 mapping；DC→Formality 流程尤其依赖 **SVF**。
- **Mutant anchor 失效**：flat/post-route netlist 的 literal instance/net name 会因优化、resize、route 改变。Negative-control mutator 应按结构和 cell family 找 **anchor**，找不到时 fail loudly。

## Successful Tool Flags / Setup

- SymbiYosys：把 `depth`、`multiclock on` 写入 `.sby` 的 `[options]`；vacuity 通过 cover/reachability/assumption-disable 方法验证，而不是依赖不存在的 CLI shortcut。
- Formality：DC compile 前保存 SVF；Formality 读取 reference/implementation library 与 netlist 后执行 match/verify，并对 deliberately mutated netlist 做 negative control。
- Conformal：需要高级 mapping flow 时使用对应许可（实测流程为 `lec -nogui -xl -dofile <lec.do>`）；guided compare 之外再做 direct compare。

## PDK / Tool Quirks

- **Z3 vs Boolector**：算术较重的 bit-vector problem 可尝试 Z3；偏 Boolean 的问题 Boolector 往往更合适。长时间 inconclusive 时应记录 solver/bound 后切换，而不是把 timeout 当 PASS。
- **Post-route diode blackbox**：antenna/protection diode 可能产生 implementation-only unmatched point。保留原 compare，同时在副本中剥离这些 functionless diode，要求核心逻辑 0 unmatched。

## Notes

- P0 property 出现 CEX 是 hard blocker。
- LEC 的 EQUIVALENT 只有在同一 setup 能抓到 structural mutant 时才可信。
- _Measured commercial notes: Formality X-2025.06 / Conformal LEC 24.10-p100._
