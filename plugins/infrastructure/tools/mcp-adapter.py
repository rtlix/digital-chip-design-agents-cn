#!/usr/bin/env python3
"""
mcp-adapter.py —— 用于封装 EDA 工具 wrapper script 的通用 MCP stdio Server。

通过 stdio 实现 MCP protocol 2024-11-05（JSON-RPC 2.0，每行一个消息）。

用法：
    python3 mcp-adapter.py --wrapper /path/to/wrap-TOOL.sh --tool TOOL \\
        [--description "Short description"] [--version 1.0.0]

环境变量：
    TOOL_TIMEOUT_S   wrapper 进程的超时秒数（默认：300）

每次 tools/call 都使用传入参数运行 wrapper script，并把 wrapper 的紧凑 JSON 输出
作为 MCP tool result 返回。所有 debug/status 信息写到 stderr，避免污染 stdout 上的 MCP protocol stream。
"""

import sys
import json
import subprocess
import argparse
import os
import tempfile
import atexit

# inline Tcl script 创建的临时文件——进程退出时统一清理
_temp_files: list[str] = []


def _cleanup_temp_files() -> None:
    for path in _temp_files:
        try:
            os.unlink(path)
        except OSError:
            pass


atexit.register(_cleanup_temp_files)

# ---------------------------------------------------------------------------
# MCP protocol 辅助函数
# ---------------------------------------------------------------------------

def _send(msg: dict) -> None:
    """把 msg 序列化为 stdout 上的一行 JSON，并立即 flush。"""
    sys.stdout.write(json.dumps(msg, separators=(',', ':')) + '\n')
    sys.stdout.flush()


def _ok(req_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


# ---------------------------------------------------------------------------
# 各工具的 input schema 与参数构造
# ---------------------------------------------------------------------------

_EXTRA_PROPERTIES: dict[str, dict] = {
    "yosys": {
        "script": {
            "type": "string",
            "description": "通过 -p 传给 Yosys 的 inline command（可替代 args）"
        },
        "script_file": {
            "type": "string",
            "description": "`.ys` script 文件路径"
        },
    },
    "openroad": {
        "tcl_script": {
            "type": "string",
            "description": "写入临时文件后传给 OpenROAD 的 inline Tcl script"
        },
    },
    "opensta": {
        "tcl_script": {
            "type": "string",
            "description": "写入临时文件后传给 OpenSTA 的 inline Tcl script"
        },
    },
    "verilator": {
        "mode": {
            "type": "string",
            "enum": ["lint", "sim"],
            "description": "lint：verilator --lint-only；sim：运行预编译 simulation binary"
        },
        "sim_binary": {
            "type": "string",
            "description": "已编译 Verilator simulation binary 的路径（sim mode 必填）"
        },
    },
    "bambu": {
        "c_file": {
            "type": "string",
            "description": "要综合的 C/C++ source file 路径"
        },
        "top_function": {
            "type": "string",
            "description": "要综合的 top-level function 名称"
        },
    },
    "gem5": {
        "config_script": {
            "type": "string",
            "description": "gem5 Python configuration script 路径"
        },
        "binary": {
            "type": "string",
            "description": "要仿真的 workload binary（追加在 config_script 后）"
        },
    },
    "symbiflow": {
        "sby_file": {
            "type": "string",
            "description": "SymbiYosys `.sby` configuration file 路径"
        },
        "task": {
            "type": "string",
            "description": "`.sby` 文件中的可选 task 名称"
        },
    },
}


def _input_schema(tool: str) -> dict:
    props: dict = {
        "args": {
            "type": "array",
            "items": {"type": "string"},
            "description": "直接传给 wrapper script 的原始 CLI 参数",
            "default": [],
        }
    }
    props.update(_EXTRA_PROPERTIES.get(tool, {}))
    return {"type": "object", "properties": props}


def _build_cli_args(tool: str, inputs: dict) -> list[str]:
    """
    Map structured tool inputs to the CLI argument list that will be passed
    to the wrapper script.  Falls back to raw args[] if no typed fields match.
    """
    raw: list[str] = inputs.get("args", [])

    if tool == "yosys":
        if "script" in inputs:
            return ["-p", inputs["script"]] + raw
        if "script_file" in inputs:
            return [inputs["script_file"]] + raw

    elif tool in ("openroad", "opensta"):
        if "tcl_script" in inputs:
            tf = tempfile.NamedTemporaryFile(
                mode="w", suffix=".tcl", delete=False, prefix="mcp_tcl_"
            )
            tf.write(inputs["tcl_script"])
            tf.flush()
            tf.close()
            _temp_files.append(tf.name)
            print(f"[mcp-adapter] wrote Tcl script to {tf.name}", file=sys.stderr)
            return [tf.name] + raw

    elif tool == "verilator":
        mode = inputs.get("mode", "sim")
        if mode == "lint":
            return ["--lint-only"] + raw
        sim_bin = inputs.get("sim_binary", "")
        if sim_bin:
            return [sim_bin] + raw

    elif tool == "bambu":
        cli: list[str] = []
        if "top_function" in inputs:
            cli.append("--top-fname=" + inputs["top_function"])
        cli.extend(raw)
        if "c_file" in inputs:
            cli.insert(0, inputs["c_file"])
        return cli

    elif tool == "gem5":
        cli = list(raw)
        if "config_script" in inputs:
            cli.insert(0, inputs["config_script"])
        if "binary" in inputs:
            cli.append(inputs["binary"])
        return cli

    elif tool in ("symbiyosys", "symbiflow"):
        cli = list(raw)
        if "sby_file" in inputs:
            cli.insert(0, inputs["sby_file"])
        if "task" in inputs:
            cli.append(inputs["task"])
        return cli

    return raw


# ---------------------------------------------------------------------------
# Wrapper 执行
# ---------------------------------------------------------------------------

VALID_STATUSES = ("PASS", "WARN", "FAIL")

def _run_wrapper(wrapper_path: str, tool: str, inputs: dict, timeout: int) -> dict:
    """
    执行 wrapper script 并返回解析后的 JSON。始终返回符合 wrapper JSON schema 的 dict，调用方无需处理意外数据形状。
    """
    cli_args = _build_cli_args(tool, inputs)
    cmd = [wrapper_path] + cli_args
    print(f"[mcp-adapter] running: {' '.join(cmd)}", file=sys.stderr)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = proc.stdout.strip()
        stderr_snippet = proc.stderr.strip()[:500] if proc.stderr else ""

        # A wrapper prints its JSON on every run, whatever the tool's exit code.
        # Anything else means the wrapper itself did not produce a result, so it
        # is reported as FAIL even when the process exited 0.
        if stdout:
            try:
                result = json.loads(stdout)
            except json.JSONDecodeError:
                result = None
                problem = "wrapper output was not valid JSON"
            else:
                if isinstance(result, dict) and result.get("status") in VALID_STATUSES:
                    return result
                problem = "wrapper JSON has no valid 'status' (expected PASS, WARN or FAIL)"
        else:
            problem = "wrapper produced no output"

        failure = {
            "tool": tool,
            "exit_code": proc.returncode,
            "status": "FAIL",
            "verified": False,
            "summary": {},
            "errors": [f"{problem} (exit {proc.returncode}) - no result to report"],
            "warnings": [],
            "raw_log": "",
        }
        if stdout:
            failure["raw_output_excerpt"] = stdout[:500]
        if stderr_snippet:
            failure["stderr_excerpt"] = stderr_snippet
        return failure

    except subprocess.TimeoutExpired:
        return {
            "tool": tool,
            "exit_code": -1,
            "status": "FAIL",
            "verified": False,
            "summary": {},
            "errors": [
                f"process timed out after {timeout}s — raise TOOL_TIMEOUT_S env var to allow longer runs"
            ],
            "warnings": [],
            "raw_log": "",
        }

    except FileNotFoundError:
        return {
            "tool": tool,
            "exit_code": 1,
            "status": "FAIL",
            "verified": False,
            "summary": {},
            "errors": [f"wrapper script not found: {wrapper_path}"],
            "warnings": [],
            "raw_log": "",
        }


# ---------------------------------------------------------------------------
# 主 Server 循环
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="用于 EDA tool wrapper script 的通用 MCP stdio adapter"
    )
    parser.add_argument("--wrapper", required=True, help="wrapper script 的绝对路径")
    parser.add_argument("--tool", required=True, help="工具名（yosys、openroad 等）")
    parser.add_argument(
        "--description",
        default="",
        help="显示在 tools/list 中的一行说明",
    )
    parser.add_argument("--version", default="1.0.0")
    args = parser.parse_args()

    _timeout_raw = os.environ.get("TOOL_TIMEOUT_S", "300")
    try:
        timeout = int(_timeout_raw)
    except ValueError:
        print(
            f"[mcp-adapter] WARNING: invalid TOOL_TIMEOUT_S={_timeout_raw!r}, using default 300s",
            file=sys.stderr,
        )
        timeout = 300
    tool_name = args.tool
    wrapper_path = args.wrapper
    description = args.description or (
        f"通过 output-filtering wrapper 运行 {tool_name}；返回紧凑 JSON summary"
    )

    print(
        f"[mcp-adapter] starting {tool_name} MCP server "
        f"(wrapper={wrapper_path}, timeout={timeout}s)",
        file=sys.stderr,
    )

    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        try:
            req = json.loads(raw_line)
        except json.JSONDecodeError:
            print(f"[mcp-adapter] malformed JSON ignored: {raw_line[:100]}", file=sys.stderr)
            continue

        method: str = req.get("method", "")
        req_id = req.get("id")  # None for notifications
        _raw_params = req.get("params")
        params: dict = _raw_params if isinstance(_raw_params, dict) else {}

        # Notifications have no id — no response required
        if req_id is None:
            print(f"[mcp-adapter] notification: {method}", file=sys.stderr)
            continue

        print(f"[mcp-adapter] request id={req_id} method={method}", file=sys.stderr)

        if method == "initialize":
            _send(_ok(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": f"{tool_name}-mcp", "version": args.version},
            }))

        elif method == "ping":
            _send(_ok(req_id, {}))

        elif method == "tools/list":
            _send(_ok(req_id, {
                "tools": [{
                    "name": tool_name,
                    "description": description,
                    "inputSchema": _input_schema(tool_name),
                }]
            }))

        elif method == "tools/call":
            if not isinstance(params, dict):
                _send(_err(req_id, -32602, "Invalid params: expected object"))
                continue
            call_name: str = params.get("name", "")
            _raw_args = params.get("arguments")
            call_inputs: dict = _raw_args if isinstance(_raw_args, dict) else {}
            if _raw_args is not None and not isinstance(_raw_args, dict):
                _send(_err(req_id, -32602, "Invalid params: 'arguments' must be an object"))
                continue

            if call_name != tool_name:
                _send(_err(req_id, -32602, f"Unknown tool '{call_name}'; this server exposes '{tool_name}'"))
                continue

            result = _run_wrapper(wrapper_path, tool_name, call_inputs, timeout)
            _send(_ok(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                "isError": result.get("status") == "FAIL",
            }))

        else:
            _send(_err(req_id, -32601, f"Method not found: {method}"))


if __name__ == "__main__":
    main()
