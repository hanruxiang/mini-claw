"""记忆索引器 - 基于 SQLite FTS5 全文搜索"""

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class MemoryChunk:
    """记忆块"""
    source: str
    start_line: int
    end_line: int
    content: str
    score: float = 0.0


class MemoryIndexer:
    """记忆索引器"""

    def __init__(self, agent_dir: Path):
        self.agent_dir = agent_dir
        self.db_path = agent_dir / ".memory_index.db"
        self._conn: sqlite3.Connection | None = None
        self._file_hashes: dict[str, str] = {}

        # 初始化数据库
        self._init_db()

        # 索引现有记忆文件
        self._index_existing_files()

    def _init_db(self) -> None:
        """初始化数据库"""
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        cursor = self._conn.cursor()

        # 创建记忆块表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建 FTS5 全文搜索虚拟表
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                source, content,
                content='chunks',
                content_rowid='id'
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source)
        """)

        self._conn.commit()

    def _index_existing_files(self) -> None:
        """索引现有记忆文件"""
        memory_dir = self.agent_dir / "memory"
        memory_md = self.agent_dir / "MEMORY.md"

        files_to_index = []

        # 索引 MEMORY.md
        if memory_md.exists():
            files_to_index.append(memory_md)

        # 索引 memory/ 目录下的文件
        if memory_dir.exists():
            files_to_index.extend(memory_dir.glob("*.md"))

        for file_path in files_to_index:
            self.index_file(file_path)

    def _get_file_hash(self, file_path: Path) -> str:
        """计算文件哈希"""
        content = file_path.read_text(encoding="utf-8")
        return hashlib.md5(content.encode()).hexdigest()

    def _chunk_file(self, file_path: Path) -> list[tuple[int, int, str]]:
        """将文件分块（按段落）"""
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        chunks = []
        current_chunk_start = 0
        current_chunk_lines = []

        for i, line in enumerate(lines):
            # 跳过空行作为分隔符
            if line.strip() == "" and current_chunk_lines:
                # 保存当前块
                chunks.append((
                    current_chunk_start,
                    i - 1,
                    "\n".join(current_chunk_lines),
                ))
                current_chunk_lines = []
                current_chunk_start = i + 1
            else:
                current_chunk_lines.append(line)

        # 保存最后一个块
        if current_chunk_lines:
            chunks.append((
                current_chunk_start,
                len(lines) - 1,
                "\n".join(current_chunk_lines),
            ))

        return chunks

    def index_file(self, file_path: Path) -> None:
        """索引记忆文件"""
        if not file_path.exists():
            return

        relative_path = file_path.relative_to(self.agent_dir)
        source = str(relative_path)

        # 检查文件是否已变更
        current_hash = self._get_file_hash(file_path)
        if source in self._file_hashes and self._file_hashes[source] == current_hash:
            return

        # 删除旧的索引
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM chunks WHERE source = ?", (source,))
        cursor.execute("DELETE FROM chunks_fts WHERE rowid IN (SELECT id FROM chunks WHERE source = ?)", (source,))

        # 分块并索引
        chunks = self._chunk_file(file_path)

        for start_line, end_line, content in chunks:
            if not content.strip():
                continue

            content_hash = hashlib.md5(content.encode()).hexdigest()

            cursor.execute("""
                INSERT INTO chunks (source, start_line, end_line, content, content_hash)
                VALUES (?, ?, ?, ?, ?)
            """, (source, start_line, end_line, content, content_hash))

        self._conn.commit()
        self._file_hashes[source] = current_hash

    def search(
        self,
        query: str,
        max_results: int = 10,
        min_score: float = 0.0,
    ) -> list[MemoryChunk]:
        """搜索记忆"""
        cursor = self._conn.cursor()

        # 使用 FTS5 全文搜索
        cursor.execute("""
            SELECT
                c.source,
                c.start_line,
                c.end_line,
                c.content,
                bm25(chunks_fts) AS score
            FROM chunks c
            JOIN chunks_fts f ON c.id = f.rowid
            WHERE chunks_fts MATCH ?
            ORDER BY score
            LIMIT ?
        """, (query, max_results))

        results = []
        for row in cursor.fetchall():
            score = -row["score"] / 100.0  # BM25 分数转换为 0-1
            if score >= min_score:
                results.append(MemoryChunk(
                    source=row["source"],
                    start_line=row["start_line"],
                    end_line=row["end_line"],
                    content=row["content"],
                    score=score,
                ))

        return results

    def get_chunk(
        self,
        source: str,
        start_line: int,
        end_line: int,
    ) -> str | None:
        """获取指定记忆块的内容"""
        cursor = self._conn.cursor()

        cursor.execute("""
            SELECT content
            FROM chunks
            WHERE source = ? AND start_line = ? AND end_line = ?
        """, (source, start_line, end_line))

        row = cursor.fetchone()
        if row:
            return row["content"]
        return None

    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None


# 全局索引器实例
_indexers: dict[str, MemoryIndexer] = {}


def get_indexer(agent_id: str, agent_dir: Path) -> MemoryIndexer:
    """获取 Agent 的记忆索引器"""
    if agent_id not in _indexers:
        _indexers[agent_id] = MemoryIndexer(agent_dir)
    return _indexers[agent_id]
