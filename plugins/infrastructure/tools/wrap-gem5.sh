#!/usr/bin/env bash
# wrap-gem5.sh —— 运行 gem5，并输出紧凑 JSON summary
set -euo pipefail

TOOL="gem5"

if ! command -v "$TOOL" &>/dev/null; then
  _LOG=$(mktemp /tmp/gem5-notfound-XXXXXX.log)
  echo "tool not found: gem5" > "$_LOG"
  python3 - "$_LOG" <<'PYEOF'
import json, sys
log_path = sys.argv[1]
print(json.dumps({"tool":"gem5","exit_code":1,"status":"FAIL","verified":False,"summary":{},"errors":["tool not found: gem5"],"warnings":[],"raw_log":log_path}))
PYEOF
  exit 1
fi

LOG=$(mktemp /tmp/gem5-XXXXXX.log)
set +e
"$TOOL" "$@" >"$LOG" 2>&1
EXIT_CODE=$?
set -e

python3 - "$LOG" "$EXIT_CODE" <<'PYEOF'
import json, re, sys

log_path = sys.argv[1]
exit_code = int(sys.argv[2])

with open(log_path, encoding='utf-8', errors='replace') as f:
    text = f.read()

errors   = [l.strip() for l in text.splitlines() if re.search(r'\bERROR\b|panic|fatal', l, re.I)]
warnings = [l.strip() for l in text.splitlines() if re.search(r'\bWARN(?:ING)?\b', l, re.I)]

sim_insts_m   = re.search(r'simInsts\s+(\d+)', text)
host_secs_m   = re.search(r'hostSeconds\s+([\d.]+)', text)
ipc_m         = re.search(r'\bipc\b\s+([\d.]+)', text, re.I)

summary = {}
if sim_insts_m: summary["sim_insts"]    = int(sim_insts_m.group(1))
if host_secs_m: summary["host_seconds"] = float(host_secs_m.group(1))
if ipc_m:       summary["ipc"]          = float(ipc_m.group(1))
summary["error_count"]   = len(errors)
summary["warning_count"] = len(warnings)

# PASS 必须有工具输出中的可识别结果；仅 exit 0 不能作为 PASS 依据。 gem5 writes
# gem5 会把统计写入 m5out/stats.txt；如果运行输出中没有任何可识别统计，
# 则标记为 unverified，由 Agent 再读取该文件。
evidence = bool(sim_insts_m or host_secs_m or ipc_m)

if exit_code != 0 or errors:
    status = "FAIL"
elif not evidence:
    status = "WARN"
    warnings.insert(0, "no recognisable result in tool output (exit 0) - not verified; read raw_log")
elif warnings:
    status = "WARN"
else:
    status = "PASS"

print(json.dumps({
    "tool":      "gem5",
    "exit_code": exit_code,
    "status":    status,
    "verified":  status == "FAIL" or evidence,
    "summary":   summary,
    "errors":    errors[:10],
    "warnings":  warnings[:10],
    "raw_log":   log_path
}, indent=2))
PYEOF

exit $EXIT_CODE
