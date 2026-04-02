"""v0 — Chatbot baseline: streaming REPL, no tools."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv(override=False)

import anthropic


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set. Add it to .env or environment.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(
        api_key=api_key,
        base_url=os.environ.get("ANTHROPIC_BASE_URL") or None,
    )
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    messages: list[dict] = []

    print("\n  nano-claude v0 (chatbot baseline)")
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

            sys.stdout.write("\033[34mAssistant: \033[0m")
            sys.stdout.flush()

            with client.messages.stream(
                model=model,
                max_tokens=4096,
                system="You are a helpful coding assistant. Be concise and direct.",
                messages=messages,
            ) as stream:
                full_text = ""
                for text in stream.text_stream:
                    sys.stdout.write(text)
                    sys.stdout.flush()
                    full_text += text

            print("\n")
            messages.append({"role": "assistant", "content": full_text})
    except KeyboardInterrupt:
        pass

    print("\nBye!")
