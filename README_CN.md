<p align="center">
  <h1 align="center">mini-claw</h1>
  <p align="center">
    <strong>轻量级多智能体 AI 助手框架</strong>
  </p>
  <p align="center">
    <a href="#特性">特性</a> &bull;
    <a href="#系统架构">架构</a> &bull;
    <a href="#快速开始">快速开始</a> &bull;
    <a href="#配置说明">配置</a> &bull;
    <a href="#扩展指南">扩展</a>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/LangChain-0.3+-green?logo=chainlink&logoColor=white" alt="LangChain">
    <img src="https://img.shields.io/badge/LangGraph-0.2+-orange" alt="LangGraph">
    <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
  </p>
</p>

---

## 项目简介

**mini-claw** 是一个基于 **LangChain/LangGraph** 构建的轻量级多智能体 AI 助手框架，灵感来源于 OpenClaw 的设计理念。它提供了模块化、可扩展的多 Agent 系统，支持持久化记忆、工具编排和可插拔的 LLM 提供商层 —— 核心代码不到 **2000 行** Python。

```
用户  -->  AgentManager  -->  LangGraph ReAct Agent  -->  工具 / 记忆 / 子 Agent
                    |                                          |
                    +-- SessionManager (JSON 持久化)           +-- 文件 / 执行 / 网络 / 记忆
                    +-- LLM 提供商 (4 种后端)                  +-- SQLite FTS5 + 向量搜索
                    +-- Skill 技能系统 (约定优于配置)
```

## 特性

### 多 LLM 提供商支持

统一的 `ChatOpenAI` 接口抹平了不同提供商之间的差异，修改配置即可切换模型。

| 提供商   | 可用模型                             | 认证方式   |
|----------|--------------------------------------|-----------|
| DeepSeek | deepseek-chat, deepseek-coder        | API Key   |
| OpenAI   | gpt-4o, gpt-4o-mini, o1              | API Key   |
| 通义千问 | qwen-plus, qwen-max, qwen-turbo      | API Key   |
| Ollama   | llama3.2, qwen2.5, ...               | 本地运行   |

### 持久化记忆系统

双层记忆架构让 Agent 拥有长期上下文能力：

- **第一层 —— 文件存储**：每日 Markdown 文件（`memory/2026-03-24.md`）+ 结构化的 `MEMORY.md`
- **第二层 —— 可检索索引**：SQLite FTS5 全文索引 + BM25 排序，可选向量语义搜索，以及混合检索模式

```
记忆写入  -->  Markdown 文件  -->  段落分块  -->  FTS5 索引
记忆召回  -->  查询语句  -->  FTS5 / 向量 / 混合  -->  排序结果
```

基于段落的分块策略（以空行为分隔符）比固定窗口更好地保留了语义完整性。通过 MD5 哈希进行变更检测，避免重复索引。

### 工具系统

Agent 可以使用一套精选工具集，每个工具都配备了路径沙箱和输入验证：

| 类别   | 工具                                           | 说明                       |
|--------|------------------------------------------------|---------------------------|
| 文件   | `read`, `write`, `edit`, `ls`                   | 受工作区限制的文件读写     |
| 执行   | `exec`, `pwd`, `cd`                             | Shell 命令（含黑名单过滤） |
| 记忆   | `memory_search`, `memory_get`, `memory_write`   | 持久化记忆操作             |
| 网络   | `web_search`, `web_fetch`, `tavily_search`      | 搜索和网页内容抓取         |
| Agent  | `sessions_spawn`, `subagents`, `reset`          | 子 Agent 任务委派          |

### 多 Agent 协作

Agent 可以通过 `sessions_spawn` 创建子会话来处理委派任务。父 Agent 发送任务描述，子会话独立运行完整的 ReAct 循环，结果返回给父 Agent。

```
父 Agent  --任务-->  子 Agent 会话  --ReAct 循环-->  结果  -->  父 Agent
```

可配置的递归限制防止失控：
- `max_spawn_depth: 2` — 最大嵌套层级
- `max_children_per_agent: 5` — 并发子 Agent 上限

### Agent 人格文件

每个 Agent 工作区包含定义其行为的 Markdown 文件：

| 文件          | 用途                                       |
|---------------|-------------------------------------------|
| `SOUL.md`     | 性格特质、价值观、工作风格                 |
| `IDENTITY.md` | 能力和指导原则                             |
| `HEARTBEAT.md`| 定期自检指令                               |
| `MEMORY.md`   | 长期结构化记忆                             |
| `memory/`     | 每日记忆文件（自动索引）                   |
| `skills/`     | 可自动发现的技能定义                       |

### 技能系统

技能遵循 **约定优于配置** 原则：`skills/` 目录下任何包含 `SKILL.md` 的文件夹都会被自动发现并注入系统提示词。每个技能通过 YAML frontmatter 定义元数据，通过 Markdown 内容为 Agent 提供使用指南。

### API 服务

生产级 FastAPI 服务，支持 SSE 流式输出：

```
POST /chat          非流式对话
POST /chat/stream   SSE 流式对话
GET  /agents        获取可用 Agent 列表
GET  /agents/{id}/sessions   获取会话列表
DELETE /sessions/{id}        删除会话
POST /sessions/{id}/reset    重置会话
GET  /health                 健康检查
```

### 安全机制

- **路径沙箱**：所有文件操作限制在工作区目录内
- **命令黑名单**：危险命令（`rm`、`sudo`、`shutdown`、`dd` 等）被拦截
- **无硬编码密钥**：所有 API Key 通过环境变量管理，YAML 中使用 `${VAR}` 模板语法
- **可选白名单模式**：可将执行工具限制为显式命令集

## 快速开始

### 环境要求

- Python 3.11+
- 至少一个 LLM API Key（DeepSeek / OpenAI / 通义千问）—— 或使用 Ollama 本地推理

### 安装

```bash
# 克隆仓库
git clone https://github.com/hanruxiang/mini-claw.git
cd mini-claw

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 API Key
```

### 控制台模式

```bash
python main.py
```

### Web UI 模式

```bash
python api.py
# 浏览器打开 http://localhost:8080
```

### REPL 命令

| 命令     | 说明                 |
|----------|----------------------|
| `/new`   | 创建新会话           |
| `/reset` | 重置当前会话         |
| `/compact`| 压缩会话历史        |
| `/help`  | 显示帮助信息         |
| `/exit`  | 退出                 |

## 系统架构

```
                          ┌──────────────────────────────────┐
                          │            入口层                 │
                          │  main.py (控制台)   api.py (HTTP) │
                          └──────────────┬───────────────────┘
                                         │
                          ┌──────────────▼───────────────────┐
                          │       AgentManager (核心引擎)      │
                          │  ┌─────────────────────────────┐ │
                          │  │  CommandParser  命令解析     │ │
                          │  │  LangGraph ReAct Agent      │ │
                          │  │  Tool Orchestration 工具编排 │ │
                          │  └─────────────────────────────┘ │
                          └─────┬──────────┬──────────┬──────┘
                                │          │          │
               ┌────────────────▼──┐  ┌────▼────┐  ┌▼─────────────────┐
               │ SessionManager    │  │  LLM    │  │  Memory System   │
               │ 会话管理           │  │ 提供商  │  │  记忆系统         │
               │ • JSON 文件存储   │  │ 工厂模式│  │ • FTS5 索引器    │
               │ • 线程安全        │  │ 4种后端 │  │ • 向量搜索       │
               │ • 会话压缩        │  │         │  │ • 混合检索       │
               └───────────────────┘  └─────────┘  └─────────────────┘
```

### 核心设计决策

**统一的 OpenAI 兼容接口**：DeepSeek、通义千问、Ollama 均暴露 OpenAI 兼容的 API。通过一个 `ChatOpenAI` 适配器处理所有提供商 —— 零提供商专属 SDK 代码。

**基于 LangGraph 的 ReAct 循环**：Agent 先推理需要做什么（Thought），再执行操作（Tool Call），观察结果（Observation），决定下一步 —— 循环直到任务完成。

**段落级记忆分块**：不使用任意固定大小的窗口，而是以空行分割记忆文件。这种方式保留了自然段落的语义完整性。

**约定优于配置**：技能从文件系统自动发现。无需注册、无需配置 —— 放入 `SKILL.md` 即可生效。

## 配置说明

所有配置集中在 `config.yaml` 中：

```yaml
workspace_dir: ./workspace

models:
  providers:
    deepseek:
      api_key: ${DEEPSEEK_API_KEY}       # 从 .env 文件解析
      base_url: https://api.deepseek.com
      models: [deepseek-chat, deepseek-coder]

    ollama:
      base_url: http://localhost:11434/v1
      api_key: ollama                      # 本地推理无需 Key
      models: [llama3.2, qwen2.5]

agents:
  defaults:
    model: qwen-plus
    temperature: 0.7
    memory:
      enabled: true
      vector_enabled: false                # 设为 true 启用向量语义搜索
    subagents:
      max_spawn_depth: 2
      max_children_per_agent: 5

tools:
  fs:
    workspace_only: true
    readonly_dirs: [docs]
  web:
    search:
      provider: duckduckgo                  # 或 tavily
```

## 项目结构

```
mini-claw/
├── src/
│   ├── config.py              # YAML 配置管理 + 环境变量模板解析
│   ├── agent_manager.py       # 核心引擎：ReAct Agent、流式输出、工具编排
│   ├── session_manager.py     # 基于 JSON 的会话持久化
│   ├── llm/
│   │   ├── providers.py       # 工厂模式：4 种 LLM 提供商
│   │   ├── callbacks.py       # 完整请求/响应日志回调
│   │   └── simple_callbacks.py# Emoji 风格思维流程展示
│   ├── memory/
│   │   ├── indexer.py         # SQLite FTS5 段落索引器
│   │   └── search.py          # FTS5 / 向量 / 混合搜索引擎
│   ├── prompts/
│   │   └── system.py          # 系统提示词构建器
│   └── tools/
│       ├── file_tools.py      # 文件读写编辑
│       ├── exec_tools.py      # 命令执行
│       ├── memory_tools.py    # 记忆搜索与写入
│       ├── web_tools.py       # 网络搜索与抓取
│       └── agent_tools.py     # 子 Agent 创建与管理
├── workspace/
│   └── agents/
│       └── main/              # 默认 Agent 工作区
│           ├── SOUL.md        # 人格定义
│           ├── IDENTITY.md    # 身份定义
│           ├── HEARTBEAT.md   # 心跳任务
│           ├── MEMORY.md      # 长期记忆
│           ├── memory/        # 每日记忆文件
│           ├── skills/        # 自动发现的技能
│           └── sessions/      # 会话记录（JSON）
├── static/
│   └── index.html             # Web 聊天界面
├── config.yaml                # 主配置文件
├── main.py                    # 控制台入口
├── api.py                     # FastAPI 服务
├── requirements.txt
├── README.md                  # English
└── README_CN.md               # 本文件
```

## 扩展指南

### 添加新工具

```python
# src/tools/my_tool.py
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

class MyToolInput(BaseModel):
    query: str = Field(description="搜索查询")

class MyTool(BaseTool):
    name: str = "my_tool"
    description: str = "做一件有用的事"
    args_schema: type[BaseModel] = MyToolInput

    def _run(self, query: str) -> str:
        return f"查询结果: {query}"

# 在 agent_manager.py 的 _build_tools() 中注册
tools.append(MyTool())
```

### 添加新 LLM 提供商

```python
# 在 src/llm/providers.py 中添加
class MyProvider(LLMProvider):
    def get_model(self, model_id, temperature=0.7, max_tokens=4096):
        return ChatOpenAI(
            model=model_id,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )

# 在 config.yaml 中配置
# models.providers.my_provider:
#   api_key: ${MY_API_KEY}
#   base_url: https://my-api.com/v1
```

### 添加新技能

```bash
mkdir -p workspace/agents/main/skills/my_skill
```

```markdown
<!-- workspace/agents/main/skills/my_skill/SKILL.md -->
---
name: my_skill
description: "描述何时使用此技能"
---

# 我的技能

Agent 使用此技能的详细说明...
```

技能在下一次 Agent 调用时自动发现 —— 无需重启。

### 添加新 Agent

```yaml
# config.yaml
agents:
  list:
    - id: main
      name: 通用助手
      model: qwen-plus

    - id: coder
      name: 编程专家
      model: deepseek-coder
```

然后创建 `workspace/agents/coder/` 目录，放入 `SOUL.md`、`IDENTITY.md` 等文件。

## 技术栈

| 组件        | 技术方案                             |
|-------------|--------------------------------------|
| Agent 框架  | LangChain 0.3+ / LangGraph 0.2+     |
| LLM 接口    | langchain-openai（OpenAI 兼容协议）   |
| 记忆索引    | SQLite FTS5                          |
| 语义搜索    | sentence-transformers（可选）         |
| 控制台 UI   | Rich                                 |
| Web 服务    | FastAPI / SSE                        |
| 配置管理    | PyYAML + Pydantic                    |
| 网络搜索    | DuckDuckGo（免费）/ Tavily（付费）   |

## 设计模式

| 模式          | 应用位置                              |
|---------------|---------------------------------------|
| 工厂模式      | `LLMProviderFactory`、`create_web_tools()` |
| 单例模式      | Config、SessionManager、MemoryEngine  |
| 策略模式      | 搜索模式（FTS5/向量/混合）            |
| 建造者模式    | `build_system_prompt()`               |
| 沙箱模式      | `validate_path()` 文件系统隔离        |
| 观察者模式    | LangChain 回调机制                    |
| 模板方法      | `BaseTool` 子类                       |

## 许可证

MIT
