"""Session persistence: save/load/list conversation sessions."""

from __future__ import annotations

import json
import os
import random
import string
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console

SESSION_DIR = Path.home() / ".nano-claude" / "sessions"

console = Console(stderr=True)


def _ensure_dir() -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)


def _session_path(session_id: str) -> Path:
    return SESSION_DIR / f"{session_id}.json"


def new_session_id() -> str:
    now = datetime.now(timezone.utc)
    date_part = now.strftime("%Y%m%d")
    time_part = now.strftime("%H%M%S")
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{date_part}-{time_part}-{rand}"


def save_session(
    session_id: str,
    messages: list[dict[str, Any]],
    model: str,
    total_input: int,
    total_output: int,
) -> None:
    _ensure_dir()
    first_msg = _get_first_user_message(messages)
    path = _session_path(session_id)

    # Preserve original createdAt
    created_at = datetime.now(timezone.utc).isoformat()
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            created_at = old.get("createdAt", created_at)
        except Exception:
            pass

    data = {
        "id": session_id,
        "cwd": os.getcwd(),
        "model": model,
        "createdAt": created_at,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "messageCount": len(messages),
        "firstMessage": first_msg[:100],
        "messages": messages,
        "totalInput": total_input,
        "totalOutput": total_output,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_session(session_id: str) -> dict[str, Any] | None:
    path = _session_path(session_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_sessions(limit: int = 10) -> list[dict[str, Any]]:
    _ensure_dir()
    files = sorted(SESSION_DIR.glob("*.json"), reverse=True)[:limit]
    sessions = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            sessions.append({
                "id": data["id"],
                "cwd": data.get("cwd", ""),
                "model": data.get("model", ""),
                "createdAt": data.get("createdAt", ""),
                "updatedAt": data.get("updatedAt", ""),
                "messageCount": data.get("messageCount", 0),
                "firstMessage": data.get("firstMessage", ""),
            })
        except Exception:
            continue
    return sessions


def print_session_list() -> None:
    sessions = list_sessions()
    if not sessions:
        console.print("  [dim]No saved sessions.[/dim]")
        return
    console.print("\n[cyan]Recent sessions:[/cyan]")
    for s in sessions:
        date_str = s["updatedAt"][:16].replace("T", " ")
        preview = s["firstMessage"][:50]
        console.print(
            f"  [dim]{s['id']}[/dim] [dim]({date_str})[/dim] "
            f"[dim][{s['messageCount']} msgs][/dim]  {preview}"
        )
    console.print("\n  [dim]Use /resume <id> to restore a session.[/dim]")


def _get_first_user_message(messages: list[dict[str, Any]]) -> str:
    for m in messages:
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            return m["content"]
    return "(no message)"
