[English](./README.md) | **中文**

# nano-claude-py

[nano-claude](https://github.com/dox012/nano-claude) 的 Python 移植版 — 用 **~1,800 行 Python** 轻量级复刻 [Claude Code](https://docs.anthropic.com/en/docs/claude-code)。

| | Claude Code | nano-claude (TS) | nano-claude-py |
|---|---|---|---|
| 代码行数 | 512,685 | ~2,000 | **~1,800** |
| 文件数 | 1,902 | 19 | **19** |
| 工具数 | ~50 | 7 | **7** |
| 语言 | TypeScript | TypeScript | **Python** |
| 运行时 | Bun | Node.js | **CPython** |
| UI | React + Ink | readline | **rich + input()** |

## 快速开始

```bash
pip install -e .
cp .env.example .env        # Windows CMD: copy .env.example .env
# 编辑 .env 填入你的 API key
nano-claude
```

或者不安装直接运行：

```bash
pip install anthropic rich python-dotenv
python -m nano_claude
```

## 命令行用法

```bash
nano-claude                          # 交互式 REPL
nano-claude "解释一下这个项目"          # 带初始 prompt 的交互
nano-claude -p "列出所有 TODO"         # 非交互模式，输出后退出
nano-claude -c                       # 继续上次对话
nano-claude -r <session-id>          # 恢复指定会话
nano-claude -p --max-turns 5 "重构这个函数"
nano-claude --dangerously-skip-permissions "写一个 hello.txt"
```

| 参数 | 说明 |
|------|------|
| `-p, --print` | 非交互模式：只输出文本，完成后退出 |
| `-c, --continue` | 继续最近一次对话 |
| `-r, --resume <id>` | 按 ID 恢复指定会话 |
| `-m, --model <model>` | 覆盖模型名称 |
| `--max-turns <n>` | 最大 Agent 轮次（默认：无限） |
| `--dangerously-skip-permissions` | 跳过所有权限确认 |
| `-h, --help` | 显示帮助 |
| `-v, --version` | 显示版本号 |

## 斜杠命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示可用命令 |
| `/cost` | 显示 token 使用量 |
| `/clear` | 清空对话历史 |
| `/compact` | 智能对话压缩 |
| `/model` | 查看或切换模型 |
| `/sessions` | 列出已保存的会话 |
| `/resume` | 恢复之前的会话 |
| `/remember` | 保存一条持久记忆 |
| `/forget` | 删除一条记忆 |
| `/memory` | 列出已保存的记忆 |

## 架构

```
src/nano_claude/
├── cli.py               # 入口 + REPL + CLI 参数 + 斜杠命令
├── api.py               # Anthropic SDK 流式封装
├── prompt.py            # 系统提示词构建
├── context.py           # Git 上下文 + 多层级 CLAUDE.md
├── types.py             # 核心类型定义 (dataclasses)
├── permissions.py       # 工具风险分级 + 确认
├── session.py           # 会话保存/加载/列表
├── compact.py           # 智能对话压缩
├── memory.py            # 持久化键值记忆
└── tools/
    ├── __init__.py       # 工具注册表
    ├── bash.py           # Shell 命令执行
    ├── read.py           # 带行号文件读取
    ├── write.py          # 文件创建/覆盖
    ├── edit.py           # 字符串替换编辑
    ├── glob_tool.py      # 文件模式搜索
    ├── grep.py           # 内容搜索 (ripgrep)
    └── agent.py          # 子代理生成
```

## 工具

| 工具 | 说明 | 风险等级 |
|------|------|---------|
| **Bash** | 执行 Shell 命令 | 按命令分级 |
| **Read** | 带行号读取文件 | 安全 |
| **Write** | 创建/覆盖文件 | 写入 |
| **Edit** | 字符串替换编辑 | 写入 |
| **Glob** | 按模式搜索文件 | 安全 |
| **Grep** | 搜索文件内容 | 安全 |
| **Agent** | 生成只读子代理 | 安全 |

## 依赖

仅 3 个运行时依赖：

- [`anthropic`](https://pypi.org/project/anthropic/) — Anthropic 官方 SDK
- [`rich`](https://pypi.org/project/rich/) — 终端 Markdown 渲染 + 彩色输出
- [`python-dotenv`](https://pypi.org/project/python-dotenv/) — .env 文件加载

其余全部使用 Python 标准库。

## 与 TypeScript 版本的差异

| 方面 | TS 版 | Python 版 |
|------|-------|----------|
| Markdown 渲染 | 手写 88 行解析器 + chalk | `rich.Markdown`（内置） |
| 参数解析 | 手写解析器 | `argparse`（标准库） |
| 状态管理 | 模块级变量 | `App` 类 |
| 类型系统 | TS interface | `dataclass` |
| 异步模型 | `async/await` | 同步 |
| 项目检测 | `.git` / `package.json` | `.git` / `pyproject.toml` / `package.json` |

## 许可证

MIT
