"""Main entry point: CLI argument parsing, REPL, agentic loop, slash commands."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from dotenv import load_dotenv

# Load .env before anything else
load_dotenv(override=False)

import anthropic
from rich.console import Console
from rich.markdown import Markdown

from .api import create_client, stream_message
from .tools import all_tools
from .tools.agent import init_agent_tool
from .prompt import build_system_prompt
from .permissions import classify_tool_risk, ask_permission
from .session import (
    new_session_id, save_session, load_session,
    list_sessions, print_session_list,
)
from .compact import smart_compact, should_auto_compact, estimate_tokens
from .memory import save_memory, delete_memory, print_memories
from .types import Config

VERSION = "0.1.0"

console = Console(stderr=True)
out = Console()  # stdout


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="nano-claude",
        description="Lightweight Claude Code reimplementation in Python",
        add_help=False,
    )
    parser.add_argument("-p", "--print", action="store_true", dest="print_mode",
                        help="Non-interactive mode: output text only, then exit")
    parser.add_argument("-c", "--continue", action="store_true", dest="continue_",
                        help="Continue most recent conversation")
    parser.add_argument("-r", "--resume", type=str, default=None,
                        help="Resume a specific session by ID")
    parser.add_argument("-m", "--model", type=str, default=None,
                        help="Override the model name")
    parser.add_argument("--max-turns", type=int, default=None,
                        help="Maximum agentic turns (default: unlimited)")
    parser.add_argument("--dangerously-skip-permissions", action="store_true",
                        help="Skip all permission prompts")
    parser.add_argument("-h", "--help", action="store_true", dest="show_help",
                        help="Show help")
    parser.add_argument("-v", "--version", action="store_true",
                        help="Show version")
    parser.add_argument("prompt", nargs="*", help="Inline prompt")
    return parser.parse_args()


def print_help() -> None:
    out.print(f"""
[bold cyan]nano-claude[/bold cyan] [dim]v{VERSION}[/dim] — lightweight Claude Code reimplementation (Python)

[bold]Usage:[/bold]
  nano-claude [options] [prompt]

[bold]Options:[/bold]
  -p, --print          Non-interactive mode (output text only, then exit)
  -c, --continue       Continue most recent conversation
  -r, --resume <id>    Resume a specific session by ID
  -m, --model <model>  Override the model name
  --max-turns <n>      Maximum agentic turns (default: unlimited, useful with -p)
  --dangerously-skip-permissions  Skip all permission prompts
  -h, --help           Show this help
  -v, --version        Show version

[bold]Examples:[/bold]
  nano-claude                          # interactive REPL
  nano-claude "explain this project"   # interactive with initial prompt
  nano-claude -p "list all TODOs"      # non-interactive, print result and exit
  nano-claude -c                       # continue last conversation

[bold]Environment:[/bold]
  ANTHROPIC_API_KEY      API key (or set in .env)
  ANTHROPIC_BASE_URL     API base URL for proxies
  ANTHROPIC_MODEL        Default model name
""")


class App:
    """Application state — holds everything the REPL needs."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.messages: list[dict[str, Any]] = []
        self.total_input = 0
        self.total_output = 0
        self.session_id = new_session_id()
        self.max_turns = args.max_turns if args.max_turns is not None else float("inf")

        self.config = Config(
            model=args.model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=16384,
            system_prompt="",
        )

        self.config.system_prompt = build_system_prompt()
        self.client = create_client(self.config)
        init_agent_tool(self.client, self.config.model, self.config.system_prompt)

    # ── Core agentic loop ──

    def run_conversation_loop(self) -> None:
        tool_map = {t.name: t for t in all_tools}
        turns = 0

        while True:
            if turns >= self.max_turns:
                if not self.args.print_mode:
                    console.print("[yellow]\n  [max-turns] Reached limit[/yellow]")
                break
            turns += 1

            # Auto-compact
            if should_auto_compact(self.messages):
                if not self.args.print_mode:
                    console.print("[yellow]\n  [auto-compact] Context window filling up...[/yellow]")
                try:
                    compacted, saved = smart_compact(self.client, self.config, self.messages)
                    self.messages[:] = compacted
                    if not self.args.print_mode:
                        console.print(f"[yellow]  [auto-compact] Saved {saved} messages[/yellow]")
                except Exception as e:
                    if not self.args.print_mode:
                        console.print(f"[red]  [auto-compact failed] {e}[/red]")

            # Stream response
            text_buffer = ""
            if not self.args.print_mode:
                sys.stdout.write("\033[34mAssistant: \033[0m")
                sys.stdout.flush()

            response = stream_message(
                self.client,
                self.config,
                self.messages,
                all_tools,
                on_text=lambda delta: self._on_text(delta),
            )

            # Collect text from response
            for block in response.content:
                if block.get("type") == "text":
                    text_buffer += block.get("text", "")

            # Re-render with markdown (interactive mode only)
            if text_buffer.strip() and not self.args.print_mode:
                raw_lines = text_buffer.count("\n") + 1
                # Erase raw streamed text
                sys.stdout.write("\r\033[K")
                for _ in range(raw_lines):
                    sys.stdout.write("\033[A\033[K")
                sys.stdout.flush()
                out.print("[blue]Assistant:[/blue]")
                out.print(Markdown(text_buffer))
            elif text_buffer.strip() and self.args.print_mode:
                sys.stdout.write("\n")
                sys.stdout.flush()

            self.total_input += response.usage.get("input", 0)
            self.total_output += response.usage.get("output", 0)

            # Add assistant response to history
            self.messages.append({"role": "assistant", "content": response.content})

            # Find tool_use blocks
            tool_uses = [b for b in response.content if b.get("type") == "tool_use"]
            if not tool_uses:
                break

            # Execute tools
            tool_results: list[dict[str, Any]] = []

            for tu in tool_uses:
                tool = tool_map.get(tu["name"])
                if not self.args.print_mode:
                    console.print(
                        f"\n  [dim][tool][/dim] [yellow]{tu['name']}[/yellow]"
                        f" [dim]{_format_tool_input(tu)}[/dim]"
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
                    auto = self.args.print_mode or self.args.dangerously_skip_permissions
                    allowed = True if auto else ask_permission(tu["name"], tool_input, risk)
                    if not allowed:
                        if not self.args.print_mode:
                            console.print("[red]  [denied][/red]")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": "Permission denied by user.",
                            "is_error": True,
                        })
                        continue

                try:
                    result = tool.call(**tool_input)
                    if len(result) > 80_000:
                        result = result[:40_000] + "\n...[truncated]...\n" + result[-40_000:]
                    if not self.args.print_mode:
                        console.print(f"  [dim][result] {result.count(chr(10)) + 1} lines[/dim]")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu["id"],
                        "content": result,
                    })
                except Exception as e:
                    err_msg = str(e)
                    if not self.args.print_mode:
                        console.print(f"  [red][error] {err_msg}[/red]")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu["id"],
                        "content": f"Error: {err_msg}",
                        "is_error": True,
                    })

            self.messages.append({"role": "user", "content": tool_results})

    def _on_text(self, delta: str) -> None:
        sys.stdout.write(delta)
        sys.stdout.flush()

    # ── Slash commands ──

    def handle_command(self, user_input: str) -> None:
        parts = user_input.split()
        cmd = parts[0].lower()

        if cmd == "/help":
            out.print("[cyan]\nCommands:[/cyan]")
            out.print("  /help      Show this help")
            out.print("  /cost      Show token usage")
            out.print("  /clear     Clear conversation history")
            out.print("  /compact   Summarize conversation to save context")
            out.print("  /model     Show or change model")
            out.print("  /sessions  List saved sessions")
            out.print("  /resume    Resume a saved session")
            out.print("  /remember  Save a memory (/remember key: content)")
            out.print("  /forget    Delete a memory (/forget key)")
            out.print("  /memory    List saved memories")

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

        elif cmd == "/remember":
            body = user_input[len("/remember"):].strip()
            colon_idx = body.find(":")
            if not body or colon_idx == -1:
                out.print("[dim]  Usage: /remember key: content[/dim]")
                return
            key = body[:colon_idx].strip()
            content = body[colon_idx + 1:].strip()
            save_memory(key, content)
            out.print(f"[green]  Saved memory: {key}[/green]")
            self.config.system_prompt = build_system_prompt()

        elif cmd == "/forget":
            key = user_input[len("/forget"):].strip()
            if not key:
                out.print("[dim]  Usage: /forget key[/dim]")
                return
            if delete_memory(key):
                out.print(f"[yellow]  Deleted memory: {key}[/yellow]")
                self.config.system_prompt = build_system_prompt()
            else:
                out.print(f"[red]  Memory not found: {key}[/red]")

        elif cmd == "/memory":
            print_memories()

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

    # ── Session helpers ──

    def restore_session(self, session_data: dict[str, Any]) -> None:
        self.messages.extend(session_data["messages"])
        self.total_input = session_data.get("totalInput", 0)
        self.total_output = session_data.get("totalOutput", 0)
        self.session_id = session_data["id"]
        self.config.model = self.args.model or session_data.get("model", self.config.model)

    def save(self) -> None:
        save_session(
            self.session_id, self.messages, self.config.model,
            self.total_input, self.total_output,
        )


def _format_tool_input(tu: dict[str, Any]) -> str:
    inp = tu.get("input", {})
    if not inp:
        return ""
    first_key = next(iter(inp), None)
    if not first_key:
        return ""
    val = str(inp[first_key] or "")
    short = val[:77] + "..." if len(val) > 80 else val
    return f"{first_key}={short}"


def main() -> None:
    args = parse_args()

    if args.show_help:
        print_help()
        sys.exit(0)
    if args.version:
        print(VERSION)
        sys.exit(0)

    # Validate API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]Error: ANTHROPIC_API_KEY not set. Add it to .env or environment.[/red]")
        sys.exit(1)

    app = App(args)
    inline_prompt = " ".join(args.prompt) if args.prompt else None

    # Handle --continue
    if args.continue_:
        sessions = list_sessions(1)
        if sessions:
            session = load_session(sessions[0]["id"])
            if session:
                app.restore_session(session)
                if not args.print_mode:
                    console.print(f"[green]  Resumed session {session['id']} ({session.get('messageCount', '?')} messages)[/green]")
        elif not args.print_mode:
            console.print("[dim]  No sessions to continue.[/dim]")

    # Handle --resume <id>
    if args.resume:
        session = load_session(args.resume)
        if not session:
            console.print(f"[red]Session not found: {args.resume}[/red]")
            sys.exit(1)
        app.restore_session(session)
        if not args.print_mode:
            console.print(f"[green]  Resumed session {session['id']} ({session.get('messageCount', '?')} messages)[/green]")

    # ── Print mode (non-interactive) ──
    if args.print_mode:
        if not inline_prompt and not args.continue_ and not args.resume:
            console.print("[red]Error: --print requires a prompt or --continue/--resume[/red]")
            sys.exit(1)
        if inline_prompt:
            app.messages.append({"role": "user", "content": inline_prompt})
        try:
            app.run_conversation_loop()
        except Exception as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(1)
        app.save()
        sys.exit(0)

    # ── Interactive REPL ──
    out.print(
        f"\n  [bold cyan]nano-claude[/bold cyan] [dim]v{VERSION}[/dim]"
        f" [dim](model: {app.config.model})[/dim]"
    )
    out.print("[dim]  Type your message. /help for commands, Ctrl+C to exit.\n[/dim]")

    # Handle inline prompt
    if inline_prompt:
        out.print(f"[green]You: [/green]{inline_prompt}")
        app.messages.append({"role": "user", "content": inline_prompt})
        try:
            app.run_conversation_loop()
        except Exception as e:
            console.print(f"[red]\nError: {e}[/red]")
        app.save()
        print()

    # REPL loop
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
