# RTL Design Domain Knowledge（RTL 设计领域知识）

## Known Failure Patterns

- **Verilator -Wall** 能抓 implicit wire；但必须使用 CI 实际版本，不能只信 README/comment。
- **Multi-bit CDC** 不能只靠 2-FF；需 Gray/handshake/async FIFO 等一致性协议。
- **Async reset** 需要正确 reset-removal/timing constraint。
- **Stale generated header**：include first-match-wins，旧树排前面会同时制造 duplicate declaration 与 undeclared identifier；先检查真实 filelist/path，别改正确 RTL。
- **Lint aborted 不代表 0 finding**：setup/elaboration abort 时规则没有跑，分类 `input_setup`。
- **User override config 可能绕过 managed project file**：先打印工具实际读取的 project/config 绝对路径。
- **Legal SystemVerilog 可能无法被 sv2v 降低**：例如 function-call result 的 part-select。真正 downstream 用 sv2v→Yosys 时必须 parse 转换后的文件。
- **新增 module 漏了某个工具 source list**：simulation/lint/synthesis/PD/formal 各有独立 list；用 `check_design_inputs.py` 检查。

## Successful Tool Flags

- `verilator --lint-only -Wall -Wno-DECLFILENAME ...`。
- Slang 使用完整 elaboration：`slang -Weverything --ignore-unknown-modules --allow-use-before-declare --strict-driver-checking ...`，不要加跳过 elaboration 的 `--lint-only`。
- Front-end gate：`sv2v ... > out.v && yosys -q -p 'read_verilog out.v; hierarchy -check -top <top>'`。

## PDK / Tool Quirks

- SpyGlass CDC 对 Gray bus false positive 更多，但 structural coverage 较全。
- Yosys native SV support 有限；front-end gate 必须使用 downstream 真正消费的转换路径。
- **SpyGlass X-2025.06**：大型 array 可能需要提高 `mthresh`；含 `string/real` parameter 的 module 可能被 black-box。Verdict 从实际 report 读取，不看 exit code。
- **SpyGlass CDC/RDC license**：goal 可能请求 `cdc_adv_checker`；server 有其他 CDC product feature 不代表该 rule feature 可用。若 crossing rule 全 skip，0 violation 是 vacuous。
- Cadence HAL 的 synth engine 可能等待 license；关闭某些 synthesis-based rule 时必须明确说明哪些 rule NOT RUN。

## Notes

- RTL sign-off filelist 使用 relative path。
