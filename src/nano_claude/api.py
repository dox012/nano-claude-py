"""Anthropic SDK streaming wrapper."""

from __future__ import annotations

import json
import os
from typing import Any, Callable

import anthropic

from .types import Config, ApiResponse, ToolDef


def create_client(config: Config) -> anthropic.Anthropic:
    return anthropic.Anthropic(
        api_key=config.api_key or os.environ.get("ANTHROPIC_API_KEY", ""),
        base_url=config.base_url or os.environ.get("ANTHROPIC_BASE_URL") or None,
    )


def stream_message(
    client: anthropic.Anthropic,
    config: Config,
    messages: list[dict[str, Any]],
    tools: list[ToolDef],
    on_text: Callable[[str], None],
) -> ApiResponse:
    """Stream a single API call, printing text deltas in real-time."""

    sdk_tools = [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in tools
    ]

    blocks: list[dict[str, Any]] = []
    input_tokens = 0
    output_tokens = 0

    with client.messages.stream(
        model=config.model,
        max_tokens=config.max_tokens,
        system=config.system_prompt,
        messages=messages,
        tools=sdk_tools,
    ) as stream:
        for event in stream:
            match event.type:
                case "message_start":
                    input_tokens = getattr(event.message.usage, "input_tokens", 0)
                case "message_delta":
                    usage = getattr(event, "usage", None)
                    if usage:
                        output_tokens = getattr(usage, "output_tokens", output_tokens)
                case "content_block_start":
                    block = _block_to_dict(event.content_block)
                    blocks.append(block)
                case "content_block_delta":
                    if not blocks:
                        continue
                    block = blocks[-1]
                    delta = event.delta
                    delta_type = getattr(delta, "type", "")
                    if delta_type == "text_delta" and block.get("type") == "text":
                        block["text"] += delta.text
                        on_text(delta.text)
                    elif delta_type == "input_json_delta" and block.get("type") == "tool_use":
                        block["_partial_json"] = block.get("_partial_json", "") + delta.partial_json
                case "content_block_stop":
                    if not blocks:
                        continue
                    block = blocks[-1]
                    if block.get("type") == "tool_use" and block.get("_partial_json"):
                        try:
                            block["input"] = json.loads(block["_partial_json"])
                        except json.JSONDecodeError:
                            pass
                        block.pop("_partial_json", None)

        final = stream.get_final_message()

    return ApiResponse(
        content=blocks,
        stop_reason=final.stop_reason,
        usage={
            "input": getattr(final.usage, "input_tokens", input_tokens),
            "output": getattr(final.usage, "output_tokens", output_tokens),
        },
    )


def _block_to_dict(block: Any) -> dict[str, Any]:
    """Convert an SDK content block to a mutable dict."""
    if hasattr(block, "model_dump"):
        return block.model_dump()
    d: dict[str, Any] = {"type": getattr(block, "type", "unknown")}
    if d["type"] == "text":
        d["text"] = getattr(block, "text", "")
    elif d["type"] == "tool_use":
        d["id"] = getattr(block, "id", "")
        d["name"] = getattr(block, "name", "")
        d["input"] = getattr(block, "input", {})
    return d
