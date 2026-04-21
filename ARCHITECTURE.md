# mini-claw 核心架构与原理

## 项目概述

mini-claw 是一个基于 OpenClaw 核心功能的简易版 AI 助手，使用 **LangChain/LangGraph** 实现，专注于控制台交互。

### 设计目标

- 🎯 **简化**：只实现核心功能，不追求完整复刻
- 💻 **控制台优先**：无需 Web UI，保持简洁
- 🔧 **模块化**：清晰的目录结构，易于扩展
- 🔑 **多 LLM 支持**：DeepSeek、OpenAI、Ollama、通义千问

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          控制台入口 (main.py)                    │
│                     REPL 循环 + Rich UI                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AgentManager (核心引擎)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  命令解析    │  │  会话管理    │  │   LangGraph Agent       │ │
│  │  CommandParser│ │SessionManager│ │  (create_react_agent)   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐ ┌──────────────┐ ┌─────────────────────┐
│   记忆系统       │ │   工具系统    │ │    LLM 提供商        │
│  MemorySystem   │ │   Tools      │ │  LLMProvider        │
├─────────────────┤ ├──────────────┤ ├─────────────────────┤
│• SQLite FTS5   │ │• 文件操作      │ │• DeepSeek          │
│• 向量检索(可选) │ │• 命令执行      │ │• OpenAI            │
│• 分块索引       │ │• 记忆操作      │ │• Ollama            │
│• 语义搜索       │ │• 网络搜索      │ │• Qwen              │
└─────────────────┘ └──────────────┘ └─────────────────────┘
```

---

## 核心模块详解

### 1. AgentManager (核心引擎)

**文件**: `src/agent_manager.py`

**职责**:
- 管理多个 Agent 实例的生命周期
- 协调会话、记忆、工具和 LLM
- 流式处理用户消息

**核心流程**:

```python
async def astream(message, session_id, agent_id):
    # 1. 解析命令 (/new, /reset, /help, /exit)
    command, action, remaining = CommandParser.parse(message)

    # 2. 加载 Agent 状态
    agent_state = self._get_agent_state(agent_id)

    # 3. 加载或创建会话
    self.session_manager.create_session(session_id, agent_id)

    # 4. 保存用户消息
    self.session_manager.save_message(session_id, agent_id, "user", message)

    # 5. 构建工具列表
    tools = self._build_tools(agent_id)

    # 6. 获取 LLM 模型
    model = get_model(model_id, temperature, max_tokens)

    # 7. 构建系统提示词
    system_prompt = build_system_prompt(agent_id, tools_description)

    # 8. 创建 LangGraph ReAct Agent
    agent = create_react_agent(model, tools, state_modifier=system_prompt)

    # 9. 流式执行
    async for event in agent.astream_events(...):
        # 处理 tokens、工具调用、错误
        yield event

    # 10. 保存助手响应
    self.session_manager.save_message(session_id, agent_id, "assistant", response)
```

**关键点**:
- 使用 **LangGraph 的 `create_react_agent`** 构建推理-行动循环
- **流式输出** 通过 `astream_events` 实现实时响应
- **事件驱动** 架构，支持 token、tool_start、tool_end、error 等事件

---

### 2. SessionManager (会话管理)

**文件**: `src/session_manager.py`

**职责**:
- 管理会话的生命周期
- 持久化会话历史
- 支持会话压缩

**数据结构**:

```python
@dataclass
class SessionData:
    session_id: str
    agent_id: str
    label: str
    created_at: str
    updated_at: str
    messages: list[dict]        # 对话历史
    compressed_context: str      # 压缩的摘要
    metadata: dict
```

**存储格式**:

```json
// workspace/agents/{agent_id}/sessions/{session_id}.json
{
  "session_id": "main",
  "agent_id": "main",
  "label": "默认会话",
  "created_at": "2026-03-06T10:00:00",
  "updated_at": "2026-03-06T10:30:00",
  "messages": [
    {"role": "user", "content": "你好", "timestamp": "..."},
    {"role": "assistant", "content": "你好！我是你的AI助手", "timestamp": "..."}
  ],
  "compressed_context": "",
  "metadata": {}
}
```

**LLM 消息格式化**:

```python
def get_messages_for_llm(session_id, agent_id):
    # 1. 添加压缩摘要（如果有）
    # 2. 合并连续的 assistant 消息
    # 3. 转换为 LangChain 消息格式
    return lc_messages
```

---

### 3. MemorySystem (记忆系统)

**文件**: `src/memory/indexer.py`, `src/memory/search.py`

**架构**:

```
┌─────────────────────────────────────────────────────────┐
│                    记忆搜索引擎                         │
│  ┌──────────────┐      ┌─────────────────────────────┐ │
│  │ MemoryIndexer│ ───▶ │   混合搜索策略               │ │
│  │              │      │  • FTS5 全文搜索             │ │
│  │ • SQLite FTS5│      │  • 向量语义搜索（可选）      │ │
│  │ • 分块索引    │      │  • 加权合并                 │ │
│  │ • 文件监听    │      └─────────────────────────────┘ │
│  └──────────────┘                                        │
└─────────────────────────────────────────────────────────┘
```

**索引结构**:

```sql
-- 记忆块表
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,        -- 文件路径
    start_line INTEGER NOT NULL,  -- 起始行号
    end_line INTEGER NOT NULL,    -- 结束行号
    content TEXT NOT NULL,        -- 内容
    content_hash TEXT NOT NULL    -- 内容哈希（用于变更检测）
);

-- FTS5 全文搜索虚拟表
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    source, content,
    content='chunks',
    content_rowid='id'
);
```

**分块策略**:

```python
# 按段落分块（以空行为分隔符）
def _chunk_file(file_path):
    lines = file_path.read_text().splitlines()
    chunks = []
    current_chunk = []

    for line in lines:
        if line.strip() == "":  # 空行作为分隔符
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
        else:
            current_chunk.append(line)

    return chunks
```

**搜索流程**:

```python
def search(query, mode="auto"):
    if mode == "fts5":
        # SQLite FTS5 全文搜索
        results = fts5_search(query)

    elif mode == "vector":
        # sentence-transformers 向量搜索
        query_embedding = model.encode(query)
        similarities = cosine_similarity(chunk_embeddings, query_embedding)

    elif mode == "hybrid":
        # 加权合并
        fts5_results = fts5_search(query)
        vector_results = vector_search(query)
        results = weighted_merge(fts5_results, vector_results)

    return results
```

---

### 4. Tools System (工具系统)

**文件**: `src/tools/*.py`

**工具分类**:

| 类别 | 工具 | 功能 |
|------|------|------|
| **文件操作** | `read`, `write`, `edit`, `ls` | 文件读写编辑 |
| **命令执行** | `exec`, `pwd` | Shell 命令 |
| **记忆操作** | `memory_search`, `memory_get`, `memory_write` | 记忆读写搜索 |
| **网络操作** | `web_search`, `web_fetch` | 网络搜索抓取 |
| **Agent 协作** | `sessions_spawn`, `reset` | 子 Agent 创建 |

**工具接口**:

```python
class ReadTool(BaseTool):
    name: str = "read"
    description: str = "读取文件内容"
    args_schema: type[BaseModel] = ReadInput

    root_dir: Path  # 工作目录（安全限制）
    readonly_dirs: list[str]  # 只读目录

    def _run(self, path: str, offset: int = None, limit: int = None) -> str:
        # 1. 路径安全验证
        safe_path = validate_path(path, self.root_dir)

        # 2. 读取文件
        content = safe_path.read_text()

        # 3. 处理行号范围
        if offset or limit:
            lines = content.splitlines()
            selected = lines[start:end]

        return format_output(selected)
```

**安全策略**:

```python
def validate_path(path: str, root_dir: Path) -> Path:
    # 1. 解析路径
    target_path = Path(path).expanduser().resolve()

    # 2. 检查是否在根目录内
    try:
        target_path.relative_to(root_dir)
    except ValueError:
        raise PermissionError("路径不在允许范围内")

    # 3. 检查只读目录
    for readonly_path in readonly_dirs:
        try:
            target_path.relative_to(readonly_path)
            return target_path  # 允许访问只读目录
        except ValueError:
            continue

    return target_path
```

---

### 5. System Prompt (系统提示词)

**文件**: `src/prompts/system.py`

**提示词结构**:

```python
SYSTEM_PROMPT_TEMPLATE = """
You are a personal assistant running inside mini-claw.

## Tooling
{tools_list}

## Safety
You have no independent goals: do not pursue self-preservation,
replication, resource acquisition, or power-seeking.
Prioritize safety and human oversight over completion.

## Memory Recall
Before answering anything about prior work:
1. Run memory_search on MEMORY.md + memory/*.md
2. Use memory_get to pull only the needed lines

## Workspace
- workspace_dir: {workspace_dir}
- agent_id: {agent_id}

## Heartbeats
Heartbeat prompt: Read HEARTBEAT.md if it exists.
If nothing needs attention, reply HEARTBEAT_OK.

## Current Date & Time
{current_time}

{soul_context}      # SOUL.md 内容
{identity_context}  # IDENTITY.md 内容
"""
```

**动态内容加载**:

```python
def build_system_prompt(agent_id, tools_description):
    # 1. 加载 SOUL.md（个性）
    soul_content = (agent_dir / "SOUL.md").read_text()

    # 2. 加载 IDENTITY.md（身份）
    identity_content = (agent_dir / "IDENTITY.md").read_text()

    # 3. 加载 HEARTBEAT.md（心跳任务）
    heartbeat_content = (agent_dir / "HEARTBEAT.md").read_text()

    # 4. 组装最终提示词
    return template.format(
        tools_list=tools_description,
        workspace_dir=agent_dir,
        agent_id=agent_id,
        soul_context=soul_content,
        identity_context=identity_content,
        heartbeat_context=heartbeat_content,
        current_time=datetime.now().isoformat(),
    )
```

---

### 6. LLM Providers (LLM 提供商)

**文件**: `src/llm/providers.py`

**提供商抽象**:

```python
class LLMProvider(ABC):
    @abstractmethod
    def get_model(self, model_id, temperature, max_tokens) -> ChatOpenAI:
        pass

class DeepSeekProvider(LLMProvider):
    API_BASE = "https://api.deepseek.com/v1"

    def get_model(self, model_id, ...):
        return ChatOpenAI(
            model=model_id,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )

class OllamaProvider(LLMProvider):
    # 本地运行，无需 API key
    def get_model(self, model_id, ...):
        return ChatOpenAI(
            model=model_id,
            base_url="http://localhost:11434/v1",
            api_key="ollama",  # 占位符
        )
```

**工厂模式**:

```python
class LLMProviderFactory:
    _providers: dict[str, LLMProvider] = {}

    @classmethod
    def register(cls, name, provider):
        cls._providers[name] = provider

    @classmethod
    def create_from_config(cls, config):
        for provider_id, provider_config in config.items():
            if provider_id == "deepseek":
                cls.register("deepseek", DeepSeekProvider(...))
            elif provider_id == "openai":
                cls.register("openai", OpenAIProvider(...))
            # ...

def get_model(model_id, provider_name=None):
    if provider_name is None:
        provider_name = config.get_provider_for_model(model_id)

    provider = LLMProviderFactory.get(provider_name)
    return provider.get_model(model_id, ...)
```

---

## 数据流

### 用户请求处理流程

```
用户输入
  │
  ▼
┌─────────────────┐
│  命令解析        │  /new, /reset, /help, /exit
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  加载会话历史    │  SessionManager.load_session()
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  构建系统提示词  │  build_system_prompt()
│  • 工具列表       │
│  • 安全规则       │
│  • 记忆召回       │
│  • 身份定义       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LangGraph Agent│  create_react_agent()
│  (ReAct 循环)    │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌──────────┐
│ 思考    │ │ 行动     │
│ Thinking│ │ Tool Use│
└────────┘ └────┬─────┘
               │
         ┌─────┴─────┐
         │           │
         ▼           ▼
    ┌────────┐  ┌──────────┐
    │ LLM    │  │ Tools    │
    │ 调用    │  │ 执行     │
    └───┬────┘  └────┬─────┘
        │            │
        └─────┬──────┘
              │
              ▼
        ┌─────────┐
        │ 流式输出 │
        │ astream │
        └────┬────┘
             │
             ▼
        用户看到响应
```

---

## 配置系统

**文件**: `src/config.py`

**配置层次**:

```yaml
# config.yaml
workspace_dir: ./workspace

models:
  providers:
    deepseek:
      api_key: ${DEEPSEEK_API_KEY}
      base_url: https://api.deepseek.com/v1
      models: [deepseek-chat, deepseek-coder]

    ollama:
      base_url: http://localhost:11434/v1
      models: [llama3.2, qwen2.5]

agents:
  defaults:
    model: deepseek-chat
    temperature: 0.7
    memory:
      enabled: true
      vector_enabled: false

  list:
    - id: main
      name: Assistant
      description: 默认助手

tools:
  fs:
    workspace_only: true
    readonly_dirs: [docs]

  web:
    search:
      provider: duckduckgo
```

**环境变量替换**:

```python
def load_config(config_path):
    with open(config_path) as f:
        data = yaml.safe_load(f)

    # 替换 ${VAR_NAME} 为环境变量值
    for key, value in data.items():
        if isinstance(value, str) and value.startswith("${"):
            env_key = value[2:-1]
            data[key] = os.environ.get(env_key, "")

    return Config(**data)
```

---

## 工作目录结构

```
workspace/
├── agents/
│   └── main/                    # Agent 工作目录
│       ├── SOUL.md              # 灵魂和个性
│       ├── IDENTITY.md          # 身份定义
│       ├── HEARTBEAT.md         # 心跳任务
│       ├── MEMORY.md            # 长期记忆
│       ├── memory/              # 每日记忆
│       │   ├── 2026-03-06.md
│       │   └── 2026-03-05.md
│       ├── skills/              # 技能目录
│       │   └── {skill_name}/
│       │       └── SKILL.md
│       ├── sessions/            # 会话记录
│       │   ├── main.json
│       │   └── session-xxx.json
│       └── .memory_index.db     # 记忆索引数据库
└── config/
    └── user.yaml                # 用户配置覆盖
```

---

## 关键设计决策

### 1. 为什么选择 LangGraph 的 ReAct Agent？

**ReAct (Reasoning + Acting)** 模式：
- **推理先行**：先思考需要做什么
- **行动执行**：然后调用工具执行
- **观察结果**：最后观察结果决定下一步

```python
# ReAct 循环示例
Thought: 用户想知道今天的天气，我需要使用网络搜索
Action: web_search(query="今天北京天气")
Observation: 晴天，15-25°C
Thought: 我得到了结果，可以回答用户了
Answer: 今天北京晴天，温度15-25度
```

### 2. 为什么使用 SQLite FTS5？

| 特性 | SQLite FTS5 | 向量搜索 |
|------|-------------|----------|
| 速度 | 快（毫秒级） | 中等 |
| 准确度 | 关键词匹配 | 语义相似 |
| 资源占用 | 极低 | 较高 |
| 依赖 | 内置 | 需要额外模型 |

**结论**: FTS5 适合大多数场景，向量搜索作为可选增强

### 3. 为什么文件系统是工作区限制？

- **安全性**：防止意外修改系统文件
- **可预测性**：Agent 只能在指定目录工作
- **可审计性**：所有操作都在可监控范围内

### 4. 流式输出 vs 批量输出

```python
# 批量输出（等待完整响应）
response = agent.invoke({"messages": messages})
print(response)

# 流式输出（实时响应）
async for token in agent.astream({"messages": messages}):
    print(token, end="", flush=True)
```

**优势**:
- 更好的用户体验
- 降低首字延迟（TTFF）
- 支持长时间运行的工具

---

## 与 OpenClaw 的对比

| 特性 | OpenClaw | mini-claw |
|------|----------|-----------|
| **语言** | TypeScript | Python |
| **框架** | 自定义 | LangChain/LangGraph |
| **UI** | Web + 多平台 | 控制台 |
| **搜索** | Brave/Perplexity 等（付费） | DuckDuckGo（免费） |
| **记忆** | QMD/Builtin | SQLite FTS5 |
| **部署** | 全栈应用 | 单脚本运行 |
| **复杂度** | 高（企业级） | 低（个人使用） |

---

## 扩展指南

### 添加新工具

```python
# 1. 创建工具类
class MyTool(BaseTool):
    name = "my_tool"
    description = "我的工具"
    args_schema = MyInput

    def _run(self, param: str) -> str:
        return f"处理: {param}"

# 2. 在 AgentManager._build_tools() 中注册
tools.append(MyTool())
```

### 添加新 LLM 提供商

```python
# 1. 创建提供商类
class MyProvider(LLMProvider):
    def get_model(self, model_id, ...):
        return ChatOpenAI(
            base_url="https://my-api.com/v1",
            api_key=self.api_key,
        )

# 2. 在配置中注册
models:
  providers:
    myprovider:
      api_key: ${MY_API_KEY}
      base_url: https://my-api.com/v1
```

### 添加新 Agent

```yaml
# config.yaml
agents:
  list:
    - id: main
      name: 通用助手

    - id: coder
      name: 编程助手
      model: deepseek-coder
```

---

## 总结

mini-claw 是一个**精简但完整**的 AI 助手系统：

- ✅ **核心功能完整**：记忆、工具、多 Agent、流式输出
- ✅ **架构清晰**：模块化设计，易于理解和扩展
- ✅ **开箱即用**：DuckDuckGo 免费搜索，无需 API key
- ✅ **生产就绪**：安全控制、错误处理、会话持久化

适用于个人学习、实验和轻量级 AI 助手应用场景。
