"""记忆搜索引擎 - 支持 FTS5 + 向量检索"""

from pathlib import Path
from typing import Any

from .indexer import MemoryIndexer, MemoryChunk, get_indexer


class MemorySearchEngine:
    """记忆搜索引擎"""

    def __init__(
        self,
        agent_dir: Path,
        config: dict[str, Any] | None = None,
    ):
        self.agent_dir = agent_dir
        self.config = config or {}

        # 获取索引器
        self.indexer = MemoryIndexer(agent_dir)

        # 向量检索配置
        self.vector_enabled = self.config.get("vector_enabled", False)
        self.embedding_model = None

        if self.vector_enabled:
            self._init_vector_search()

    def _init_vector_search(self) -> None:
        """初始化向量检索"""
        try:
            from sentence_transformers import SentenceTransformer

            model_name = self.config.get(
                "embedding_model",
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
            self.embedding_model = SentenceTransformer(model_name)
        except ImportError:
            print("警告: sentence-transformers 未安装，向量检索不可用")
            self.vector_enabled = False

    def search(
        self,
        query: str,
        mode: str = "auto",
        max_results: int = 10,
        min_score: float = 0.0,
    ) -> list[MemoryChunk]:
        """
        搜索记忆

        Args:
            query: 搜索查询
            mode: 搜索模式 ("fts5", "vector", "hybrid", "auto")
            max_results: 最大结果数
            min_score: 最低分数阈值

        Returns:
            搜索结果列表
        """
        if mode == "auto":
            # 自动选择模式
            if self.vector_enabled:
                mode = "hybrid" if self.config.get("hybrid_enabled", False) else "vector"
            else:
                mode = "fts5"

        if mode == "fts5":
            return self._search_fts5(query, max_results, min_score)
        elif mode == "vector":
            return self._search_vector(query, max_results, min_score)
        elif mode == "hybrid":
            return self._search_hybrid(query, max_results, min_score)
        else:
            raise ValueError(f"未知的搜索模式: {mode}")

    def _search_fts5(
        self,
        query: str,
        max_results: int,
        min_score: float,
    ) -> list[MemoryChunk]:
        """FTS5 全文搜索"""
        return self.indexer.search(query, max_results, min_score)

    def _search_vector(
        self,
        query: str,
        max_results: int,
        min_score: float,
    ) -> list[MemoryChunk]:
        """向量语义搜索"""
        if not self.embedding_model:
            # 回退到 FTS5
            return self._search_fts5(query, max_results, min_score)

        # 获取所有记忆块
        cursor = self.indexer._conn.cursor()
        cursor.execute("""
            SELECT source, start_line, end_line, content
            FROM chunks
        """)

        chunks = []
        embeddings = []

        for row in cursor.fetchall():
            chunks.append({
                "source": row["source"],
                "start_line": row["start_line"],
                "end_line": row["end_line"],
                "content": row["content"],
            })
            embeddings.append(row["content"])

        if not embeddings:
            return []

        # 计算查询向量
        import numpy as np

        query_embedding = self.embedding_model.encode(query)
        chunk_embeddings = self.embedding_model.encode(embeddings)

        # 计算余弦相似度
        similarities = np.dot(chunk_embeddings, query_embedding) / (
            np.linalg.norm(chunk_embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        # 排序并返回结果
        results = []
        for idx in np.argsort(similarities)[::-1][:max_results]:
            score = float(similarities[idx])
            if score >= min_score:
                chunk_data = chunks[idx]
                results.append(MemoryChunk(
                    source=chunk_data["source"],
                    start_line=chunk_data["start_line"],
                    end_line=chunk_data["end_line"],
                    content=chunk_data["content"],
                    score=score,
                ))

        return results

    def _search_hybrid(
        self,
        query: str,
        max_results: int,
        min_score: float,
    ) -> list[MemoryChunk]:
        """混合搜索（FTS5 + 向量）"""
        fts5_results = self._search_fts5(query, max_results * 2, min_score)
        vector_results = self._search_vector(query, max_results * 2, min_score)

        # 合并结果
        merged: dict[str, MemoryChunk] = {}

        for result in fts5_results:
            key = f"{result.source}:{result.start_line}:{result.end_line}"
            if key not in merged:
                merged[key] = result
            else:
                # 加权平均
                merged[key].score = (merged[key].score + result.score) / 2

        for result in vector_results:
            key = f"{result.source}:{result.start_line}:{result.end_line}"
            if key not in merged:
                merged[key] = result
            else:
                # 向量结果权重更高
                merged[key].score = (merged[key].score + result.score * 2) / 3

        # 排序并返回
        results = sorted(merged.values(), key=lambda x: x.score, reverse=True)
        return results[:max_results]

    def index_file(self, file_path: Path) -> None:
        """索引文件"""
        self.indexer.index_file(file_path)

    def get_memory_content(
        self,
        source: str,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        """获取记忆内容"""
        if start_line is not None and end_line is not None:
            content = self.indexer.get_chunk(source, start_line, end_line)
            if content:
                return content

        # 从文件读取
        file_path = self.agent_dir / source
        if not file_path.exists():
            return ""

        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        if start_line is not None or end_line is not None:
            start = max((start_line or 1) - 1, 0)
            end = min(end_line or len(lines), len(lines))
            selected = lines[start:end]
            return "\n".join(f"{start + i + 1:>6}|{line}" for i, line in enumerate(selected))

        return content

    def close(self) -> None:
        """关闭搜索引擎"""
        self.indexer.close()


# 全局搜索引擎实例
_search_engines: dict[str, MemorySearchEngine] = {}


def get_search_engine(agent_id: str, agent_dir: Path, config: dict[str, Any] | None = None) -> MemorySearchEngine:
    """获取 Agent 的记忆搜索引擎"""
    if agent_id not in _search_engines:
        _search_engines[agent_id] = MemorySearchEngine(agent_dir, config)
    return _search_engines[agent_id]
