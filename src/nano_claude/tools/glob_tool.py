"""File pattern matching tool."""

import os
from pathlib import Path

from ..types import ToolDef

# Patterns to ignore
IGNORE_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv"}


def _glob_recursive(base: Path, pattern: str, max_results: int = 200) -> list[str]:
    """Glob with ignore support using pathlib."""
    results: list[str] = []
    for match in sorted(base.glob(pattern)):
        # Skip ignored directories
        parts = match.relative_to(base).parts
        if any(p in IGNORE_DIRS for p in parts):
            continue
        if match.is_file():
            results.append(str(match.relative_to(base)))
            if len(results) >= max_results:
                break
    return results


def _call(*, pattern: str, path: str | None = None, **_: object) -> str:
    search_path = Path(path).resolve() if path else Path.cwd()

    files = _glob_recursive(search_path, pattern)

    if not files:
        return f"No files found matching: {pattern}"

    MAX = 200
    truncated = len(files) > MAX
    shown = files[:MAX]

    result = "\n".join(shown)
    if truncated:
        result += f"\n\n({len(files)} total, showing first {MAX})"
    else:
        result += f"\n\n({len(files)} files)"
    return result


GlobTool = ToolDef(
    name="Glob",
    description=(
        "Find files by glob pattern. Returns matching file paths. "
        "Use for finding files by name or extension (e.g. '**/*.ts', 'src/**/*.test.js')."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match (e.g. '**/*.ts')",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (default: cwd)",
            },
        },
        "required": ["pattern"],
    },
    _call=_call,
)
