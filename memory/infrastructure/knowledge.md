# Infrastructure Domain Knowledge（基础设施领域知识）

Tracking **默认关闭**，仅当 `pipeline_config.track_infrastructure:true` 或 `--track-memory`
启用。`experiences.jsonl` 按环境（`host/os/arch`）分 key。读取本文件时优先使用与当前
host 匹配的经验，因为 tool version/quirk 强依赖机器。Lockfile 仍是精确版本的主要 source of truth；
本 Memory 记录的是版本不匹配带来的 debugging cost，而不是 canonical version pin。

## Known Failure Patterns

- **Verilator <5.0 不支持 `--timing`**：含 `#delay` 或 event control 的设计在 Verilator 4.x
  会报 timing controls unsupported。正确修复是安装/加载 Verilator ≥5.0，而不是改 RTL。
  把版本写入 `tool_versions`，在 setup 阶段提前发现。
- **OpenROAD nightly 与 release ABI drift**：nightly binary 与固定 release 的 ORFS script 混用，会出现
  Tcl command-not-found 或 signature mismatch。OpenROAD 与 ORFS 应使用匹配 tag；如果
  `openroad --version` 与最近成功 run 不同，先标记版本差异，再 debug flow。
- **module unload 后 `python3` 指向错误 interpreter**：`python_env.type=="module"` 时，
  新 shell 未 source `load-modules.sh` 会 fallback 到 system python3，使 cocotb/openlane 假 MISSING。
  修复是先 source 脚本，并在 notes 记录 `python_env.module_name`。

## Successful Tool Flags / Install Notes

- 任何 Python package 检测前先 `module load <python-module>`，整个 run 中保持已加载。
- `"$PYTHON_EXEC" -m pip show openlane` / `"$PYTHON_BIN_DIR/cocotb-config" --version`：
  Python package 一律使用已解析 interpreter path；裸 `which` 在 custom/module Python 下会误报。
- `EDA_TOOLS_ROOT` 与 `EDA_MODULEFILES_ROOT` 决定 install layout；记录值便于在兄弟工作站复现。

## PDK / Tool Quirks

- **Bambu HLS 仅支持 Linux**：macOS/Windows 检测结果应为 WARN，而非 FAIL。环境指纹记录 os，避免将“macOS 缺失”误认为 Linux 安装损坏。
- **模块版本先遵循站点默认，再按发布版本比较器选择**（#98 前错误使用字典序）：module_discovery 优先 module avail 标注的系统默认，随后取最高发布版本，只有无发布版本时才选 -dev、_test、-debug 等非发布构建。站点默认经常比最新版本旧，这是预期行为；module-status.json 的 selected_basis 保留选择依据。仅某流程确实不适合站点默认时，才在 load-modules.sh 显式固定版本，不再将固定版本作为弥补普通字符串排序的常规方法。

## Notes

- 该 domain 与 design 无关，`design_name` 通常为 null；record 由 environment fingerprint 区分。
- `key_metrics.tool_versions` 是核心价值：比较多次 run 可快速找出导致 previously-passing flow 失败的版本变化。
