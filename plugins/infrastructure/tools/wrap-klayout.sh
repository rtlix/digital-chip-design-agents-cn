#!/usr/bin/env bash
# wrap-klayout.sh —— 运行 KLayout DRC，并输出紧凑 JSON summary
set -euo pipefail

TOOL="klayout"

if ! command -v "$TOOL" &>/dev/null; then
  python3 - <<'PYEOF'
import json
print(json.dumps({"tool":"klayout","exit_code":1,"status":"FAIL","verified":False,"summary":{},"errors":["tool not found: klayout"],"warnings":[],"raw_log":""}))
PYEOF
  exit 1
fi

LOG=$(mktemp /tmp/klayout-XXXXXX.log)
START_EPOCH=$(python3 -c "import time; print(time.time())")
set +e
"$TOOL" "$@" >"$LOG" 2>&1
EXIT_CODE=$?
set -e

python3 - "$LOG" "$EXIT_CODE" "$START_EPOCH" <<'PYEOF'
import json, re, sys, os, glob

log_path        = sys.argv[1]
exit_code       = int(sys.argv[2])
invocation_start = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0

with open(log_path, encoding='utf-8', errors='replace') as f:
    text = f.read()

errors   = [l.strip() for l in text.splitlines() if re.search(r'\bERROR\b', l, re.I)]
warnings = [l.strip() for l in text.splitlines() if re.search(r'\bWARN(?:ING)?\b', l, re.I)]

# 如果存在 KLayout DRC report XML（*.lyrdb 或 *.xml），则解析
drc_categories = {}
total_drc = 0
# Report 可解析且没有 category 时视为 clean run；如果没有 report 且 log 中也没有 count，
# 则 DRC 结果是 unknown，不能当作 0。
evidence = False

for report_file in [f for f in glob.glob('*.lyrdb') + glob.glob('*drc*.xml')
                    if os.path.getmtime(f) >= invocation_start]:
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(report_file)
        root = tree.getroot()
        evidence = True
        for cat in root.findall('.//category'):
            name_el = cat.find('name')
            items   = cat.findall('.//item')
            if name_el is not None:
                cat_name  = name_el.text or "unknown"
                cat_count = len(items)
                drc_categories[cat_name] = cat_count
                total_drc += cat_count
    except Exception:
        pass

# Fallback：从文本 log 解析 DRC count
if not drc_categories:
    drc_m = re.search(r'(\d+)\s+(?:DRC\s+)?(?:error|violation)', text, re.I)
    if drc_m:
        total_drc = int(drc_m.group(1))
        evidence = True

summary = {
    "drc_total":      total_drc if evidence else None,
    "drc_categories": drc_categories,
    "error_count":    len(errors),
    "warning_count":  len(warnings),
}

if exit_code != 0 or errors:
    status = "FAIL"
elif not evidence:
    status = "WARN"
    warnings.insert(0, "no recognisable result in tool output (exit 0) - not verified; read raw_log")
elif total_drc > 0 or warnings:
    status = "WARN"
else:
    status = "PASS"

print(json.dumps({
    "tool":      "klayout",
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
