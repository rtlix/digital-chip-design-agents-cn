#!/usr/bin/env python3
"""
mcp-session-adapter.py —— 面向交互式 EDA tool session 的持久化 MCP stdio Server。

通过 stdio 实现 MCP protocol 2024-11-05（JSON-RPC 2.0，每行一个消息）。
在多次 tool call 之间保持长期运行的 Tcl 子进程（openroad 或 sta），这样 Agent 可以对已加载 design 反复查询 timing、DRC、area 等，而无需每次重新加载。

用法：
    python3 mcp-session-adapter.py --tool openroad [--version 1.0.0]
    python3 mcp-session-adapter.py --tool opensta  [--version 1.0.0]

环境变量（openroad）：
    OPENROAD_EXE        openroad executable name or path (default: openroad)
    PDK_ROOT            path to PDK root (used in load_design defaults)
    PLATFORM            PDK platform name e.g. sky130hd

环境变量（opensta）：
    OPENSTA_EXE         sta executable name or path (default: sta)
    LIBERTY_PATH        default directory for .lib files
    SPEF_PATH           full path to the .spef parasitics file (not a directory); passed directly to read_parasitics

环境变量（两者通用）：
    SESSION_TIMEOUT_S   per-command timeout in seconds (default: 120)
    SESSION_STARTUP_S   startup drain timeout in seconds (default: 10)
"""

import sys
import json
import subprocess
import argparse
import os
import re
import select
import time
import threading
from typing import Optional


def _readline_timed(stream, deadline: float) -> str:
    """
    从 stream 读取一行；若在收到数据前已到 deadline，则返回空字符串。使用 select(2)，确保调用线程不会阻塞超过剩余时间预算。

    注意：对 file object 使用 select 仅适用于 POSIX（Linux/macOS）。这些 wrapper script 面向 Linux EDA 环境，不支持 Windows。
    """
    remaining = deadline - time.time()
    if remaining <= 0:
        return ''
    ready, _, _ = select.select([stream], [], [], remaining)
    if not ready:
        return ''
    return stream.readline()

# ---------------------------------------------------------------------------
# Protocol 辅助函数
# ---------------------------------------------------------------------------

def _send(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg, separators=(',', ':')) + '\n')
    sys.stdout.flush()


def _ok(req_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _log(msg: str) -> None:
    print(f"[mcp-session] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Tcl session
# ---------------------------------------------------------------------------

_SENTINEL = "<<MCP_SESSION_DONE>>"


class TclSession:
    """
    封装长期运行的 Tcl-based EDA 进程（openroad / sta）。

    命令通过 stdin 发送；持续收集输出直到 sentinel 行出现。stderr 合并进 stdout，以便捕获错误消息。
    """

    def __init__(self, exe: str, startup_timeout: int = 10):
        self._proc = subprocess.Popen(
            [exe],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,          # line-buffered
        )
        self._lock = threading.Lock()
        self._alive = True
        # 清理启动 banner
        self._drain_startup(startup_timeout)
        _log(f"session started (pid={self._proc.pid})")

    def _drain_startup(self, timeout: int) -> None:
        """
        通过立即发送 sentinel 并收集到回显为止，丢弃启动 banner；通过 select 遵守 timeout。
        """
        self._proc.stdin.write(f'puts "{_SENTINEL}"\n')
        self._proc.stdin.flush()
        deadline = time.time() + timeout
        while True:
            line = _readline_timed(self._proc.stdout, deadline)
            if not line or line.rstrip('\n') == _SENTINEL:
                break

    def run(self, tcl: str, timeout: int = 120) -> tuple[list[str], bool]:
        """
        发送 Tcl 命令并收集输出直到 sentinel。返回 (lines, had_error)，线程安全。
        """
        if not self._alive:
            return ["session is closed"], True

        with self._lock:
            script = tcl.strip() + f'\nputs "{_SENTINEL}"\n'
            try:
                self._proc.stdin.write(script)
                self._proc.stdin.flush()
            except BrokenPipeError:
                self._alive = False
                return ["session process died (broken pipe)"], True

            lines: list[str] = []
            had_error = False
            deadline = time.time() + timeout

            while True:
                line = _readline_timed(self._proc.stdout, deadline)
                if line == '':
                    # 空字符串表示 deadline 已到（select timeout）或 EOF
                    if self._proc.poll() is not None:
                        self._alive = False
                        had_error = True
                        lines.append("session process exited unexpectedly")
                    else:
                        had_error = True
                        lines.append(f"command timed out after {timeout}s")
                        try:
                            self._proc.kill()
                        except OSError:
                            pass
                        self._alive = False
                    break
                stripped = line.rstrip('\n')
                if stripped == _SENTINEL:
                    break
                lines.append(stripped)
                if re.search(r'\[ERROR\]|^Error\b|^error\b', stripped):
                    had_error = True

            return lines, had_error

    def is_alive(self) -> bool:
        if not self._alive:
            return False
        if self._proc.poll() is not None:
            self._alive = False
        return self._alive

    def close(self) -> None:
        if not self._alive:
            return
        try:
            self._proc.stdin.write("exit\n")
            self._proc.stdin.flush()
        except Exception:
            pass
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        self._alive = False
        _log("session closed")


# ---------------------------------------------------------------------------
# 解析辅助函数
# ---------------------------------------------------------------------------

def _parse_timing(lines: list[str]) -> dict:
    """从 report_timing 输出提取 WNS、TNS 和 worst-slack path。"""
    text = '\n'.join(lines)
    result: dict = {}

    wns_m = re.search(r'wns\s+([-\d.]+)', text)
    tns_m = re.search(r'tns\s+([-\d.]+)', text)
    if wns_m:
        result["setup_wns_ns"] = float(wns_m.group(1))
    if tns_m:
        result["setup_tns_ns"] = float(tns_m.group(1))

    # Hold 指标
    hold_wns_m = re.search(r'hold\s+wns\s+([-\d.]+)', text, re.I)
    hold_tns_m = re.search(r'hold\s+tns\s+([-\d.]+)', text, re.I)
    if hold_wns_m:
        result["hold_wns_ns"] = float(hold_wns_m.group(1))
    if hold_tns_m:
        result["hold_tns_ns"] = float(hold_tns_m.group(1))

    # 最差路径 endpoint 名称
    endpoints = re.findall(r'Endpoint\s*:\s*(\S+)', text)
    if endpoints:
        result["worst_endpoints"] = endpoints[:5]

    slack_m = re.findall(r'slack\s+\((?:MET|VIOLATED)\)\s+([-\d.]+)', text)
    if slack_m:
        result["worst_slack_ns"] = float(slack_m[0])

    result["raw_lines"] = len(lines)
    return result


def _parse_drc(lines: list[str]) -> dict:
    """从 check_drc / report_drc 输出提取 DRC violation 数量。"""
    text = '\n'.join(lines)
    result: dict = {}
    total_m = re.search(r'(\d+)\s+(?:DRC\s+)?(?:violations?|errors?)', text, re.I)
    if total_m:
        result["drc_total"] = int(total_m.group(1))
    else:
        # 输出中没有计数时，结果是 unknown，而不是 0 violation。
        result["drc_total"] = None

    cats: dict = {}
    for m in re.finditer(r'(\w[\w\s]*?)\s*:\s*(\d+)\s*violations?', text, re.I):
        cats[m.group(1).strip()] = int(m.group(2))
    if cats:
        result["drc_categories"] = cats

    result["raw_lines"] = len(lines)
    return result


def _parse_area(lines: list[str]) -> dict:
    """从 report_design_area 输出提取 area 和 utilization。"""
    text = '\n'.join(lines)
    result: dict = {}
    area_m = re.search(r'Design area\s+([\d.]+)\s+u\^2\s+([\d.]+)%', text)
    if area_m:
        result["area_um2"] = float(area_m.group(1))
        result["utilisation_pct"] = float(area_m.group(2))
    result["raw_lines"] = len(lines)
    return result


def _parse_power(lines: list[str]) -> dict:
    """从 report_power 输出提取 power summary。"""
    text = '\n'.join(lines)
    result: dict = {}
    total_m = re.search(r'Total\s+([\d.e+\-]+)\s+([\d.e+\-]+)\s+([\d.e+\-]+)\s+([\d.e+\-]+)', text)
    if total_m:
        result["internal_power_W"] = float(total_m.group(1))
        result["switching_power_W"] = float(total_m.group(2))
        result["leakage_power_W"]   = float(total_m.group(3))
        result["total_power_W"]     = float(total_m.group(4))
    result["raw_lines"] = len(lines)
    return result


# ---------------------------------------------------------------------------
# 各 session 类型的工具定义
# ---------------------------------------------------------------------------

_TOOLS_OPENROAD = [
    {
        "name": "load_design",
        "description": "把 OpenROAD design database（.odb/.db）加载到当前 session",
        "inputSchema": {
            "type": "object",
            "properties": {
                "db_path": {
                    "type": "string",
                    "description": ".odb 或 .db 文件的绝对路径"
                }
            },
            "required": ["db_path"],
        },
    },
    {
        "name": "query_timing",
        "description": "报告 setup/hold timing summary：WNS、TNS、worst endpoints",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path_count": {
                    "type": "integer",
                    "default": 5,
                    "description": "要报告的 worst path 数量（默认 5）"
                },
                "path_type": {
                    "type": "string",
                    "enum": ["setup", "hold", "both"],
                    "default": "setup",
                    "description": "要报告的 timing check 类型"
                },
            },
        },
    },
    {
        "name": "query_drc",
        "description": "运行 DRC check，并返回总 violation 数和按 category 分类的统计",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_design_area",
        "description": "返回 core area（um²）和 utilization 百分比",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_power",
        "description": "返回 power breakdown：internal、switching、leakage、total（W）",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_tcl",
        "description": "在 OpenROAD session 中执行任意 Tcl，并返回原始输出行",
        "inputSchema": {
            "type": "object",
            "properties": {
                "script": {
                    "type": "string",
                    "description": "要执行的 Tcl script"
                },
                "timeout_s": {
                    "type": "integer",
                    "description": "覆盖单条命令 timeout 的秒数"
                },
            },
            "required": ["script"],
        },
    },
    {
        "name": "close_design",
        "description": "重置 OpenROAD session（清除已加载 design，但 session 进程保持运行）",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

_TOOLS_OPENSTA = [
    {
        "name": "load_design",
        "description": "把 gate-level netlist、Liberty、SDC 以及可选 parasitics 加载到 OpenSTA",
        "inputSchema": {
            "type": "object",
            "properties": {
                "netlist": {
                    "type": "string",
                    "description": "gate-level Verilog netlist 路径"
                },
                "sdc": {
                    "type": "string",
                    "description": "SDC constraint 文件路径"
                },
                "liberty_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "`.lib` Liberty 文件路径列表（补充 LIBERTY_PATH 环境变量）"
                },
                "spef": {
                    "type": "string",
                    "description": "`.spef` parasitics 文件路径（可选）"
                },
                "top_module": {
                    "type": "string",
                    "description": "要 link 的 top-level module 名称"
                },
            },
            "required": ["netlist", "sdc"],
        },
    },
    {
        "name": "report_timing",
        "description": "报告 setup/hold timing：WNS、TNS、每个 corner 的 worst-slack path",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path_count": {
                    "type": "integer",
                    "default": 5,
                    "description": "worst path 数量（默认 5）"
                },
                "path_type": {
                    "type": "string",
                    "enum": ["max", "min", "both"],
                    "default": "max",
                    "description": "max=setup，min=hold"
                },
                "corner": {
                    "type": "string",
                    "description": "指定 corner 名；省略则表示全部 corner"
                },
            },
        },
    },
    {
        "name": "report_slack_histogram",
        "description": "返回所有 endpoint 的 slack 分布 histogram",
        "inputSchema": {
            "type": "object",
            "properties": {
                "bins": {
                    "type": "integer",
                    "default": 10,
                    "description": "histogram bin 数量"
                }
            },
        },
    },
    {
        "name": "check_timing",
        "description": "报告 unconstrained path、multi-driven net 和 missing constraint",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_tcl",
        "description": "在 OpenSTA session 中执行任意 Tcl，并返回原始输出行",
        "inputSchema": {
            "type": "object",
            "properties": {
                "script": {
                    "type": "string",
                    "description": "要执行的 Tcl script"
                },
                "timeout_s": {
                    "type": "integer",
                    "description": "覆盖单条命令 timeout 的秒数"
                },
            },
            "required": ["script"],
        },
    },
    {
        "name": "close_design",
        "description": "重置 OpenSTA session（清除已加载 design，但 session 进程保持运行）",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

def _dispatch_openroad(
    session: TclSession, tool_name: str, inputs: dict, timeout: int
) -> dict:
    if tool_name == "load_design":
        db = inputs["db_path"]
        lines, err = session.run(f'read_db {{{db}}}', timeout)
        return {"loaded": not err, "db_path": db, "messages": lines[:20], "had_error": err}

    elif tool_name == "query_timing":
        n = inputs.get("path_count", 5)
        pt = inputs.get("path_type", "setup")
        if pt == "both":
            tcl = (
                f'report_timing -path_type summary -nworst {n}\n'
                f'report_timing -path_type summary -nworst {n} -hold'
            )
        elif pt == "hold":
            tcl = f'report_timing -path_type summary -nworst {n} -hold'
        else:
            tcl = f'report_timing -path_type summary -nworst {n}'
        lines, err = session.run(tcl, timeout)
        parsed = _parse_timing(lines)
        parsed["had_error"] = err
        return parsed

    elif tool_name == "query_drc":
        lines, err = session.run('check_drc', timeout)
        parsed = _parse_drc(lines)
        parsed["had_error"] = err
        return parsed

    elif tool_name == "get_design_area":
        lines, err = session.run('report_design_area', timeout)
        parsed = _parse_area(lines)
        parsed["had_error"] = err
        return parsed

    elif tool_name == "get_power":
        lines, err = session.run('report_power', timeout)
        parsed = _parse_power(lines)
        parsed["had_error"] = err
        return parsed

    elif tool_name == "run_tcl":
        script = inputs["script"]
        t = inputs.get("timeout_s", timeout)
        lines, err = session.run(script, t)
        return {"output_lines": lines, "had_error": err, "line_count": len(lines)}

    elif tool_name == "close_design":
        lines, err = session.run('delete_db', timeout)
        return {"reset": True, "messages": lines[:10], "had_error": err}

    return {"error": f"unknown tool: {tool_name}"}


def _dispatch_opensta(
    session: TclSession, tool_name: str, inputs: dict, timeout: int
) -> dict:
    if tool_name == "load_design":
        tcl_parts: list[str] = []

        # Liberty 文件来自环境变量和输入参数
        liberty_dir = os.environ.get("LIBERTY_PATH", "")
        for lib in inputs.get("liberty_files", []):
            tcl_parts.append(f'read_liberty {{{lib}}}')
        if liberty_dir and not inputs.get("liberty_files"):
            tcl_parts.append(f'foreach f [glob -nocomplain {{{liberty_dir}}}/*.lib] {{ read_liberty $f }}')

        tcl_parts.append(f'read_verilog {{{inputs["netlist"]}}}')
        top = inputs.get("top_module", "")
        tcl_parts.append(f'link_design {top}' if top else 'link_design')
        tcl_parts.append(f'read_sdc {{{inputs["sdc"]}}}')

        spef = inputs.get("spef") or os.environ.get("SPEF_PATH", "")
        if spef:
            tcl_parts.append(f'read_parasitics {{{spef}}}')

        lines, err = session.run('\n'.join(tcl_parts), timeout)
        return {"loaded": not err, "messages": lines[:20], "had_error": err}

    elif tool_name == "report_timing":
        n = inputs.get("path_count", 5)
        pt = inputs.get("path_type", "max")
        corner = inputs.get("corner", "")
        corner_flag = f'-corner {corner}' if corner else ''
        if pt == "both":
            tcl = (
                f'report_timing -path_type summary -nworst {n} {corner_flag}\n'
                f'report_timing -path_type summary -nworst {n} -path_type min {corner_flag}'
            )
        else:
            path_flag = '-path_type min' if pt == "min" else ''
            tcl = f'report_timing -path_type summary -nworst {n} {path_flag} {corner_flag}'
        lines, err = session.run(tcl, timeout)
        parsed = _parse_timing(lines)
        parsed["had_error"] = err
        return parsed

    elif tool_name == "report_slack_histogram":
        bins = inputs.get("bins", 10)
        lines, err = session.run(f'report_slack_histogram -digits 3 -bins {bins}', timeout)
        text = '\n'.join(lines)
        buckets: list[dict] = []
        for m in re.finditer(r'([-\d.]+)\s+([-\d.]+)\s+(\d+)', text):
            buckets.append({
                "slack_low_ns": float(m.group(1)),
                "slack_high_ns": float(m.group(2)),
                "count": int(m.group(3)),
            })
        return {"buckets": buckets, "had_error": err, "raw_lines": len(lines)}

    elif tool_name == "check_timing":
        lines, err = session.run('check_timing', timeout)
        text = '\n'.join(lines)
        unconstrained = len(re.findall(r'unconstrained', text, re.I))
        multi_driven  = len(re.findall(r'multiple.driven|multi.driven', text, re.I))
        return {
            "unconstrained_endpoints": unconstrained,
            "multi_driven_nets": multi_driven,
            "output_lines": lines[:30],
            "had_error": err,
        }

    elif tool_name == "run_tcl":
        script = inputs["script"]
        t = inputs.get("timeout_s", timeout)
        lines, err = session.run(script, t)
        return {"output_lines": lines, "had_error": err, "line_count": len(lines)}

    elif tool_name == "close_design":
        lines, err = session.run('remove_design', timeout)
        return {"reset": True, "messages": lines[:10], "had_error": err}

    return {"error": f"unknown tool: {tool_name}"}


# ---------------------------------------------------------------------------
# 主 Server 循环
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="OpenROAD / OpenSTA 的持久化 MCP stdio session adapter"
    )
    parser.add_argument(
        "--tool",
        required=True,
        choices=["openroad", "opensta"],
        help="要管理的工具：openroad 或 opensta",
    )
    parser.add_argument("--version", default="1.0.0")
    args = parser.parse_args()

    tool_type = args.tool
    cmd_timeout = int(os.environ.get("SESSION_TIMEOUT_S", "120"))
    startup_timeout = int(os.environ.get("SESSION_STARTUP_S", "10"))

    if tool_type == "openroad":
        exe = os.environ.get("OPENROAD_EXE", "openroad")
        tools_list = _TOOLS_OPENROAD
        server_name = "openroad-session-mcp"
    else:
        exe = os.environ.get("OPENSTA_EXE", "sta")
        tools_list = _TOOLS_OPENSTA
        server_name = "opensta-session-mcp"

    session: Optional[TclSession] = None

    def _get_session() -> TclSession:
        nonlocal session
        if session is None or not session.is_alive():
            _log(f"(re)starting {tool_type} session with: {exe}")
            session = TclSession(exe, startup_timeout)
        return session

    _log(f"starting {server_name} (exe={exe}, cmd_timeout={cmd_timeout}s)")

    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        try:
            req = json.loads(raw_line)
        except json.JSONDecodeError:
            _log(f"malformed JSON ignored: {raw_line[:80]}")
            continue

        method: str = req.get("method", "")
        req_id = req.get("id")
        params: dict = req.get("params") or {}

        if req_id is None:
            _log(f"notification: {method}")
            continue

        _log(f"request id={req_id} method={method}")

        if method == "initialize":
            _send(_ok(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": server_name, "version": args.version},
            }))

        elif method == "ping":
            _send(_ok(req_id, {}))

        elif method == "tools/list":
            _send(_ok(req_id, {"tools": tools_list}))

        elif method == "tools/call":
            call_name: str = params.get("name", "")
            call_inputs: dict = params.get("arguments") or {}

            known = {t["name"] for t in tools_list}
            if call_name not in known:
                _send(_err(req_id, -32602, f"Unknown tool '{call_name}'"))
                continue

            try:
                sess = _get_session()
                if tool_type == "openroad":
                    result = _dispatch_openroad(sess, call_name, call_inputs, cmd_timeout)
                else:
                    result = _dispatch_opensta(sess, call_name, call_inputs, cmd_timeout)
            except Exception as exc:
                _log(f"dispatch error: {exc}")
                result = {"had_error": True, "error": str(exc)}

            is_error = result.get("had_error", False)
            _send(_ok(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                "isError": is_error,
            }))

        else:
            _send(_err(req_id, -32601, f"Method not found: {method}"))

    # EOF 时清理 session
    if session and session.is_alive():
        session.close()


if __name__ == "__main__":
    main()
