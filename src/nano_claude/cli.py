"""v3 — Permission confirmation + bash safety."""

from __future__ import annotations

import os
import sys
from typing import Any

from dotenv import load_dotenv

load_dotenv(override=False)

import anthropic
from rich.console import Console
from rich.markdown import Markdown

from .api import create_client, stream_message
from .tools import all_tools
from .permissions import classify_tool_risk, ask_permission
from .types import Config

SYSTEM_PROMPT = """\
You are an AI coding assistant. You help users with software engineering tasks.

# Tool Usage
- Use Read to read files before editing. Never edit a file you haven't read.
- Use Edit for modifying existing files. Use Write only for new files or complete rewrites.
- Use Glob to find files by name pattern. Use Grep to search file contents.
- Use Bash for shell commands. Prefer dedicated tools over shell equivalents.

# Response Style
- Be concise and direct. Keep changes minimal and focused.
- Use markdown formatting when helpful."""

console = Console(stderr=True)
out = Console()


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY not set. Add it to .env or environment.[/red]")
        sys.exit(1)

    config = Config(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        max_tokens=16384,
        system_prompt=SYSTEM_PROMPT,
    )
    client = create_client(config)
    messages: list[dict[str, Any]] = []
    tool_map = {t.name: t for t in all_tools}

    out.print(f"\n  [bold cyan]nano-claude[/bold cyan] [dim]v2 (model: {config.model})[/dim]")
    out.print("[dim]  Type your message. Ctrl+C to exit.\n[/dim]")

    try:
        while True:
            try:
                user_input = input("\033[32mYou: \033[0m").strip()
            except EOFError:
                break
            if not user_input:
                continue

            messages.append({"role": "user", "content": user_input})

            # ── Agentic loop ──
            while True:
                # Two-pass: stream raw text first, then re-render with markdown
                text_buffer = ""
                sys.stdout.write("\033[34mAssistant: \033[0m")
                sys.stdout.flush()

                response = stream_message(
                    client, config, messages, all_tools,
                    on_text=lambda delta: (sys.stdout.write(delta), sys.stdout.flush()),
                )

                # Collect text from response
                for block in response.content:
                    if block.get("type") == "text":
                        text_buffer += block.get("text", "")

                # Re-render with markdown
                if text_buffer.strip():
                    raw_lines = text_buffer.count("\n") + 1
                    sys.stdout.write("\r\033[K")
                    for _ in range(raw_lines):
                        sys.stdout.write("\033[A\033[K")
                    sys.stdout.flush()
                    out.print("[blue]Assistant:[/blue]")
                    out.print(Markdown(text_buffer))

                messages.append({"role": "assistant", "content": response.content})

                # Find tool_use blocks
                tool_uses = [b for b in response.content if b.get("type") == "tool_use"]
                if not tool_uses:
                    break

                # Execute tools
                tool_results: list[dict[str, Any]] = []
                for tu in tool_uses:
                    tool = tool_map.get(tu["name"])
                    console.print(
                        f"\n  [dim][tool][/dim] [yellow]{tu['name']}[/yellow]"
                        f" [dim]{_format_input(tu)}[/dim]"
                    )

                    if not tool:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": f'Error: Unknown tool "{tu["name"]}"',
                            "is_error": True,
                        })
                        continue

                    # Permission check
                    tool_input = tu.get("input", {})
                    risk = classify_tool_risk(tu["name"], tool_input)
                    if risk != "safe":
                        if not ask_permission(tu["name"], tool_input, risk):
                            console.print("[red]  [denied][/red]")
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tu["id"],
                                "content": "Permission denied by user.",
                                "is_error": True,
                            })
                            continue

                    try:
                        result = tool.call(**tu.get("input", {}))
                        if len(result) > 80_000:
                            result = result[:40_000] + "\n...[truncated]...\n" + result[-40_000:]
                        console.print(f"  [dim][result] {result.count(chr(10)) + 1} lines[/dim]")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": result,
                        })
                    except Exception as e:
                        console.print(f"  [red][error] {e}[/red]")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": f"Error: {e}",
                            "is_error": True,
                        })

                messages.append({"role": "user", "content": tool_results})

            print()
    except KeyboardInterrupt:
        pass

    console.print("[dim]\nBye![/dim]")


def _format_input(tu: dict[str, Any]) -> str:
    inp = tu.get("input", {})
    first_key = next(iter(inp), None)
    if not first_key:
        return ""
    val = str(inp[first_key] or "")
    return f"{first_key}={val[:77] + '...' if len(val) > 80 else val}"
