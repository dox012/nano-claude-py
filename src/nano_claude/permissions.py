"""Tool risk classification and permission prompts."""

from __future__ import annotations

import re
from typing import Any

from rich.console import Console

console = Console(stderr=True)

RiskLevel = str  # "safe" | "write" | "destructive"

DESTRUCTIVE_PATTERNS = [
    re.compile(r"\brm\s+(-[rRf]+\s+|.*--no-preserve-root)"),
    re.compile(r"\brm\s+-[a-zA-Z]*[rR]"),
    re.compile(r"\bgit\s+(reset\s+--hard|clean\s+-[a-zA-Z]*f|push\s+.*--force|checkout\s+--\s+\.)"),
    re.compile(r"\bgit\s+branch\s+-[dD]\b"),
    re.compile(r"\b(drop\s+table|drop\s+database|truncate)\b", re.IGNORECASE),
    re.compile(r"\bkill\s+-9\b"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bdd\s+"),
    re.compile(r">\s*/dev/sd"),
    re.compile(r"\bchmod\s+777\b"),
    re.compile(r"\bsudo\s+rm\b"),
    re.compile(r"\bcurl\b.*\|\s*(bash|sh)\b"),
]

WRITE_PATTERNS = [
    re.compile(r"\bgit\s+(add|commit|push|merge|rebase|stash|checkout|switch|branch)\b"),
    re.compile(r"\b(npm|yarn|pnpm)\s+(install|uninstall|update|publish)\b"),
    re.compile(r"\bpip\s+install\b"),
    re.compile(r"\bmkdir\b"),
    re.compile(r"\btouch\b"),
    re.compile(r"\bmv\b"),
    re.compile(r"\bcp\b"),
    re.compile(r"\brm\b"),
    re.compile(r"\bchmod\b"),
    re.compile(r"\bchown\b"),
    re.compile(r">\s*\S"),
    re.compile(r"\bsed\s+-i\b"),
    re.compile(r"\btee\b"),
    re.compile(r"\bdocker\s+(run|build|push|rm|stop|kill)\b"),
    re.compile(r"\bkubectl\s+(apply|delete|create|patch)\b"),
]


def classify_bash_risk(command: str) -> RiskLevel:
    for p in DESTRUCTIVE_PATTERNS:
        if p.search(command):
            return "destructive"
    for p in WRITE_PATTERNS:
        if p.search(command):
            return "write"
    return "safe"


def classify_tool_risk(tool_name: str, tool_input: dict[str, Any]) -> RiskLevel:
    if tool_name == "Bash":
        return classify_bash_risk(str(tool_input.get("command", "")))
    if tool_name in ("Write", "Edit"):
        return "write"
    return "safe"


def ask_permission(tool_name: str, tool_input: dict[str, Any], risk: RiskLevel) -> bool:
    """Interactive permission prompt. Returns True if allowed."""
    if risk == "safe":
        return True

    if risk == "destructive":
        risk_label = "[bold white on red] DESTRUCTIVE [/bold white on red]"
    else:
        risk_label = "[black on yellow] WRITE [/black on yellow]"

    detail = ""
    if tool_name == "Bash":
        detail = str(tool_input.get("command", ""))
    elif tool_name in ("Write", "Edit"):
        detail = str(tool_input.get("file_path", ""))

    short = detail[:97] + "..." if len(detail) > 100 else detail

    console.print(f"\n  {risk_label} [yellow]{tool_name}[/yellow]: [dim]{short}[/dim]")

    try:
        answer = input("  Allow? (y)es / (n)o / (a)lways: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False

    return answer in ("y", "yes", "a", "always")
