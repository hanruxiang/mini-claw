"""网络搜索工具"""

from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class WebSearchInput(BaseModel):
    """web_search 工具输入"""
    query: str = Field(description="搜索查询")


class DuckDuckGoSearchTool(BaseTool):
    """DuckDuckGo 搜索工具（免费，无需 API）"""

    name: str = "web_search"
    description: str = """使用 DuckDuckGo 搜索网络信息。
返回相关的搜索结果摘要和链接。
"""
    args_schema: type[BaseModel] = WebSearchInput

    max_results: int = 5

    def _run(self, query: str) -> str:
        try:
            from duckduckgo_search import DDGS

            ddgs = DDGS()
            results = list(ddgs.text(
                query,
                max_results=self.max_results,
            ))

            if not results:
                return f"未找到与 \"{query}\" 相关的搜索结果"

            output = [f"找到 {len(results)} 条搜索结果:\n"]

            for i, result in enumerate(results, 1):
                title = result.get("title", "")
                url = result.get("link", "")
                body = result.get("body", "")

                output.append(f"\n{i}. {title}")
                output.append(f"   URL: {url}")
                if body:
                    output.append(f"   摘要: {body[:200]}...")

            return "\n".join(output)

        except ImportError:
            return "错误: duckduckgo_search 未安装，请运行: pip install duckduckgo-search"
        except Exception as e:
            return f"搜索失败: {e}"


class WebFetchInput(BaseModel):
    """web_fetch 工具输入"""
    url: str = Field(description="要抓取的网页 URL")


class WebFetchTool(BaseTool):
    """网页内容抓取工具"""

    name: str = "web_fetch"
    description: str = """获取网页的完整内容。
返回网页的文本内容（去除 HTML 标签）。
"""
    args_schema: type[BaseModel] = WebFetchInput

    max_length: int = 10000  # 最大字符数

    def _run(self, url: str) -> str:
        try:
            import requests
            from bs4 import BeautifulSoup

            # 获取网页
            response = requests.get(url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            })
            response.raise_for_status()

            # 解析内容
            soup = BeautifulSoup(response.text, "html.parser")

            # 移除脚本和样式
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()

            # 获取文本
            text = soup.get_text(separator="\n", strip=True)

            # 清理空行
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            text = "\n".join(lines)

            # 限制长度
            if len(text) > self.max_length:
                text = text[:self.max_length] + "\n... (内容已截断)"

            return f"=== 网页内容 ===\nURL: {url}\n\n{text}"

        except ImportError:
            return "错误: requests 或 beautifulsoup4 未安装，请运行: pip install requests beautifulsoup4"
        except Exception as e:
            return f"抓取失败: {e}"


class TavilySearchInput(BaseModel):
    """tavily_search 工具输入"""
    query: str = Field(description="搜索查询")
    max_results: int = Field(default=5, description="最大结果数")


class TavilySearchTool(BaseTool):
    """Tavily 搜索工具（需要 API Key，搜索质量好）"""

    name: str = "tavily_search"
    description: str = """使用 Tavily AI 搜索引擎进行高质量搜索。
专门为 AI 优化的搜索结果。
"""
    args_schema: type[BaseModel] = TavilySearchInput

    api_key: str = ""
    max_results: int = 5

    def _run(self, query: str, max_results: int = 5) -> str:
        if not self.api_key:
            return "错误: TAVILY_API_KEY 未配置"

        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=self.api_key)

            response = client.search(
                query=query,
                max_results=max_results,
                search_depth="basic",
            )

            results = response.get("results", [])

            if not results:
                return f"未找到与 \"{query}\" 相关的搜索结果"

            output = [f"找到 {len(results)} 条搜索结果:\n"]

            for i, result in enumerate(results, 1):
                title = result.get("title", "")
                url = result.get("url", "")
                content = result.get("content", "")

                output.append(f"\n{i}. {title}")
                output.append(f"   URL: {url}")
                if content:
                    output.append(f"   内容: {content[:300]}...")

            return "\n".join(output)

        except ImportError:
            return "错误: tavily-python 未安装，请运行: pip install tavily-python"
        except Exception as e:
            return f"搜索失败: {e}"


def create_web_tools(provider: str = "duckduckgo", api_key: str = "") -> list[BaseTool]:
    """创建网络工具

    Args:
        provider: 搜索提供商 ("duckduckgo", "tavily")
        api_key: API Key（某些提供商需要）
    """
    tools = []

    if provider == "tavily" and api_key:
        tools.append(TavilySearchTool(api_key=api_key))
    else:
        # 默认使用 DuckDuckGo
        tools.append(DuckDuckGoSearchTool())

    # 添加网页抓取工具
    tools.append(WebFetchTool())

    return tools
