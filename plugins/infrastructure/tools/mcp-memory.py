#!/usr/bin/env python3
"""
mcp-memory.py —— 暴露语义/关键词 experience 搜索能力的 MCP stdio Server。

通过 stdio 实现 MCP protocol 2024-11-05（JSON-RPC 2.0，每行一个消息），协议骨架与 ``mcp-adapter.py`` 保持一致。
与 tool adapter 不同，本 Server 直接在进程内导入 ``tools/experience_search.py`` 完成工作，不再启动 shell wrapper。

仅暴露一个 ``query_experiences`` 工具：按 query 相关性对 ``memory/<domain>/experiences.jsonl`` 中的历史 experience record 排序，并返回紧凑 JSON（排序后的记录、score、matched terms、实际 backend，以及是否回退到 keyword search）。

用法：
    python3 mcp-memory.py [--memory-root PATH] [--version 1.0.0]

所有 debug/status 输出都写到 stderr，避免污染 stdout 上的 MCP protocol stream。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

# tools/experience_search.py 是 ranking 与 Memory-root resolver 的唯一可信实现。
# plugins/infrastructure/tools/mcp-memory.py -> repo root 为 parents[3]。
REPO_ROOT = Path(__file__).resolve().parents[3]
_SEARCH_PATH = REPO_ROOT / "tools" / "experience_search.py"

_spec = importlib.util.spec_from_file_location("experience_search", _SEARCH_PATH)
experience_search = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(experience_search)


# ---------------------------------------------------------------------------
# MCP protocol 辅助函数（结构与 mcp-adapter.py 相同）
# ---------------------------------------------------------------------------

def _send(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _ok(req_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


TOOL_NAME = "query_experiences"


def _input_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "enum": list(experience_search.VALID_DOMAINS),
                "description": "要搜索的 domain（例如 synthesis、pd、sta）",
            },
            "query": {
                "type": "string",
                "description": "自然语言 query，例如“sky130 的 WNS 以前是怎么修好的”",
            },
            "filters": {
                "type": "object",
                "description": "可选的精确匹配预过滤条件",
                "properties": {
                    "design_name": {"type": "string"},
                    "pdk": {"type": "string"},
                    "tool_used": {"type": "string"},
                },
            },
            "limit": {"type": "integer", "default": 5,
                      "description": "最多返回多少条结果"},
            "min_records_threshold": {
                "type": "integer", "default": 50,
                "description": "该 domain 的 record 数低于此阈值时，embedding 回退到 keyword",
            },
            "backend": {
                "type": "string",
                "enum": ["auto", "keyword", "embedding"],
                "default": "auto",
            },
        },
        "required": ["domain", "query"],
    }


def _handle_call(arguments: dict, memory_root: str | None) -> dict:
    domain = arguments.get("domain", "")
    query = arguments.get("query", "")
    if domain not in experience_search.VALID_DOMAINS:
        return {"error": f"unknown domain {domain!r}",
                "valid_domains": list(experience_search.VALID_DOMAINS)}
    if not isinstance(query, str) or not query.strip():
        return {"error": "query must be a non-empty string"}

    raw_filters = arguments.get("filters") or {}
    filters = {k: raw_filters[k] for k in ("design_name", "pdk", "tool_used")
               if isinstance(raw_filters, dict) and raw_filters.get(k)}

    return experience_search.query_experiences(
        domain, query,
        filters=filters,
        limit=int(arguments.get("limit", 5)),
        min_records_threshold=int(arguments.get("min_records_threshold", 50)),
        memory_root=memory_root,
        backend=arguments.get("backend", "auto"),
    )


# ---------------------------------------------------------------------------
# 主 Server 循环
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="用于 experience 语义/关键词搜索的 MCP stdio Server")
    parser.add_argument("--memory-root", default=None,
                        help="显式指定 Memory root（默认自动检测）")
    parser.add_argument("--version", default="1.0.0")
    args = parser.parse_args()

    description = (
        "按相似度搜索历史芯片设计 experience record；返回 "
        "按相关性排序的历史修复、score、matched terms 以及实际使用的 backend")

    print(f"[mcp-memory] starting (memory_root={args.memory_root or 'auto'})",
          file=sys.stderr)

    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        try:
            req = json.loads(raw_line)
        except json.JSONDecodeError:
            print(f"[mcp-memory] malformed JSON ignored: {raw_line[:100]}",
                  file=sys.stderr)
            continue

        method: str = req.get("method", "")
        req_id = req.get("id")
        _raw_params = req.get("params")
        params: dict = _raw_params if isinstance(_raw_params, dict) else {}

        if req_id is None:
            print(f"[mcp-memory] notification: {method}", file=sys.stderr)
            continue

        print(f"[mcp-memory] request id={req_id} method={method}", file=sys.stderr)

        if method == "initialize":
            _send(_ok(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "memory-mcp", "version": args.version},
            }))

        elif method == "ping":
            _send(_ok(req_id, {}))

        elif method == "tools/list":
            _send(_ok(req_id, {
                "tools": [{
                    "name": TOOL_NAME,
                    "description": description,
                    "inputSchema": _input_schema(),
                }]
            }))

        elif method == "tools/call":
            call_name: str = params.get("name", "")
            _raw_args = params.get("arguments")
            if _raw_args is not None and not isinstance(_raw_args, dict):
                _send(_err(req_id, -32602, "Invalid params: 'arguments' must be an object"))
                continue
            call_inputs: dict = _raw_args if isinstance(_raw_args, dict) else {}

            if call_name != TOOL_NAME:
                _send(_err(req_id, -32602,
                           f"Unknown tool '{call_name}'; this server exposes '{TOOL_NAME}'"))
                continue

            try:
                result = _handle_call(call_inputs, args.memory_root)
            except Exception as exc:  # noqa: BLE001
                _send(_ok(req_id, {
                    "content": [{"type": "text",
                                 "text": json.dumps({"error": str(exc)})}],
                    "isError": True,
                }))
                continue

            _send(_ok(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                "isError": "error" in result,
            }))

        else:
            _send(_err(req_id, -32601, f"Method not found: {method}"))


if __name__ == "__main__":
    main()
