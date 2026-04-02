"""File creation / overwrite tool."""

from pathlib import Path

from ..types import ToolDef


def _call(*, file_path: str, content: str, **_: object) -> str:
    p = Path(file_path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)

    existed = p.exists()
    p.write_text(content, encoding="utf-8")

    lines = content.count("\n") + 1
    if existed:
        return f"File overwritten: {p} ({lines} lines)"
    return f"File created: {p} ({lines} lines)"


WriteTool = ToolDef(
    name="Write",
    description=(
        "Create a new file or completely overwrite an existing file. "
        "Use Edit tool instead for partial modifications to existing files."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "The content to write to the file",
            },
        },
        "required": ["file_path", "content"],
    },
    _call=_call,
)
