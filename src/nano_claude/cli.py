"""v1 — MVP: REPL + 6 tools + streaming agentic loop."""

from __future__ import annotations

import os
import sys
from typing import Any

from dotenv import load_dotenv

load_dotenv(override=False)

import anthropic

from .api import create_client, stream_message
from .tools import all_tools
from .types import Config

SYSTEM_PROMPT = """\
You are an AI coding assistant. You help users with software engineering tasks.

# Tool Usage
- Use Read to read files before editing. Never edit a file you haven't read.
- Use Edit for modifying existing files. Use Write only for new files or complete rewrites.
- Use Glob to find files by name pattern. Use Grep to search file contents.
- Use Bash for shell commands. Prefer dedicated tools over shell equivalents.

# Response Style
- Be concise and direct. Keep changes minimal and focused."""


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set. Add it to .env or environment.", file=sys.stderr)
        sys.exit(1)

    config = Config(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        max_tokens=16384,
        system_prompt=SYSTEM_PROMPT,
    )
    client = create_client(config)
    messages: list[dict[str, Any]] = []
    tool_map = {t.name: t for t in all_tools}

    print(f"\n  nano-claude v1 (model: {config.model})")
    print("  Type your message. Ctrl+C to exit.\n")

    try:
        while True:
            try:
                user_input = input("\033[32mYou: \033[0m").strip()
            except EOFError:
                break
            if not user_input:
                continue

            messages.append({"role": "user", "content": user_input})

            # ── Agentic loop: call API → execute tools → repeat ──
            while True:
                sys.stdout.write("\033[34mAssistant: \033[0m")
                sys.stdout.flush()

                response = stream_message(
                    client, config, messages, all_tools,
                    on_text=lambda delta: (sys.stdout.write(delta), sys.stdout.flush()),
                )
                print()

                messages.append({"role": "assistant", "content": response.content})

                # Find tool_use blocks
                tool_uses = [b for b in response.content if b.get("type") == "tool_use"]
                if not tool_uses:
                    break

                # Execute tools
                tool_results: list[dict[str, Any]] = []
                for tu in tool_uses:
                    tool = tool_map.get(tu["name"])
                    print(f"\n  \033[2m[tool]\033[0m \033[33m{tu['name']}\033[0m \033[2m{_format_input(tu)}\033[0m")

                    if not tool:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": f'Error: Unknown tool "{tu["name"]}"',
                            "is_error": True,
                        })
                        continue

                    try:
                        result = tool.call(**tu.get("input", {}))
                        if len(result) > 80_000:
                            result = result[:40_000] + "\n...[truncated]...\n" + result[-40_000:]
                        print(f"  \033[2m[result] {result.count(chr(10)) + 1} lines\033[0m")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": result,
                        })
                    except Exception as e:
                        print(f"  \033[31m[error] {e}\033[0m")
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

    print("\nBye!")


def _format_input(tu: dict[str, Any]) -> str:
    inp = tu.get("input", {})
    first_key = next(iter(inp), None)
    if not first_key:
        return ""
    val = str(inp[first_key] or "")
    return f"{first_key}={val[:77] + '...' if len(val) > 80 else val}"
