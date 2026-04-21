<p align="center">
  <h1 align="center">mini-claw</h1>
  <p align="center">
    <strong>A Minimalist Multi-Agent AI Assistant Framework</strong>
  </p>
  <p align="center">
    <a href="#features">Features</a> &bull;
    <a href="#architecture">Architecture</a> &bull;
    <a href="#quick-start">Quick Start</a> &bull;
    <a href="#configuration">Configuration</a> &bull;
    <a href="#extending">Extending</a>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/LangChain-0.3+-green?logo=chainlink&logoColor=white" alt="LangChain">
    <img src="https://img.shields.io/badge/LangGraph-0.2+-orange" alt="LangGraph">
    <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
  </p>
</p>

---

## Overview

**mini-claw** is a lightweight yet powerful AI assistant framework built on **LangChain/LangGraph**, inspired by the [OpenClaw](https://github.com/anthropics/openclaw) design philosophy. It provides a modular, extensible multi-agent system with persistent memory, tool orchestration, and a pluggable LLM provider layer — all in under **2000 lines** of core Python code.

```
User  -->  AgentManager  -->  LangGraph ReAct Agent  -->  Tools / Memory / Sub-Agents
                    |                                          |
                    +-- SessionManager (JSON persistence)       +-- File / Exec / Web / Memory
                    +-- LLM Provider (4 backends)              +-- SQLite FTS5 + Vector search
                    +-- Skill System (convention-over-config)
```

## Features

### Multi-LLM Provider Support

A unified `ChatOpenAI` interface abstracts away provider differences. Swap models with a single config change.

| Provider   | Models                          | Auth       |
|------------|---------------------------------|------------|
| DeepSeek   | deepseek-chat, deepseek-coder   | API Key    |
| OpenAI     | gpt-4o, gpt-4o-mini, o1         | API Key    |
| Qwen       | qwen-plus, qwen-max, qwen-turbo | API Key    |
| Ollama     | llama3.2, qwen2.5, ...          | Local only |

### Persistent Memory System

A two-layer memory architecture gives agents long-term context:

- **Layer 1 — File-based**: Daily markdown files (`memory/2026-03-24.md`) + structured `MEMORY.md`
- **Layer 2 — Searchable**: SQLite FTS5 full-text index with BM25 ranking, optional vector semantic search, and hybrid retrieval

```
Memory Write  -->  markdown file  -->  paragraph chunking  -->  FTS5 index
Memory Recall -->  query  -->  FTS5 / Vector / Hybrid  -->  ranked results
```

Paragraph-based chunking (splitting on blank lines) preserves semantic coherence better than fixed-size windows. Change detection via MD5 hashing avoids redundant re-indexing.

### Tool System

Agents have access to a curated toolkit, each with path sandboxing and input validation:

| Category   | Tools                                           | Description                    |
|------------|-------------------------------------------------|--------------------------------|
| Filesystem | `read`, `write`, `edit`, `ls`                   | Workspace-sandboxed file I/O   |
| Execution  | `exec`, `pwd`, `cd`                             | Shell commands (blocklisted)   |
| Memory     | `memory_search`, `memory_get`, `memory_write`   | Persistent memory operations   |
| Web        | `web_search`, `web_fetch`, `tavily_search`      | Search and page content fetch  |
| Agent      | `sessions_spawn`, `subagents`, `reset`          | Sub-agent delegation           |

### Multi-Agent Orchestration

Agents can spawn child sessions for delegated tasks via `sessions_spawn`. The parent agent sends a task description, a sub-session runs the full ReAct loop independently, and the result is returned to the parent.

```
Parent Agent  --task-->  Sub-Agent Session  --ReAct loop-->  Result  -->  Parent
```

Configurable limits prevent runaway recursion:
- `max_spawn_depth: 2` — maximum nesting level
- `max_children_per_agent: 5` — concurrent sub-agent cap

### Agent Personality Files

Each agent workspace contains markdown files that define its behavior:

| File          | Purpose                                      |
|---------------|----------------------------------------------|
| `SOUL.md`     | Personality traits, values, working style    |
| `IDENTITY.md` | Capabilities and guiding principles          |
| `HEARTBEAT.md`| Periodic self-check instructions             |
| `MEMORY.md`   | Long-term structured memory                  |
| `memory/`     | Daily memory files (auto-indexed)            |
| `skills/`     | Discoverable skill definitions               |

### Skill System

Skills follow **convention-over-configuration**: any folder under `skills/` with a `SKILL.md` is automatically discovered and injected into the system prompt. Each skill has YAML frontmatter for metadata and markdown instructions for the agent.

### API Server

A production-ready FastAPI server with SSE streaming:

```
POST /chat          Non-streaming chat
POST /chat/stream   SSE streaming (Server-Sent Events)
GET  /agents        List available agents
GET  /agents/{id}/sessions   List sessions
DELETE /sessions/{id}        Delete session
POST /sessions/{id}/reset    Reset session
GET  /health                 Health check
```

### Security

- **Path sandboxing**: All file operations restricted to workspace directory
- **Command blocklist**: Dangerous commands (`rm`, `sudo`, `shutdown`, `dd`, etc.) are blocked
- **No hardcoded secrets**: All API keys via environment variables with `${VAR}` templating in YAML
- **Optional allowlist mode**: Restrict exec tool to an explicit command set

## Quick Start

### Prerequisites

- Python 3.11+
- At least one LLM API key (DeepSeek, OpenAI, or Qwen) — or Ollama for local inference

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/mini-claw.git
cd mini-claw

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Console Mode

```bash
python main.py
```

### Web UI

```bash
python api.py
# Open http://localhost:8080
```

### REPL Commands

| Command     | Description                     |
|-------------|---------------------------------|
| `/new`      | Create a new session            |
| `/reset`    | Reset current session           |
| `/compact`  | Compress session history        |
| `/help`     | Show available commands         |
| `/exit`     | Quit                            |

## Architecture

```
                          ┌──────────────────────────────────┐
                          │         Entry Points             │
                          │  main.py (REPL)   api.py (HTTP)  │
                          └──────────────┬───────────────────┘
                                         │
                          ┌──────────────▼───────────────────┐
                          │       AgentManager (Core)         │
                          │  ┌─────────────────────────────┐ │
                          │  │  CommandParser               │ │
                          │  │  LangGraph ReAct Agent       │ │
                          │  │  Tool Orchestration          │ │
                          │  └─────────────────────────────┘ │
                          └─────┬──────────┬──────────┬──────┘
                                │          │          │
               ┌────────────────▼──┐  ┌────▼────┐  ┌▼─────────────────┐
               │ SessionManager    │  │ LLM     │  │ Memory System    │
               │ • JSON files      │  │ Provider│  │ • FTS5 indexer   │
               │ • Thread-safe     │  │ Factory │  │ • Vector search  │
               │ • Compression     │  │ 4 backends│ │ • Hybrid merge   │
               └───────────────────┘  └─────────┘  └─────────────────┘
```

### Key Design Decisions

**Unified OpenAI-compatible interface**: DeepSeek, Qwen, and Ollama all expose OpenAI-compatible APIs. A single `ChatOpenAI` adapter handles all providers — zero provider-specific SDK code.

**ReAct loop via LangGraph**: The agent reasons about what to do (Thought), takes action (Tool Call), observes the result (Observation), and decides next steps — repeating until the task is complete.

**Paragraph-level memory chunking**: Instead of arbitrary fixed-size windows, memory files are split on blank lines. This preserves the semantic coherence of natural paragraphs.

**Convention-over-configuration**: Skills are auto-discovered from the filesystem. No registration, no config — drop a `SKILL.md` and it works.

## Configuration

All configuration lives in `config.yaml`:

```yaml
workspace_dir: ./workspace

models:
  providers:
    deepseek:
      api_key: ${DEEPSEEK_API_KEY}      # Resolved from .env
      base_url: https://api.deepseek.com
      models: [deepseek-chat, deepseek-coder]

    ollama:
      base_url: http://localhost:11434/v1
      api_key: ollama                     # No key needed for local
      models: [llama3.2, qwen2.5]

agents:
  defaults:
    model: qwen-plus
    temperature: 0.7
    memory:
      enabled: true
      vector_enabled: false               # Set true for semantic search
    subagents:
      max_spawn_depth: 2
      max_children_per_agent: 5

tools:
  fs:
    workspace_only: true
    readonly_dirs: [docs]
  web:
    search:
      provider: duckduckgo                 # or tavily
```

## Project Structure

```
mini-claw/
├── src/
│   ├── config.py              # YAML config with env var templating
│   ├── agent_manager.py       # Core engine: ReAct agent, streaming, tools
│   ├── session_manager.py     # JSON-based session persistence
│   ├── llm/
│   │   ├── providers.py       # Factory pattern: 4 LLM providers
│   │   ├── callbacks.py       # Full request/response logging
│   │   └── simple_callbacks.py# Emoji-based thought-flow display
│   ├── memory/
│   │   ├── indexer.py         # SQLite FTS5 paragraph indexer
│   │   └── search.py          # FTS5 / Vector / Hybrid search engine
│   ├── prompts/
│   │   └── system.py          # System prompt builder
│   └── tools/
│       ├── file_tools.py      # read, write, edit, ls
│       ├── exec_tools.py      # exec, pwd, cd
│       ├── memory_tools.py    # memory_search, memory_get, memory_write
│       ├── web_tools.py       # web_search, web_fetch
│       └── agent_tools.py     # sessions_spawn, subagents, reset
├── workspace/
│   └── agents/
│       └── main/              # Default agent workspace
│           ├── SOUL.md
│           ├── IDENTITY.md
│           ├── HEARTBEAT.md
│           ├── MEMORY.md
│           ├── memory/        # Daily memory files
│           ├── skills/        # Auto-discovered skills
│           └── sessions/      # JSON session files
├── static/
│   └── index.html             # Web chat UI
├── config.yaml                # Main configuration
├── main.py                    # Console REPL
├── api.py                     # FastAPI server
├── requirements.txt
└── README.md
```

## Extending

### Add a New Tool

```python
# src/tools/my_tool.py
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

class MyToolInput(BaseModel):
    query: str = Field(description="Search query")

class MyTool(BaseTool):
    name: str = "my_tool"
    description: str = "Does something useful"
    args_schema: type[BaseModel] = MyToolInput

    def _run(self, query: str) -> str:
        return f"Result for: {query}"

# Register in agent_manager.py _build_tools():
tools.append(MyTool())
```

### Add a New LLM Provider

```python
# In src/llm/providers.py
class MyProvider(LLMProvider):
    def get_model(self, model_id, temperature=0.7, max_tokens=4096):
        return ChatOpenAI(
            model=model_id,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )

# Register in config.yaml
# models.providers.my_provider:
#   api_key: ${MY_API_KEY}
#   base_url: https://my-api.com/v1
```

### Add a New Skill

```bash
mkdir -p workspace/agents/main/skills/my_skill
```

```markdown
<!-- workspace/agents/main/skills/my_skill/SKILL.md -->
---
name: my_skill
description: "Description of when to use this skill"
---

# My Skill

Instructions for the agent on how to use this skill...
```

The skill is automatically discovered on next agent invocation — no restart needed.

### Add a New Agent

```yaml
# config.yaml
agents:
  list:
    - id: main
      name: General Assistant
      model: qwen-plus

    - id: coder
      name: Code Specialist
      model: deepseek-coder
```

Then create `workspace/agents/coder/` with `SOUL.md`, `IDENTITY.md`, etc.

## Tech Stack

| Component        | Technology                          |
|------------------|-------------------------------------|
| Agent Framework  | LangChain 0.3+ / LangGraph 0.2+    |
| LLM Interface    | langchain-openai (OpenAI-compatible)|
| Memory Index     | SQLite FTS5                         |
| Semantic Search  | sentence-transformers (optional)    |
| Console UI       | Rich                                |
| Web Server       | FastAPI / SSE                       |
| Configuration    | PyYAML + Pydantic                   |
| Web Search       | DuckDuckGo (free) / Tavily (paid)  |

## Design Patterns

| Pattern          | Where                                |
|------------------|--------------------------------------|
| Factory          | `LLMProviderFactory`, `create_web_tools()` |
| Singleton        | Config, SessionManager, MemoryEngine |
| Strategy         | Search modes (FTS5/Vector/Hybrid)    |
| Builder          | `build_system_prompt()`              |
| Sandbox          | `validate_path()` for filesystem     |
| Observer         | LangChain callbacks for logging      |
| Template Method  | `BaseTool` subclasses               |

## License

MIT
