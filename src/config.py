"""配置管理模块"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


@dataclass
class ModelProviderConfig:
    """LLM 提供商配置"""
    api_key: str | None = None
    base_url: str = ""
    models: list[str] = field(default_factory=list)


@dataclass
class AgentDefaultsConfig:
    """Agent 默认配置"""
    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 4096
    memory_enabled: bool = True
    memory_vector_enabled: bool = False
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    max_spawn_depth: int = 2
    max_children_per_agent: int = 5
    heartbeat_enabled: bool = True
    heartbeat_interval_minutes: int = 30


@dataclass
class AgentConfig:
    """单个 Agent 配置"""
    id: str
    name: str
    description: str = ""
    model: str = ""


@dataclass
class ToolsConfig:
    """工具配置"""
    workspace_only: bool = True
    readonly_dirs: list[str] = field(default_factory=list)
    web_search_provider: str = "duckduckgo"


@dataclass
class MemorySearchConfig:
    """记忆搜索配置"""
    fts5_enabled: bool = True
    vector_enabled: bool = False
    hybrid_enabled: bool = False


@dataclass
class Config:
    """全局配置"""

    workspace_dir: Path
    models: dict[str, ModelProviderConfig]
    agent_defaults: AgentDefaultsConfig
    agents: list[AgentConfig]
    tools: ToolsConfig
    memory_search: MemorySearchConfig

    # 运行时状态
    _env_vars: dict[str, str] = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, config_path: str | Path = "config.yaml") -> "Config":
        """加载配置文件"""
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # 解析环境变量
        env_vars = {}
        for key, value in os.environ.items():
            env_vars[key] = value

        # 解析模型提供商配置
        models = {}
        for provider_id, provider_data in data.get("models", {}).get("providers", {}).items():
            api_key = provider_data.get("api_key", "")
            # 替换环境变量
            if api_key and api_key.startswith("${") and api_key.endswith("}"):
                env_key = api_key[2:-1]
                api_key = env_vars.get(env_key, "")

            models[provider_id] = ModelProviderConfig(
                api_key=api_key,
                base_url=provider_data.get("base_url", ""),
                models=provider_data.get("models", []),
            )

        # 解析 Agent 默认配置
        defaults_data = data.get("agents", {}).get("defaults", {})
        agent_defaults = AgentDefaultsConfig(
            model=defaults_data.get("model", "deepseek-chat"),
            temperature=defaults_data.get("temperature", 0.7),
            max_tokens=defaults_data.get("max_tokens", 4096),
            memory_enabled=defaults_data.get("memory", {}).get("enabled", True),
            memory_vector_enabled=defaults_data.get("memory", {}).get("vector_enabled", False),
            embedding_model=defaults_data.get("memory", {}).get("embedding_model",
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
            max_spawn_depth=defaults_data.get("subagents", {}).get("max_spawn_depth", 2),
            max_children_per_agent=defaults_data.get("subagents", {}).get("max_children_per_agent", 5),
            heartbeat_enabled=defaults_data.get("heartbeat", {}).get("enabled", True),
            heartbeat_interval_minutes=defaults_data.get("heartbeat", {}).get("interval_minutes", 30),
        )

        # 解析 Agent 列表
        agents = []
        for agent_data in data.get("agents", {}).get("list", []):
            agents.append(AgentConfig(
                id=agent_data.get("id", "main"),
                name=agent_data.get("name", "Assistant"),
                description=agent_data.get("description", ""),
                model=agent_data.get("model", agent_defaults.model),
            ))

        # 解析工具配置
        tools_data = data.get("tools", {})
        fs_data = tools_data.get("fs", {})
        web_data = tools_data.get("web", {})
        tools = ToolsConfig(
            workspace_only=fs_data.get("workspace_only", True),
            readonly_dirs=fs_data.get("readonly_dirs", []),
            web_search_provider=web_data.get("search", {}).get("provider", "duckduckgo"),
        )

        # 解析记忆搜索配置
        memory_search_data = data.get("memory_search", {})
        memory_search = MemorySearchConfig(
            fts5_enabled=memory_search_data.get("fts5", {}).get("enabled", True),
            vector_enabled=memory_search_data.get("vector", {}).get("enabled", False),
            hybrid_enabled=memory_search_data.get("hybrid", {}).get("enabled", False),
        )

        # 工作目录
        workspace_dir = Path(data.get("workspace_dir", "./workspace"))
        workspace_dir = workspace_dir.expanduser().resolve()

        return cls(
            workspace_dir=workspace_dir,
            models=models,
            agent_defaults=agent_defaults,
            agents=agents,
            tools=tools,
            memory_search=memory_search,
            _env_vars=env_vars,
        )

    def get_agent_config(self, agent_id: str) -> AgentConfig | None:
        """获取指定 Agent 的配置"""
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        return None

    def get_provider_for_model(self, model: str) -> str | None:
        """获取模型对应的提供商"""
        for provider_id, provider_config in self.models.items():
            if model in provider_config.models:
                return provider_id
        return None

    def get_model_api_key(self, model: str) -> str | None:
        """获取模型的 API key"""
        provider_id = self.get_provider_for_model(model)
        if provider_id:
            return self.models[provider_id].api_key
        return None

    def get_model_base_url(self, model: str) -> str:
        """获取模型的基础 URL"""
        provider_id = self.get_provider_for_model(model)
        if provider_id:
            return self.models[provider_id].base_url
        return ""

    def get_agent_dir(self, agent_id: str) -> Path:
        """获取 Agent 的工作目录"""
        return self.workspace_dir / "agents" / agent_id

    def get_sessions_dir(self, agent_id: str) -> Path:
        """获取 Agent 的会话目录"""
        return self.get_agent_dir(agent_id) / "sessions"

    def get_memory_dir(self, agent_id: str) -> Path:
        """获取 Agent 的记忆目录"""
        return self.get_agent_dir(agent_id) / "memory"

    def get_skills_dir(self, agent_id: str) -> Path:
        """获取 Agent 的技能目录"""
        return self.get_agent_dir(agent_id) / "skills"


# 全局配置实例
_global_config: Config | None = None


def get_config() -> Config:
    """获取全局配置实例"""
    global _global_config
    if _global_config is None:
        _global_config = Config.load()
    return _global_config


def set_config(config: Config) -> None:
    """设置全局配置实例"""
    global _global_config
    _global_config = config
