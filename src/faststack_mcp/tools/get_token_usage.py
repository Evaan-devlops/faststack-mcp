from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime


def _token_log_path() -> Path:
    from ..storage import cache_root
    return cache_root() / "token_usage.jsonl"


def run(last_n: int = 20, session_id: str | None = None) -> dict:
    """Read token usage log written by the Claude Code Stop hook."""
    log_path = _token_log_path()
    if not log_path.exists():
        return {
            "status": "no_data",
            "message": (
                "No token usage data yet. Make sure the Stop hook is configured in "
                "~/.claude/settings.json and at least one session has completed."
            ),
            "log_path": str(log_path),
            "entries": [],
        }

    entries: list[dict] = []
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if session_id:
        entries = [e for e in entries if e.get("session_id") == session_id]

    # most recent first
    entries = list(reversed(entries))[:last_n]

    # aggregate totals
    total_input = sum(e.get("input_tokens", 0) for e in entries)
    total_output = sum(e.get("output_tokens", 0) for e in entries)
    total_cache_read = sum(e.get("cache_read_input_tokens", 0) for e in entries)
    total_cache_write = sum(e.get("cache_creation_input_tokens", 0) for e in entries)

    # approximate cost (claude-sonnet-4-6 pricing)
    # $3/M input, $15/M output, $0.30/M cache read, $3.75/M cache write
    cost_usd = (
        (total_input / 1_000_000) * 3.00
        + (total_output / 1_000_000) * 15.00
        + (total_cache_read / 1_000_000) * 0.30
        + (total_cache_write / 1_000_000) * 3.75
    )

    return {
        "status": "ok",
        "entries_shown": len(entries),
        "totals": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cache_read_input_tokens": total_cache_read,
            "cache_creation_input_tokens": total_cache_write,
            "estimated_cost_usd": round(cost_usd, 6),
        },
        "entries": entries,
        "log_path": str(log_path),
    }
