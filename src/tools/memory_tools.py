"""记忆操作工具"""

from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from ..memory.search import get_search_engine
from ..config import get_config


class MemorySearchInput(BaseModel):
    """memory_search 工具输入"""
    query: str = Field(description="搜索查询")
    max_results: int = Field(default=6, description="最大结果数")
    min_score: float = Field(default=0.0, description="最低相关度分数")


class MemorySearchTool(BaseTool):
    """在记忆中搜索"""

    name: str = "memory_search"
    description: str = """在 MEMORY.md 和 memory/*.md 中搜索相关信息。
返回带路径和行号的相关片段。
使用语义搜索找到相关内容。
"""
    args_schema: type[BaseModel] = MemorySearchInput

    agent_id: str = "main"
    agent_dir: Path | None = None

    def _get_search_engine(self):
        """获取搜索引擎实例"""
        if self.agent_dir is None:
            config = get_config()
            self.agent_dir = config.get_agent_dir(self.agent_id)

        return get_search_engine(self.agent_id)

    def _run(self, query: str, max_results: int = 6, min_score: float = 0.0) -> str:
        try:
            engine = self._get_search_engine()
            results = engine.search(query, max_results=max_results, min_score=min_score)

            if not results:
                return f"未找到与 \"{query}\" 相关的记忆"

            output = [f"找到 {len(results)} 条相关记忆:\n"]

            for i, result in enumerate(results, 1):
                output.append(f"\n{i}. {result.source} (行 {result.start_line}-{result.end_line}) [相关度: {result.score:.2f}]")
                output.append(f"   {result.content[:200]}...")

            return "\n".join(output)

        except Exception as e:
            return f"搜索失败: {e}"


class MemoryGetInput(BaseModel):
    """memory_get 工具输入"""
    source: str = Field(description="记忆文件路径（相对于 agent 目录）")
    start_line: int | None = Field(default=None, description="起始行号")
    end_line: int | None = Field(default=None, description="结束行号")


class MemoryGetTool(BaseTool):
    """获取记忆内容"""

    name: str = "memory_get"
    description: str = """读取特定记忆文件的完整内容或指定行范围。
source: 文件路径（如 MEMORY.md, memory/2026-03-06.md）
start_line: 起始行号（可选）
end_line: 结束行号（可选）
"""
    args_schema: type[BaseModel] = MemoryGetInput

    agent_id: str = "main"
    agent_dir: Path | None = None

    def _get_search_engine(self):
        """获取搜索引擎实例"""
        if self.agent_dir is None:
            config = get_config()
            self.agent_dir = config.get_agent_dir(self.agent_id)

        return get_search_engine(self.agent_id)

    def _run(self, source: str, start_line: int | None = None, end_line: int | None = None) -> str:
        try:
            engine = self._get_search_engine()
            content = engine.get_memory_content(source, start_line, end_line)

            if not content:
                return f"记忆文件为空或不存在: {source}"

            return f"=== {source} ===\n\n{content}"

        except Exception as e:
            return f"读取失败: {e}"


class MemoryWriteInput(BaseModel):
    """memory_write 工具输入"""
    content: str = Field(description="要写入记忆的内容")
    file: str = Field(default="memory/today.md", description="目标文件（默认为 memory/today.md）")


class MemoryWriteTool(BaseTool):
    """写入记忆"""

    name: str = "memory_write"
    description: str = """将重要信息写入记忆文件。
默认追加到 memory/today.md，会自动使用正确的日期文件名。
content: 要写入的内容
"""
    args_schema: type[BaseModel] = MemoryWriteInput

    agent_id: str = "main"
    agent_dir: Path | None = None

    def _get_agent_dir(self) -> Path:
        """获取 Agent 目录"""
        if self.agent_dir is None:
            config = get_config()
            self.agent_dir = config.get_agent_dir(self.agent_id)
        return self.agent_dir

    def _run(self, content: str, file: str = "memory/today.md") -> str:
        try:
            agent_dir = self._get_agent_dir()

            # 处理 today.md 为实际日期
            if file == "memory/today.md" or file == "today.md":
                from datetime import datetime
                file = f"memory/{datetime.now().strftime('%Y-%m-%d')}.md"

            file_path = agent_dir / file

            # 创建父目录
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # 追加内容
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"\n{content}\n")

            # 重新索引
            from ..memory.search import get_search_engine
            engine = get_search_engine(self.agent_id, agent_dir)
            engine.index_file(file_path)

            return f"已写入记忆: {file} ({len(content)} 字符)"

        except Exception as e:
            return f"写入失败: {e}"
