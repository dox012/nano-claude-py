"""v5 — Smart conversation compaction."""

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
from .session import (
    new_session_id, save_session, load_session, print_session_list,
)
from .compact import smart_compact, should_auto_compact, estimate_tokens
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


class App:
    def __init__(self) -> None:
        self.config = Config(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=16384,
            system_prompt=SYSTEM_PROMPT,
        )
        self.client = create_client(self.config)
        self.messages: list[dict[str, Any]] = []
        self.total_input = 0
        self.total_output = 0
        self.session_id = new_session_id()

    def run_conversation_loop(self) -> None:
        tool_map = {t.name: t for t in all_tools}

        while True:
            # Auto-compact if context is getting large
            if should_auto_compact(self.messages):
                console.print("[yellow]\n  [auto-compact] Context window filling up...[/yellow]")
                try:
                    compacted, saved = smart_compact(self.client, self.config, self.messages)
                    self.messages[:] = compacted
                    console.print(f"[yellow]  [auto-compact] Saved {saved} messages[/yellow]")
                except Exception as e:
                    console.print(f"[red]  [auto-compact failed] {e}[/red]")

            text_buffer = ""
            sys.stdout.write("\033[34mAssistant: \033[0m")
            sys.stdout.flush()

            response = stream_message(
                self.client, self.config, self.messages, all_tools,
                on_text=lambda delta: (sys.stdout.write(delta), sys.stdout.flush()),
            )

            for block in response.content:
                if block.get("type") == "text":
                    text_buffer += block.get("text", "")

            if text_buffer.strip():
                raw_lines = text_buffer.count("\n") + 1
                sys.stdout.write("\r\033[K")
                for _ in range(raw_lines):
                    sys.stdout.write("\033[A\033[K")
                sys.stdout.flush()
                out.print("[blue]Assistant:[/blue]")
                out.print(Markdown(text_buffer))

            self.total_input += response.usage.get("input", 0)
            self.total_output += response.usage.get("output", 0)
            self.messages.append({"role": "assistant", "content": response.content})

            tool_uses = [b for b in response.content if b.get("type") == "tool_use"]
            if not tool_uses:
                break

            tool_results: list[dict[str, Any]] = []
            for tu in tool_uses:
                tool = tool_map.get(tu["name"])
                console.print(
                    f"\n  [dim][tool][/dim] [yellow]{tu['name']}[/yellow]"
                    f" [dim]{_format_input(tu)}[/dim]"
                )

                if not tool:
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tu["id"],
                        "content": f'Error: Unknown tool "{tu["name"]}"', "is_error": True,
                    })
                    continue

                tool_input = tu.get("input", {})
                risk = classify_tool_risk(tu["name"], tool_input)
                if risk != "safe":
                    if not ask_permission(tu["name"], tool_input, risk):
                        console.print("[red]  [denied][/red]")
                        tool_results.append({
                            "type": "tool_result", "tool_use_id": tu["id"],
                            "content": "Permission denied by user.", "is_error": True,
                        })
                        continue

                try:
                    result = tool.call(**tool_input)
                    if len(result) > 80_000:
                        result = result[:40_000] + "\n...[truncated]...\n" + result[-40_000:]
                    console.print(f"  [dim][result] {result.count(chr(10)) + 1} lines[/dim]")
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tu["id"], "content": result,
                    })
                except Exception as e:
                    console.print(f"  [red][error] {e}[/red]")
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tu["id"],
                        "content": f"Error: {e}", "is_error": True,
                    })

            self.messages.append({"role": "user", "content": tool_results})

    def save(self) -> None:
        save_session(
            self.session_id, self.messages, self.config.model,
            self.total_input, self.total_output,
        )

    def handle_command(self, user_input: str) -> None:
        cmd = user_input.split()[0].lower()

        if cmd == "/help":
            out.print("[cyan]\nCommands:[/cyan]")
            out.print("  /help      Show this help")
            out.print("  /cost      Show token usage")
            out.print("  /clear     Clear conversation history")
            out.print("  /compact   Summarize conversation to save context")
            out.print("  /model     Show or change model")
            out.print("  /sessions  List saved sessions")
            out.print("  /resume    Resume a saved session")

        elif cmd == "/cost":
            out.print(f"[cyan]\nTokens: {self.total_input} in / {self.total_output} out[/cyan]")
            out.print(f"[dim]Messages: {len(self.messages)}[/dim]")

        elif cmd == "/clear":
            self.messages.clear()
            self.total_input = 0
            self.total_output = 0
            out.print("[yellow]Conversation cleared.[/yellow]")

        elif cmd == "/compact":
            if len(self.messages) <= 4:
                out.print("[dim]Nothing to compact.[/dim]")
                return
            try:
                compacted, saved = smart_compact(self.client, self.config, self.messages)
                self.messages[:] = compacted
                tokens = estimate_tokens(self.messages)
                out.print(
                    f"[yellow]Compacted: {len(self.messages) + saved} -> "
                    f"{len(self.messages)} messages (~{tokens} tokens)[/yellow]"
                )
            except Exception as e:
                out.print(f"[red]Compact failed: {e}[/red]")

        elif cmd == "/model":
            arg = user_input[len("/model"):].strip()
            if arg:
                self.config.model = arg
                out.print(f"[cyan]Model set to: {arg}[/cyan]")
            else:
                out.print(f"[cyan]Current model: {self.config.model}[/cyan]")

        elif cmd == "/sessions":
            print_session_list()

        elif cmd == "/resume":
            resume_id = user_input[len("/resume"):].strip()
            if not resume_id:
                print_session_list()
                return
            session = load_session(resume_id)
            if not session:
                out.print(f"[red]Session not found: {resume_id}[/red]")
                return
            self.messages[:] = session["messages"]
            self.total_input = session.get("totalInput", 0)
            self.total_output = session.get("totalOutput", 0)
            self.session_id = session["id"]
            self.config.model = session.get("model", self.config.model)
            out.print(f"[green]Resumed session {resume_id} ({session.get('messageCount', '?')} messages)[/green]")

        else:
            out.print(f"[red]Unknown command: {cmd}. Type /help for commands.[/red]")


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY not set. Add it to .env or environment.[/red]")
        sys.exit(1)

    app = App()
    out.print(f"\n  [bold cyan]nano-claude[/bold cyan] [dim]v4 (model: {app.config.model})[/dim]")
    out.print("[dim]  Type your message. /help for commands, Ctrl+C to exit.\n[/dim]")

    try:
        while True:
            try:
                user_input = input("\033[32mYou: \033[0m").strip()
            except EOFError:
                break
            if not user_input:
                continue

            if user_input.startswith("/"):
                app.handle_command(user_input)
                continue

            app.messages.append({"role": "user", "content": user_input})

            try:
                app.run_conversation_loop()
            except Exception as e:
                console.print(f"[red]\nError: {e}[/red]")

            app.save()
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
