"""Agent 核心引擎模块"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from .config import get_config, Config
from .session_manager import get_session_manager, SessionManager
from .memory.search import get_search_engine, MemorySearchEngine
from .prompts.system import build_system_prompt, get_tools_list
from .llm.providers import get_model
from .llm.simple_callbacks import SimpleCallback


@dataclass
class AgentState:
    """Agent 状态"""
    agent_id: str
    total_tokens: int = 0
    total_turns: int = 0
    last_active: float = 0.0
    tools: list[BaseTool] = field(default_factory=list)
    memory_engine: MemorySearchEngine | None = None


class CommandParser:
    """命令解析器"""

    # 命令正则表达式
    COMMANDS = {
        r"/new": "new",
        r"/reset": "reset",
        r"/compact": "compact",
        r"/help": "help",
        r"/exit": "exit",
        r"/quit": "exit",
    }

    @classmethod
    def parse(cls, message: str) -> tuple[str | None, str | None, str]:
        """解析命令

        Returns:
            (command, action, remaining_message)
        """
        message = message.strip()

        # 检查是否是命令
        for pattern, action in cls.COMMANDS.items():
            if re.match(pattern, message, re.IGNORECASE):
                return action, action, ""

        return None, None, message


class AgentManager:
    """Agent 管理器 - 核心引擎"""

    def __init__(self, config: Config | None = None):
        self.config = config or get_config()
        self.states: dict[str, AgentState] = {}
        self.session_manager = get_session_manager(self.config.workspace_dir)

        # 初始化 LLM 提供商
        from .llm.providers import LLMProviderFactory
        LLMProviderFactory.create_from_config(self.config.models)

    def _get_agent_state(self, agent_id: str) -> AgentState:
        """获取或创建 Agent 状态"""
        if agent_id not in self.states:
            agent_dir = self.config.get_agent_dir(agent_id)

            # 创建默认文件
            from .prompts.system import create_default_agent_files
            create_default_agent_files(agent_dir)

            # 初始化记忆引擎
            memory_engine = get_search_engine(
                agent_id,
                agent_dir,
                {
                    "vector_enabled": self.config.agent_defaults.memory_vector_enabled,
                    "hybrid_enabled": self.config.memory_search.hybrid_enabled,
                },
            )

            self.states[agent_id] = AgentState(
                agent_id=agent_id,
                memory_engine=memory_engine,
            )

        return self.states[agent_id]

    def _build_tools(self, agent_id: str) -> list[BaseTool]:
        """构建工具列表"""
        from .tools.file_tools import ReadTool, WriteTool, EditTool, ListTool
        from .tools.exec_tools import ExecTool, PwdTool
        from .tools.memory_tools import MemorySearchTool, MemoryGetTool, MemoryWriteTool
        from .tools.agent_tools import ResetTool
        from .tools.web_tools import create_web_tools

        agent_dir = self.config.get_agent_dir(agent_id)

        tools = [
            # 文件工具
            ReadTool(root_dir=agent_dir, readonly_dirs=self.config.tools.readonly_dirs),
            WriteTool(root_dir=agent_dir),
            EditTool(root_dir=agent_dir),
            ListTool(root_dir=agent_dir),

            # 执行工具
            ExecTool(),
            PwdTool(),

            # 记忆工具
            MemorySearchTool(agent_id=agent_id, agent_dir=agent_dir),
            MemoryGetTool(agent_id=agent_id, agent_dir=agent_dir),
            MemoryWriteTool(agent_id=agent_id, agent_dir=agent_dir),

            # Agent 工具
            ResetTool(session_manager=self.session_manager),
        ]

        # 添加网络工具
        web_provider = self.config.tools.web_search_provider
        web_tools = create_web_tools(provider=web_provider)
        tools.extend(web_tools)

        return tools

    async def astream(
        self,
        message: str,
        session_id: str = "main",
        agent_id: str = "main",
    ) -> AsyncIterator[dict]:
        """流式处理消息

        Args:
            message: 用户消息
            session_id: 会话 ID
            agent_id: Agent ID

        Yields:
            事件字典，包含 type 和 content 字段
        """
        # 解析命令
        command, action, remaining = CommandParser.parse(message)

        if action == "exit":
            yield {"type": "exit", "content": "再见！"}
            return

        if action == "help":
            yield {"type": "message", "content": self._get_help_text()}
            return

        if action == "new":
            # 创建新会话
            new_session_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            self.session_manager.create_session(new_session_id, agent_id, label="新会话")
            yield {"type": "message", "content": f"已创建新会话: {new_session_id}"}
            return

        if action == "reset":
            # 重置会话
            self.session_manager.reset_session(session_id, agent_id)
            yield {"type": "message", "content": "会话已重置"}
            message = "[系统消息: 会话已重置]"
        elif command:
            yield {"type": "message", "content": f"未知命令: {command}"}
            return

        # 获取 Agent 状态
        agent_state = self._get_agent_state(agent_id)

        # 获取或创建会话
        self.session_manager.create_session(session_id, agent_id)

        # 保存用户消息
        self.session_manager.save_message(session_id, agent_id, "user", message)

        # 获取工具
        tools = self._build_tools(agent_id)
        agent_state.tools = tools

        # 获取模型
        agent_config = self.config.get_agent_config(agent_id)
        model_id = agent_config.model if agent_config else self.config.agent_defaults.model

        model = get_model(
            model_id,
            temperature=self.config.agent_defaults.temperature,
            max_tokens=self.config.agent_defaults.max_tokens,
        )

        # 构建系统提示词
        system_prompt = build_system_prompt(
            agent_id=agent_id,
            tools_description=get_tools_list(tools),
        )

        # 加载会话历史
        messages = self.session_manager.get_messages_for_llm(session_id, agent_id)

        # 简洁日志
        logger.info(f">>> 用户: {message[:100]}{'...' if len(message) > 100 else ''}")

        # 转换为 LangChain 消息格式
        lc_messages = []

        # 添加系统消息
        lc_messages.append(SystemMessage(content=system_prompt))

        # 添加历史消息
        for msg in messages:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))

        # 创建 LangGraph Agent
        agent = create_react_agent(
            model,
            tools=tools,
        )

        # 执行并获取响应
        full_response = ""

        try:
            result = await agent.ainvoke(
                {"messages": lc_messages},
                config={
                    "recursion_limit": 50,
                    "callbacks": [SimpleCallback()],
                },
            )

            # 解析响应
            if "messages" in result:
                messages = result["messages"]
                for msg in reversed(messages):
                    if msg.type == "ai" and hasattr(msg, "content") and msg.content:
                        full_response = msg.content
                        yield {"type": "token", "content": full_response}
                        break

        except Exception as e:
            logger.error(f"错误: {e}")
            yield {"type": "error", "content": f"执行出错: {e}"}
            return

        # 保存助手响应
        if full_response:
            self.session_manager.save_message(session_id, agent_id, "assistant", full_response)
            logger.info(f"<<< AI: {full_response[:150]}{'...' if len(full_response) > 150 else ''}")

        # 更新状态
        agent_state.total_turns += 1
        agent_state.last_active = datetime.now().timestamp()

        yield {"type": "done", "content": ""}

    def _get_help_text(self) -> str:
        """获取帮助文本"""
        return """mini-claw 控制台命令:

/new      - 创建新会话
/reset    - 重置当前会话
/compact  - 压缩会话历史
/help     - 显示帮助
/exit     - 退出程序

可用工具:
- read        : 读取文件
- write       : 写入文件
- edit        : 编辑文件
- ls          : 列出目录
- exec        : 执行命令
- pwd         : 当前目录
- memory_search : 搜索记忆
- memory_get    : 获取记忆
- memory_write  : 写入记忆
- web_search   : 网络搜索 (DuckDuckGo)
- web_fetch    : 抓取网页内容
"""
