# RTL Design Domain Knowledge（RTL 设计领域知识）

## Known Failure Patterns

- **Verilator -Wall 捕获 implicit wire**：`-Wall` 能发现 SpyGlass/DC 可能静默接受的 implicit wire。建议先跑 Verilator lint，提前暴露会影响正确综合的问题。
- **Multi-bit CDC violation**：多 bit signal 跨 clock domain 不能只用 2-FF synchronizer，还要采用 Gray encoding / handshake / async FIFO 等一致性机制；否则 intermediate state 会产生间歇性功能错误。
- **Async reset flop 需要 reset-removal SDC**：异步 reset deassertion 需要明确 removal timing constraint，例如 reset deassertion 到首级 flop clock edge 的 `set_max_delay -datapath_only`。缺失会造成假 violation 或漏检 metastability window。
- **include 路径上的陈旧生成头文件看似 RTL 缺陷：** 搜索使用首个匹配。寄存器映射/IP 配置同时含两代输出且旧版在前时，同次会出现重复声明 fatal（旧头文件仍声明 RTL 已声明项）与未声明标识符 fatal（新版本才有字段）。改 RTL 前先检查解析后的 filelist，通常只改一行列表，“重复”端口其实真实存在。
- **中止的 lint 不能说明 RTL 有误：** 工具报告规则检查中止/未完成意味着规则未执行（执行零条规则）。配置失败不得回退 RTL 编辑，以 input_setup 升级。修复输入后真实发现首次出现，原先是被中止遮蔽，并非修复引入。
- **用户覆盖配置目录可能绕过受管理项目文件：** 部分厂商 Wrapper 优先使用覆盖目录，陈旧覆盖会静默替代项目文件及其全部变量。信任结果前打印工具实际读取项目文件的绝对路径。
- **sv2v 无法降低的合法 SystemVerilog 会在仿真通过后破坏综合：** 函数结果部分选择 `strb_expand(pstrb)[N-1:0]` 通过 Verilator、slang、仿真，但 sv2v 原样输出，yosys 报 `syntax error, unexpected '['`。先把函数返回值赋给命名信号，再选择。只有解析转换后文件才能发现，即 lint_check 的前端检查。
- **某源列表缺少模块会静默黑盒化：** 仿真、lint、综合、PD、形式验证常使用不同列表/Makefile 变量。一个项目新增外设需改七列表，漏 PD 时 sv2v 无错误黑盒，而仿真仍通过。新增模块后运行 `check_design_inputs.py --rtl-dir <rtl> --list <name>=<file> ...`；未知自有模块绝不能记为 stub。
## Successful Tool Flags

- `verilator --lint-only -Wall -Wno-DECLFILENAME <files>`：抑制文件名与模块名不匹配的常见误报，保留其他 Wall 检查。
- `slang -Weverything --ignore-unknown-modules --allow-use-before-declare --strict-driver-checking <files>`：完整 elaboration；严格驱动检查可发现 Verilator 漏掉的多驱动。禁止 lint-only，它跳过 elaboration 并静默漏锁存器、多驱动；Wall 是 Verilator/Icarus 选项，slang 应用 Weverything。
- `sv2v --top <module> <files> > out.v && yosys -q -p 'read_verilog out.v; hierarchy -check -top <module>'`：下游读取 sv2v 输出时必须执行此前端检查，发现 SV 合法但 Verilog-2005 非法的结构。使用流程实际消费工具解析，不能换成 iverilog。
## PDK / Tool Quirks

- **SpyGlass CDC 与 JasperGold CDC：** SpyGlass 对 Gray 编码总线误报更多；JasperGold 误报较少但漏掉部分结构模式。先 SpyGlass 获得完整覆盖，再附理由豁免误报。
- **sky130 的 Yosys synth_check：** 复杂参数覆盖的原生 SV 支持不完整，`yosys -p "synth -top <top>; check"` 需 SV 前端。用下游 PD 相同前端：下游基于 sv2v 时检查 sv2v 输出，不能用接受实际 sv2v→yosys 路径拒绝结构的 Surelog，避免 synth_check 通过却 PD 失败。
## Notes

- RTL sign-off package 的 `filelist.f` 必须用 relative path。Absolute path 会破坏从不同 working directory 运行的 downstream synthesis flow。
