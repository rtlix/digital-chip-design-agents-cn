# Infrastructure Domain Knowledge（基础设施领域知识）

Tracking **默认关闭**，仅当 `pipeline_config.track_infrastructure:true` 或 `--track-memory` 启用。记录按 host/os/arch 分 key；精确版本仍以 lockfile 为主要 source of truth。

## Known Failure Patterns

- **Verilator <5.0 缺 `--timing`**：含 delay/event control 的设计需要升级工具，不应改 RTL 迎合旧版本。
- **OpenROAD nightly/release ABI drift**：OpenROAD binary 与 ORFS script 应使用匹配 tag；版本变化先于 flow debug 检查。
- **module Python 未加载**：新 shell 未 source `load-modules.sh` 会导致 cocotb/openlane 假 MISSING。
- **厂商 bundled Python 抢占 PATH**：EDA 安装树里的 Python 只记录为 candidate，绝不作为项目 `PYTHON_EXEC` 或 pip/venv base。
- **`pgrep` 形式的“单 licensed tool”门有 race**：两个 caller 可能同时观察到 idle。用 host-wide **`flock`** 持续覆盖 tool 全生命周期，并按 exact name `pgrep -x` 兼容旧 caller；宽泛 `pgrep -f` / `pkill -f` 会匹配调用者自身。
- **裸 `timeout` 会留下持 license 的 child**：使用 `setsid`，timeout 后杀 process group；必要时 `MemoryMax` 限制内存。
- **商业工具启动很慢**：ICC2 在高负载 VM 上实测 30–65 min；不能拿短 timeout 当 hang。

## Successful Tool Flags / Install Notes

- `module load <python-module>` 后整个 Orchestrator run 保持加载。
- Python package 通过 `"$PYTHON_EXEC" -m pip ...` / `"$PYTHON_BIN_DIR/..." ` 检测；项目 pip package 优先 project-local venv。
- `safe_run.sh`：检查 load / `MemAvailable`，设置 `MemoryMax`、nice、setsid、≤2 threads，并在 timeout 时 group kill。
- `licensed_lock.sh`：host-wide `flock`，保证同一时间只跑一个 heavy licensed tool。
- License yes/no 可使用 vendor `ckout_test`；普通 lmstat 结果不总能代表真实 checkout 能力。

## PDK / Tool Quirks

- Bambu HLS 仅 Linux，其他平台缺失为 WARN。
- Module version 选择优先 site default，再按 release version 比较；非 release build 仅在没有 release 时才选择。
- 小主机上 heavy PD/STA/signoff job 应串行，field solver 单独排队。

## Notes

- Infrastructure record 以 environment fingerprint 区分。
- `key_metrics.tool_versions` 用于快速发现“之前能跑、现在失败”的版本变化。
- _Last distilled: 2026-11-07 from measured B0/shared-host commercial-flow records._
