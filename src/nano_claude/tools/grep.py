"""Content search tool using ripgrep with grep fallback."""

import os
import subprocess
import shlex
from pathlib import Path

from ..types import ToolDef


def _call(
    *, pattern: str, path: str | None = None, glob: str | None = None, include: str | None = None,
    **_: object,
) -> str:
    search_path = str(Path(path).resolve()) if path else os.getcwd()

    # Try rg first
    args = [
        "rg",
        "--hidden",
        "--glob=!.git",
        "--glob=!node_modules",
        "--glob=!__pycache__",
        "-n",
        "--max-columns=500",
        "--max-count=100",
    ]

    if glob:
        args.append(f"--glob={glob}")
    if include:
        args.append(f"--type={include}")

    args.append(pattern)
    args.append(search_path)

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if len(lines) > 200:
                return "\n".join(lines[:200]) + f"\n\n({len(lines)} total matches, showing first 200)"
            return result.stdout.strip() or "No matches found."
        elif result.returncode == 1 and not result.stderr.strip():
            return "No matches found."
        # rg failed — fall through to grep
    except FileNotFoundError:
        pass  # rg not installed
    except Exception:
        pass  # rg error

    # Fallback to grep
    try:
        glob_filter = glob or "*"
        cmd = f"grep -rn --include='{glob_filter}' {shlex.quote(pattern)} {shlex.quote(search_path)} | head -200"
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip() or "No matches found."
    except Exception:
        return "No matches found."


GrepTool = ToolDef(
    name="Grep",
    description=(
        "Search file contents using ripgrep (rg). Supports regex patterns, file type filtering, "
        "and context lines. Falls back to grep if rg is not installed."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for",
            },
            "path": {
                "type": "string",
                "description": "File or directory to search in (default: cwd)",
            },
            "glob": {
                "type": "string",
                "description": "Glob to filter files (e.g. '*.ts')",
            },
            "include": {
                "type": "string",
                "description": "File extension filter (e.g. 'ts', 'py')",
            },
        },
        "required": ["pattern"],
    },
    _call=_call,
)
