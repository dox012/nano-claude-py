"""String-replacement editing tool."""

from pathlib import Path

from ..types import ToolDef


def _call(
    *, file_path: str, old_string: str, new_string: str, replace_all: bool = False, **_: object
) -> str:
    p = Path(file_path).resolve()

    if not p.exists():
        return f"Error: File not found: {p}"

    if old_string == new_string:
        return "Error: old_string and new_string are identical"

    content = p.read_text(encoding="utf-8")

    if old_string not in content:
        return (
            f"Error: old_string not found in {p}. "
            "Make sure the string matches exactly (including whitespace and indentation)."
        )

    if not replace_all:
        count = content.count(old_string)
        if count > 1:
            return (
                f"Error: old_string appears {count} times in the file. "
                "Use replace_all: true or provide more context to make it unique."
            )

    if replace_all:
        replacements = content.count(old_string)
        updated = content.replace(old_string, new_string)
    else:
        replacements = 1
        updated = content.replace(old_string, new_string, 1)

    p.write_text(updated, encoding="utf-8")
    return f"Edited {p}: {replacements} replacement(s) made"


EditTool = ToolDef(
    name="Edit",
    description=(
        "Edit an existing file by replacing an exact string match with new content. "
        "The old_string must be unique in the file unless replace_all is true. "
        "Read the file first before editing."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file to modify",
            },
            "old_string": {
                "type": "string",
                "description": "The exact text to replace",
            },
            "new_string": {
                "type": "string",
                "description": "The replacement text",
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences (default: false)",
                "default": False,
            },
        },
        "required": ["file_path", "old_string", "new_string"],
    },
    _call=_call,
)
