"""Agent 协作工具"""

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from ..config import get_config


class SessionsSpawnInput(BaseModel):
    """sessions_spawn 工具输入"""
    task: str = Field(description="要执行的任务描述")
    agent_id: str = Field(default="main", description="使用的 Agent ID")
    label: str | None = Field(default=None, description="子会话标签")


class SessionsSpawnTool(BaseTool):
    """创建子 Agent 执行任务"""

    name: str = "sessions_spawn"
    description: str = """创建一个子 Agent 会话来执行特定任务。
任务完成后会自动返回结果。
task: 要执行的任务描述
agent_id: 要使用的 Agent ID（默认为 main）
label: 子会话标签（可选）
"""
    args_schema: type[BaseModel] = SessionsSpawnInput

    agent_manager: Any = None  # 延迟注入
    agent_id: str = "main"

    def _run(self, task: str, agent_id: str = "main", label: str | None = None) -> str:
        """同步版本（简单返回提示）"""
        return f"[子 Agent 任务] {task}\n（注意：子 Agent 功能需要在异步环境中运行）"

    async def _arun(self, task: str, agent_id: str = "main", label: str | None = None) -> str:
        """异步版本"""
        if self.agent_manager is None:
            return "错误: AgentManager 未初始化"

        try:
            config = get_config()

            # 检查 spawn 深度限制
            # TODO: 实现深度检查

            # 生成子会话 ID
            session_id = f"subagent-{uuid.uuid4().hex[:8]}"

            # 获取子会话目录
            sessions_dir = config.get_sessions_dir(agent_id)
            session_file = sessions_dir / f"{session_id}.json"

            # 创建会话
            from ..session_manager import SessionManager
            session_mgr = SessionManager(config.workspace_dir)

            # 初始化会话
            session_mgr.create_session(session_id, agent_id, label=label or f"Spawn: {task[:50]}")

            # 发送任务
            full_task = f"""你是被创建的子 Agent，负责执行以下任务。任务完成后请返回结果摘要。

任务: {task}

请：
1. 理解任务需求
2. 使用可用工具执行任务
3. 返回清晰的结果摘要

开始执行。"""

            # 收集响应
            response_parts = []
            async for event in self.agent_manager.astream(full_task, session_id, agent_id):
                if event.get("type") == "token":
                    response_parts.append(event.get("content", ""))
                elif event.get("type") == "error":
                    return f"子 Agent 执行出错: {event.get('content')}"

            response = "".join(response_parts)

            # 清理子会话（可选）
            # session_mgr.delete_session(session_id, agent_id)

            return f"""[子 Agent 任务完成]

任务: {task}

结果:
{response}"""

        except Exception as e:
            return f"子 Agent 执行失败: {e}"


class SubagentsInput(BaseModel):
    """subagents 工具输入"""
    action: str = Field(description="操作: list, status, kill")
    run_id: str | None = Field(default=None, description="运行 ID（用于 status 和 kill）")


class SubagentsTool(BaseTool):
    """管理子 Agent"""

    name: str = "subagents"
    description: str = """管理正在运行的子 Agent。
支持操作:
- list: 列出所有子 Agent
- status <run_id>: 查看子 Agent 状态
- kill <run_id>: 终止子 Agent
"""
    args_schema: type[BaseModel] = SubagentsInput

    agent_manager: Any = None

    def _run(self, action: str, run_id: str | None = None) -> str:
        """执行子 Agent 管理操作"""

        if action == "list":
            # TODO: 实现子 Agent 列表
            return "当前没有正在运行的子 Agent"

        elif action == "status":
            if not run_id:
                return "请提供 run_id"
            # TODO: 实现状态查询
            return f"子 Agent {run_id} 状态未知"

        elif action == "kill":
            if not run_id:
                return "请提供 run_id"
            # TODO: 实现终止功能
            return f"子 Agent {run_id} 终止功能未实现"

        else:
            return f"未知操作: {action}"


class ResetInput(BaseModel):
    """reset 工具输入"""
    pass


class ResetTool(BaseTool):
    """重置当前会话"""

    name: str = "reset"
    description: str = "重置当前会话，清除所有历史记录"
    args_schema: type[BaseModel] = ResetInput

    session_manager: Any = None
    session_id: str = "main"
    agent_id: str = "main"

    def _run(self) -> str:
        if self.session_manager is None:
            return "错误: SessionManager 未初始化"

        try:
            self.session_manager.reset_session(self.session_id, self.agent_id)
            return "会话已重置"
        except Exception as e:
            return f"重置失败: {e}"
