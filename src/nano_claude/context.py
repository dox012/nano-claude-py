"""Git context and multi-level CLAUDE.md loading."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def get_git_context() -> str:
    """Gather git status information for the current directory."""
    try:
        def run(cmd: str) -> str:
            return subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=5,
            ).stdout.strip()

        branch = _try_run(lambda: run("git branch --show-current")) or "unknown"
        user_name = _try_run(lambda: run("git config user.name")) or "unknown"
        status = _try_run(lambda: run("git status --short")) or "(clean)"
        log = _try_run(lambda: run("git log --oneline -5 2>/dev/null")) or "(no commits)"

        return "\n".join([
            f"Current branch: {branch}",
            f"Git user: {user_name}",
            "",
            "Status:",
            status or "(clean)",
            "",
            "Recent commits:",
            log,
        ])
    except Exception:
        return "(not a git repository)"


def get_claude_md() -> str:
    """Load multi-level CLAUDE.md files.

    Priority order (all loaded):
      1. ~/.claude/CLAUDE.md          (user-level defaults)
      2. <project-root>/CLAUDE.md     (project-level)
      3. <project-root>/.claude/CLAUDE.md (project-level alt)
      4. <cwd>/CLAUDE.md              (subdir-level, if different from project root)
    """
    home = Path.home()
    cwd = Path.cwd()
    project_root = _find_project_root(cwd)

    candidates: list[tuple[Path, str]] = []

    # 1. User-level
    candidates.append((home / ".claude" / "CLAUDE.md", "user (~/.claude/CLAUDE.md)"))

    # 2. Project-root level
    if project_root:
        rel = os.path.relpath(project_root, cwd) if project_root != cwd else "."
        candidates.append((project_root / "CLAUDE.md", f"project ({rel}/)"))
        candidates.append((project_root / ".claude" / "CLAUDE.md", f"project ({rel}/.claude/)"))

    # 3. CWD level (if different from project root)
    if not project_root or cwd.resolve() != project_root.resolve():
        candidates.append((cwd / "CLAUDE.md", "local"))

    # Deduplicate by resolved path
    seen: set[Path] = set()
    parts: list[str] = []
    for p, label in candidates:
        resolved = p.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file():
            content = resolved.read_text(encoding="utf-8", errors="replace").strip()
            parts.append(f"# [{label}]\n{content}")

    return "\n\n---\n\n".join(parts)


def _find_project_root(from_dir: Path) -> Path | None:
    """Walk up to find .git or pyproject.toml/package.json."""
    d = from_dir.resolve()
    while True:
        if (d / ".git").exists() or (d / "pyproject.toml").exists() or (d / "package.json").exists():
            return d
        parent = d.parent
        if parent == d:
            return None
        d = parent


def _try_run(fn):
    try:
        return fn()
    except Exception:
        return None
