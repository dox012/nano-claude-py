"""Persistent key-value memory stored as markdown files."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

MEMORY_DIR = Path.home() / ".nano-claude" / "memory"

console = Console(stderr=True)


def _ensure_dir() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def save_memory(key: str, content: str) -> None:
    _ensure_dir()
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", key)[:80]
    path = MEMORY_DIR / f"{sanitized}.md"
    entry = f"---\nkey: {key}\ndate: {datetime.now(timezone.utc).isoformat()}\n---\n\n{content}\n"
    path.write_text(entry, encoding="utf-8")


def load_all_memories() -> str:
    _ensure_dir()
    files = sorted(MEMORY_DIR.glob("*.md"))
    if not files:
        return ""
    parts = [f.read_text(encoding="utf-8").strip() for f in files]
    return "\n\n---\n\n".join(parts)


def delete_memory(key: str) -> bool:
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", key)[:80]
    path = MEMORY_DIR / f"{sanitized}.md"
    if path.exists():
        path.unlink()
        return True
    return False


def list_memories() -> list[str]:
    _ensure_dir()
    return [f.stem for f in sorted(MEMORY_DIR.glob("*.md"))]


def print_memories() -> None:
    keys = list_memories()
    if not keys:
        console.print("  [dim]No saved memories.[/dim]")
        return
    console.print("\n[cyan]Memories:[/cyan]")
    for k in keys:
        console.print(f"  [dim]* {k}[/dim]")
