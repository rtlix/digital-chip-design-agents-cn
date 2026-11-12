# Formal Verification Domain Knowledge（形式验证领域知识）

## Known Failure Patterns

- **Over-constrained environment 导致 vacuous proof**：不要使用不存在的 `sby --vacuity`。应给 assertion antecedent 增加 cover property，并在 SymbiYosys 的 `mode cover` task 中检查可达性；发现 vacuity 时一次只放宽一个 constraint。
- **Bound depth 不足**：SymbiYosys 的 `depth N` 是 `.sby` 文件 `[options]` 下的选项，不是命令行 flag；至少设为 `pipeline_depth + 2`。
- **Synthesis 后 LEC fail**：常见原因是 clock-gating cell equivalence mapping 缺失；运行 LEC 前提供 synthesis tool 的 clock-gating cell list。

## Successful Tool Flags

- `sby -f <task>.sby`，并在 `.sby [options]` 显式设置 `depth <N>`。
- 多 clock design 在 `.sby [options]` 使用 `multiclock on`，不是 `--multiclock`。
- 早期曾建议 `jg -allow_empty_cex`，现已删除：JasperGold 2024.12 的 console/help 中不存在该 option。Vacuity 用 cover property 检查。

## PDK / Tool Quirks

- **Z3 vs Boolector**：重 bitvector arithmetic 的设计 Z3 常更快；纯 Boolean 问题 Boolector 可能更好。
- **Yosys prep before sby**：先 `yosys -p "prep -top <top>"` 可提前发现 elaboration error。

## LEC (Formality / Conformal)

- Formality 的 `Verification SUCCEEDED` 或 Conformal 的 all-Equivalent 只有在同一脚本能把 deliberate mutant 判为 non-equivalent 后才可信。
- Formality 的 INCONCLUSIVE、Conformal 的 Abort 都是未证明，不是 equivalent。
- **Formality X-2025.06 on a DC netlist needs DC's SVF**：`set_svf` 必须在读取设计前设置。缺 SVF 时实测有 **143 reference registers** unmatched；reference 先 `set_top r:`，再读 implementation `.db`，否则可出现 FM-236。
- **Conformal 24.10-p100 + Genus `write_do_lec`** 需要 `lec -xl`（`analyze_extended_mapping` 属于 Conformal_Ultra），并要求 `LEC_VERSION` 环境变量、第一行 `tclmode`、退出前切 `vpxmode`。
- **Mutant anchor 必须基于结构而不是 literal name**：flat/post-route netlist 会 rename/resize，例如 `a211o_1` → `a211o_2`。按 cell family/net role/pattern 找 anchor，找不到就 fail；这类 anchor 规则已跨多次记录确认。
- Antenna/port diode 在两种工具里都可能成为无功能 black box；并行运行 diode-stripped copy，并要求 stripped copy unmatched=0。

## Notes

- P0 property 出现 CEX 是 hard blocker；携带完整 trace 交给 RTL flow。
- _Last distilled: 2026-11-07 from measured Formality/Conformal LEC records; every EQUIVALENT verdict had negative controls caught._
