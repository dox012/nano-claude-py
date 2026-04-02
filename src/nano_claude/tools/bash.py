"""Shell command execution tool."""

import os
import subprocess

from ..types import ToolDef

MAX_OUTPUT = 50_000


def _truncate(s: str) -> str:
    if len(s) <= MAX_OUTPUT:
        return s
    half = MAX_OUTPUT // 2
    return s[:half] + "\n\n... [truncated] ...\n\n" + s[-half:]


def _call(*, command: str, timeout: int = 120_000, **_: object) -> str:
    timeout_sec = timeout / 1000
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=os.getcwd(),
        )
        output = result.stdout
        if result.returncode != 0:
            parts: list[str] = []
            if result.stdout:
                parts.append(result.stdout)
            if result.stderr:
                parts.append(result.stderr)
            parts.append(f"Exit code: {result.returncode}")
            output = "\n".join(parts)
        return _truncate(output or "(no output)")
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout_sec}s"
    except Exception as e:
        return f"Error: {e}"


BashTool = ToolDef(
    name="Bash",
    description=(
        "Execute a bash command. Use for running shell commands, installing packages, "
        "git operations, etc. Prefer dedicated tools (Read, Edit, Write, Glob, Grep) "
        "over cat/sed/find/grep when possible."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute",
            },
            "timeout": {
                "type": "number",
                "description": "Timeout in milliseconds (default 120000)",
            },
        },
        "required": ["command"],
    },
    _call=_call,
)
