"""会话管理模块"""

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any


@dataclass
class SessionData:
    """会话数据"""
    session_id: str
    agent_id: str
    label: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    messages: list[dict[str, Any]] = field(default_factory=list)
    compressed_context: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class SessionManager:
    """会话管理器"""

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = Path(workspace_dir)
        self._locks: dict[str, threading.RLock] = {}
        self._cache: dict[str, SessionData] = {}

    def _get_lock(self, session_id: str) -> threading.RLock:
        """获取会话锁（可重入锁）"""
        if session_id not in self._locks:
            self._locks[session_id] = threading.RLock()
        return self._locks[session_id]

    def _get_session_file(self, session_id: str, agent_id: str) -> Path:
        """获取会话文件路径"""
        agents_dir = self.workspace_dir / "agents"
        sessions_dir = agents_dir / agent_id / "sessions"
        return sessions_dir / f"{session_id}.json"

    def create_session(
        self,
        session_id: str,
        agent_id: str,
        label: str = "",
    ) -> SessionData:
        """创建新会话"""
        with self._get_lock(session_id):
            session_file = self._get_session_file(session_id, agent_id)

            # 如果会话已存在，直接加载
            if session_file.exists():
                return self.load_session(session_id, agent_id)

            # 创建新会话
            session_data = SessionData(
                session_id=session_id,
                agent_id=agent_id,
                label=label,
            )

            # 保存到文件
            session_file.parent.mkdir(parents=True, exist_ok=True)
            self._save_session_file(session_file, session_data)

            # 加入缓存
            self._cache[session_id] = session_data

            return session_data

    def load_session(self, session_id: str, agent_id: str) -> SessionData:
        """加载会话"""
        # 先检查缓存
        if session_id in self._cache:
            return self._cache[session_id]

        with self._get_lock(session_id):
            session_file = self._get_session_file(session_id, agent_id)

            if not session_file.exists():
                # 创建新会话
                return self.create_session(session_id, agent_id)

            # 从文件加载
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            session_data = SessionData(**data)

            # 加入缓存
            self._cache[session_id] = session_data

            return session_data

    def save_message(
        self,
        session_id: str,
        agent_id: str,
        role: str,
        content: str,
    ) -> None:
        """保存消息"""
        with self._get_lock(session_id):
            session_data = self.load_session(session_id, agent_id)

            # 添加消息
            session_data.messages.append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
            })

            # 更新时间戳
            session_data.updated_at = datetime.now().isoformat()

            # 保存到文件
            session_file = self._get_session_file(session_id, agent_id)
            self._save_session_file(session_file, session_data)

            # 更新缓存
            self._cache[session_id] = session_data

    def reset_session(self, session_id: str, agent_id: str) -> None:
        """重置会话"""
        with self._get_lock(session_id):
            session_data = self.load_session(session_id, agent_id)

            # 清空消息
            session_data.messages = []
            session_data.compressed_context = ""
            session_data.updated_at = datetime.now().isoformat()

            # 保存到文件
            session_file = self._get_session_file(session_id, agent_id)
            self._save_session_file(session_file, session_data)

            # 更新缓存
            self._cache[session_id] = session_data

    def delete_session(self, session_id: str, agent_id: str) -> None:
        """删除会话"""
        with self._get_lock(session_id):
            session_file = self._get_session_file(session_id, agent_id)

            # 删除文件
            if session_file.exists():
                session_file.unlink()

            # 从缓存移除
            if session_id in self._cache:
                del self._cache[session_id]

    def get_messages_for_llm(
        self,
        session_id: str,
        agent_id: str,
    ) -> list[dict[str, str]]:
        """获取适合 LLM 的消息列表"""
        session_data = self.load_session(session_id, agent_id)

        messages = []

        # 添加压缩上下文（如果有）
        if session_data.compressed_context:
            messages.append({
                "role": "assistant",
                "content": f"[以下是之前对话的摘要]\n{session_data.compressed_context}",
            })

        # 合并连续的 assistant 消息
        last_role = None
        for msg in session_data.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # 如果是连续的 assistant 消息，合并它们
            if last_role == "assistant" and role == "assistant":
                messages[-1]["content"] += "\n\n" + content
            else:
                messages.append({"role": role, "content": content})

            last_role = role

        return messages

    def compress_session(
        self,
        session_id: str,
        agent_id: str,
        summary: str,
        keep_recent: int = 5,
    ) -> None:
        """压缩会话历史"""
        with self._get_lock(session_id):
            session_data = self.load_session(session_id, agent_id)

            # 保存压缩摘要
            session_data.compressed_context = summary

            # 保留最近的消息
            if keep_recent > 0:
                session_data.messages = session_data.messages[-keep_recent:]
            else:
                session_data.messages = []

            # 保存到文件
            session_file = self._get_session_file(session_id, agent_id)
            self._save_session_file(session_file, session_data)

            # 更新缓存
            self._cache[session_id] = session_data

    def list_sessions(self, agent_id: str) -> list[dict[str, Any]]:
        """列出 Agent 的所有会话"""
        agents_dir = self.workspace_dir / "agents"
        sessions_dir = agents_dir / agent_id / "sessions"

        if not sessions_dir.exists():
            return []

        sessions = []
        for session_file in sessions_dir.glob("*.json"):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                sessions.append({
                    "session_id": data.get("session_id", session_file.stem),
                    "label": data.get("label", ""),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "message_count": len(data.get("messages", [])),
                })
            except Exception:
                pass

        return sorted(sessions, key=lambda x: x["updated_at"], reverse=True)

    def _save_session_file(self, session_file: Path, session_data: SessionData) -> None:
        """保存会话文件"""
        session_file.parent.mkdir(parents=True, exist_ok=True)

        with open(session_file, "w", encoding="utf-8") as f:
            json.dump({
                "session_id": session_data.session_id,
                "agent_id": session_data.agent_id,
                "label": session_data.label,
                "created_at": session_data.created_at,
                "updated_at": session_data.updated_at,
                "messages": session_data.messages,
                "compressed_context": session_data.compressed_context,
                "metadata": session_data.metadata,
            }, f, ensure_ascii=False, indent=2)


# 全局会话管理器实例
_session_managers: dict[Path, SessionManager] = {}


def get_session_manager(workspace_dir: Path) -> SessionManager:
    """获取会话管理器实例"""
    workspace_dir = Path(workspace_dir).resolve()

    if workspace_dir not in _session_managers:
        _session_managers[workspace_dir] = SessionManager(workspace_dir)

    return _session_managers[workspace_dir]
