"""File reading tool with line numbers."""

import os
from pathlib import Path

from ..types import ToolDef


def _call(*, file_path: str, offset: int = 0, limit: int = 2000, **_: object) -> str:
    p = Path(file_path).resolve()

    if not p.exists():
        return f"Error: File not found: {p}"

    if p.is_dir():
        return f"Error: {p} is a directory, not a file. Use Bash with 'ls' to list directory contents."

    size = p.stat().st_size
    if size > 5 * 1024 * 1024 and offset == 0 and limit == 2000:
        return f"Error: File is {size / 1024 / 1024:.1f}MB. Use offset/limit to read a portion."

    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"

    lines = content.split("\n")
    total = len(lines)
    sliced = lines[offset : offset + limit]

    numbered = "\n".join(f"{offset + i + 1}\t{line}" for i, line in enumerate(sliced))

    result = numbered
    if offset + limit < total:
        result += f"\n\n(Showing lines {offset + 1}-{offset + len(sliced)} of {total} total)"
    return result


ReadTool = ToolDef(
    name="Read",
    description=(
        "Read a file from the local filesystem. Returns content with line numbers. "
        "Supports offset/limit for reading portions of large files."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file to read",
            },
            "offset": {
                "type": "number",
                "description": "Line number to start reading from (0-based)",
            },
            "limit": {
                "type": "number",
                "description": "Number of lines to read (default: 2000)",
            },
        },
        "required": ["file_path"],
    },
    _call=_call,
)
