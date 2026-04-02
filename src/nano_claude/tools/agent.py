"""Sub-agent tool: spawns isolated read-only research conversations."""

from __future__ import annotations

from typing import Any

import anthropic
from rich.console import Console

from ..types import ToolDef

console = Console(stderr=True)

# Set by cli.py at startup
_client: anthropic.Anthropic | None = None
_model: str = ""
_system_prompt: str = ""

AGENT_TOOL_NAMES = {"Read", "Glob", "Grep"}


def init_agent_tool(client: anthropic.Anthropic, model: str, system_prompt: str) -> None:
    global _client, _model, _system_prompt
    _client = client
    _model = model
    _system_prompt = system_prompt


def _call(*, prompt: str, description: str = "research", **_: object) -> str:
    if not _client:
        return "Error: Agent not initialized"

    console.print(f"  [dim][agent:{description}] Starting...[/dim]")

    # Import here to avoid circular deps
    from . import all_tools

    agent_tools = [t for t in all_tools if t.name in AGENT_TOOL_NAMES]
    sdk_tools = [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in agent_tools
    ]
    tool_map = {t.name: t for t in agent_tools}

    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

    agent_system = (
        "You are a research sub-agent. Your job is to investigate and report findings. "
        "You can only read files and search — you cannot modify anything. "
        "Be thorough but concise. Report your findings clearly.\n\n"
        + _system_prompt
    )

    MAX_TURNS = 20
    final_text = ""

    for _turn in range(MAX_TURNS):
        response = _client.messages.create(
            model=_model,
            max_tokens=8192,
            system=agent_system,
            messages=messages,
            tools=sdk_tools,
        )

        # Convert response content to serializable dicts
        content_dicts = []
        for block in response.content:
            if hasattr(block, "model_dump"):
                content_dicts.append(block.model_dump())
            else:
                content_dicts.append({"type": "text", "text": str(block)})

        messages.append({"role": "assistant", "content": content_dicts})

        # Collect text
        for block in response.content:
            if block.type == "text":
                final_text += block.text

        # Find tool uses
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            break

        # Execute tools
        tool_results = []
        for tu in tool_uses:
            tool = tool_map.get(tu.name)
            console.print(f"  [dim][agent:{description}] {tu.name}[/dim]")

            if not tool:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": f'Error: Tool "{tu.name}" not available to sub-agents',
                    "is_error": True,
                })
                continue

            try:
                inp = tu.input if isinstance(tu.input, dict) else {}
                result = tool.call(**inp)
                if len(result) > 30_000:
                    result = result[:15_000] + "\n...[truncated]...\n" + result[-15_000:]
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": result,
                })
            except Exception as e:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": f"Error: {e}",
                    "is_error": True,
                })

        messages.append({"role": "user", "content": tool_results})

    console.print(f"  [dim][agent:{description}] Done[/dim]")
    return final_text or "(Agent produced no text output)"


AgentTool = ToolDef(
    name="Agent",
    description=(
        "Launch a sub-agent to perform a focused research task. The agent can read files "
        "and search the codebase but cannot modify files or run commands. Use this for "
        "parallel exploration, code analysis, or gathering information from multiple files."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The task for the sub-agent to perform",
            },
            "description": {
                "type": "string",
                "description": "A short (3-5 word) description of the task",
            },
        },
        "required": ["prompt", "description"],
    },
    _call=_call,
)
