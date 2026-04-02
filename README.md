**English** | [中文](./README_CN.md)

# nano-claude-py

A Python port of [nano-claude](https://github.com/dox012/nano-claude) — lightweight reimplementation of [Claude Code](https://docs.anthropic.com/en/docs/claude-code) in **~1,800 lines of Python**.

| | Claude Code | nano-claude (TS) | nano-claude-py |
|---|---|---|---|
| Lines of code | 512,685 | ~2,000 | **~1,800** |
| Files | 1,902 | 19 | **19** |
| Tools | ~50 | 7 | **7** |
| Language | TypeScript | TypeScript | **Python** |
| Runtime | Bun | Node.js | **CPython** |
| UI | React + Ink | readline | **rich + input()** |

## Quick Start

```bash
pip install -e .
cp .env.example .env        # Windows CMD: copy .env.example .env
# Edit .env with your API key
nano-claude
```

Or run without installing:

```bash
pip install anthropic rich python-dotenv
python -m nano_claude
```

## CLI Usage

```bash
nano-claude                          # interactive REPL
nano-claude "explain this project"   # interactive with initial prompt
nano-claude -p "list all TODOs"      # non-interactive, print and exit
nano-claude -c                       # continue last conversation
nano-claude -r <session-id>          # resume specific session
nano-claude -p --max-turns 5 "refactor this function"
nano-claude --dangerously-skip-permissions "write hello.txt"
```

| Flag | Description |
|------|-------------|
| `-p, --print` | Non-interactive mode: output text only, then exit |
| `-c, --continue` | Continue the most recent conversation |
| `-r, --resume <id>` | Resume a specific session by ID |
| `-m, --model <model>` | Override the model name |
| `--max-turns <n>` | Maximum agentic turns (default: unlimited) |
| `--dangerously-skip-permissions` | Skip all permission prompts |
| `-h, --help` | Show help |
| `-v, --version` | Show version |

## Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/cost` | Display token usage |
| `/clear` | Clear conversation history |
| `/compact` | Smart conversation compression |
| `/model` | Show or switch model |
| `/sessions` | List saved sessions |
| `/resume` | Resume a previous session |
| `/remember` | Save a persistent memory |
| `/forget` | Delete a memory |
| `/memory` | List saved memories |

## Architecture

```
src/nano_claude/
├── cli.py               # Entry + REPL + CLI args + slash commands
├── api.py               # Anthropic SDK streaming wrapper
├── prompt.py            # System prompt construction
├── context.py           # Git context + multi-level CLAUDE.md
├── types.py             # Core type definitions (dataclasses)
├── permissions.py       # Tool risk classification + confirmation
├── session.py           # Session save/load/list
├── compact.py           # Smart conversation compaction
├── memory.py            # Persistent key-value memory
└── tools/
    ├── __init__.py       # Tool registry
    ├── bash.py           # Shell command execution
    ├── read.py           # File reading with line numbers
    ├── write.py          # File creation / overwrite
    ├── edit.py           # String-replacement editing
    ├── glob_tool.py      # File pattern search
    ├── grep.py           # Content search (ripgrep)
    └── agent.py          # Sub-agent spawning
```

## Tools

| Tool | Description | Risk |
|------|-------------|------|
| **Bash** | Execute shell commands | Classified per command |
| **Read** | Read files with line numbers | Safe |
| **Write** | Create/overwrite files | Write |
| **Edit** | String-replacement editing | Write |
| **Glob** | Find files by pattern | Safe |
| **Grep** | Search file contents (ripgrep) | Safe |
| **Agent** | Spawn read-only sub-agent | Safe |

## Dependencies

Only 3 runtime dependencies:

- [`anthropic`](https://pypi.org/project/anthropic/) — Official Anthropic SDK
- [`rich`](https://pypi.org/project/rich/) — Terminal markdown rendering & colors
- [`python-dotenv`](https://pypi.org/project/python-dotenv/) — .env file loading

Everything else uses the Python standard library.

## Differences from TypeScript Version

| Aspect | TS version | Python version |
|--------|-----------|---------------|
| Markdown rendering | Hand-written 88-line parser + chalk | `rich.Markdown` (built-in) |
| Arg parsing | Hand-rolled | `argparse` (stdlib) |
| State management | Module-level variables | `App` class |
| Type system | TS interfaces | `dataclass` |
| Async | `async/await` (single-threaded) | Synchronous |
| Project detection | `.git` / `package.json` | `.git` / `pyproject.toml` / `package.json` |

## License

MIT
