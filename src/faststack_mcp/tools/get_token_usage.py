from __future__ import annotations

import json
from pathlib import Path

# claude-sonnet-4-6 pricing (USD per million tokens)
_PRICE = {
    "input": 3.00,
    "output": 15.00,
    "cache_read": 0.30,
    "cache_write": 3.75,
}

# Approximate per-call token savings vs reading full files
_TOOL_SAVINGS_HEURISTIC = {
    "get_symbol": 7_600,       # avg symbol ~400 tokens vs avg file ~8k
    "search_symbols": 5_000,   # returns ranked list vs loading all symbols
    "get_file_outline": 3_000, # symbol names only vs file content
    "get_project_outline": 10_000,  # counts vs full index
    "index_folder": 0,         # produces savings for future calls
    "search_text": 2_000,
    "get_file_context": 1_000,
    "find_references": 2_500,
}


def _token_log_path() -> Path:
    from ..storage import cache_root
    return cache_root() / "token_usage.jsonl"


def _cost(input_t: int, output_t: int, cache_read: int, cache_write: int) -> float:
    return (
        (input_t / 1_000_000) * _PRICE["input"]
        + (output_t / 1_000_000) * _PRICE["output"]
        + (cache_read / 1_000_000) * _PRICE["cache_read"]
        + (cache_write / 1_000_000) * _PRICE["cache_write"]
    )


def run(last_n: int = 20, session_id: str | None = None) -> dict:
    """Show token consumption per session with per-tool breakdown and savings estimate."""
    log_path = _token_log_path()
    if not log_path.exists():
        return {
            "status": "no_data",
            "message": (
                "No token usage data yet. Configure the Stop hook in ~/.claude/settings.json "
                "and complete at least one session."
            ),
            "log_path": str(log_path),
            "entries": [],
        }

    raw: list[dict] = []
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if session_id:
        raw = [e for e in raw if e.get("session_id") == session_id]

    entries = list(reversed(raw))[:last_n]

    total_input = sum(e.get("input_tokens", 0) for e in entries)
    total_output = sum(e.get("output_tokens", 0) for e in entries)
    total_cache_read = sum(e.get("cache_read_input_tokens", 0) for e in entries)
    total_cache_write = sum(e.get("cache_creation_input_tokens", 0) for e in entries)
    total_cost = _cost(total_input, total_output, total_cache_read, total_cache_write)

    # Per-tool call stats (populated if hook logs tool_calls field)
    tool_stats: dict[str, dict] = {}
    for e in entries:
        for call in e.get("tool_calls", []):
            tool = call.get("tool", "unknown")
            ts = tool_stats.setdefault(tool, {"calls": 0, "est_tokens": 0, "est_saved": 0})
            ts["calls"] += 1
            ts["est_tokens"] += call.get("tokens", 0)
            ts["est_saved"] += _TOOL_SAVINGS_HEURISTIC.get(tool, 0)

    # Heuristic total savings if no per-call data
    if not tool_stats:
        total_saved_heuristic = None
    else:
        total_saved_heuristic = sum(v["est_saved"] for v in tool_stats.values())

    # Session comparison: first vs last in window
    avg_cost = total_cost / len(entries) if entries else 0.0
    avg_input = total_input // max(len(entries), 1)
    avg_output = total_output // max(len(entries), 1)

    return {
        "status": "ok",
        "entries_shown": len(entries),
        "total_sessions_logged": len(raw),
        "totals": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cache_read_input_tokens": total_cache_read,
            "cache_creation_input_tokens": total_cache_write,
            "estimated_cost_usd": round(total_cost, 6),
        },
        "averages": {
            "input_tokens_per_session": avg_input,
            "output_tokens_per_session": avg_output,
            "cost_usd_per_session": round(avg_cost, 6),
        },
        "tool_breakdown": tool_stats or None,
        "estimated_tokens_saved_by_mcp": total_saved_heuristic,
        "entries": entries,
        "log_path": str(log_path),
    }
