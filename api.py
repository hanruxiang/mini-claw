#!/usr/bin/env python3
"""mini-claw API 服务"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

# 配置日志
from pathlib import Path
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "api.log"),
        logging.StreamHandler()  # 同时输出到控制台
    ]
)

from src.config import Config, set_config
from src.agent_manager import AgentManager

# 配置其他模块日志级别
for logger_name in ['httpx', 'httpcore']:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

# 静态文件目录
static_dir = Path(__file__).parent / "static"


# 全局配置 - 强制重新加载
config = Config.load()
set_config(config)  # 设置全局配置缓存
agent_manager = AgentManager(config)


# 请求/响应模型
class ChatRequest(BaseModel):
    message: str
    session_id: str = "main"
    agent_id: str = "main"


class ChatResponse(BaseModel):
    response: str
    session_id: str
    agent_id: str


class ChatStreamChunk(BaseModel):
    type: str  # "thinking", "token", "tool", "done", "error"
    content: str = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("🚀 mini-claw API 服务启动")
    print(f"📁 工作目录: {config.workspace_dir}")
    print(f"🤖 可用 Agent: {[a.name for a in config.agents]}")
    yield
    print("👋 mini-claw API 服务关闭")


app = FastAPI(
    title="mini-claw API",
    description="基于 LangChain/LangGraph 的 AI 助手 API",
    version="1.0.0",
    lifespan=lifespan
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """主页 - 返回聊天界面"""
    return FileResponse(static_dir / "index.html")


@app.get("/api")
async def api_info():
    """API 信息"""
    return {
        "name": "mini-claw API",
        "version": "1.0.0",
        "agents": [{"id": a.id, "name": a.name} for a in config.agents]
    }


@app.get("/test")
async def test_endpoint():
    """测试端点"""
    import sys
    sys.stderr.flush()

    # 直接测试 astream
    response = ""
    async for event in agent_manager.astream("你好", session_id="test-api", agent_id="main"):
        if event.get("type") == "token":
            response = event.get("content", "")
        elif event.get("type") == "done":
            break

    sys.stderr.flush()
    return {"response": response[:100]}


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "model": config.agent_defaults.model}


@app.get("/agents")
async def list_agents():
    """列出所有 Agent"""
    return {
        "agents": [{"id": a.id, "name": a.name, "description": a.description} for a in config.agents]
    }


@app.get("/agents/{agent_id}/sessions")
async def list_sessions(agent_id: str):
    """列出 Agent 的所有会话"""
    sessions = agent_manager.session_manager.list_sessions(agent_id)
    return {"agent_id": agent_id, "sessions": sessions}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """聊天接口（非流式）"""
    import sys
    sys.stderr.flush()

    response_text = ""
    event_count = 0

    async for event in agent_manager.astream(
        request.message,
        session_id=request.session_id,
        agent_id=request.agent_id,
    ):
        event_count += 1
        event_type = event.get("type", "")

        if event_type == "token":
            response_text = event.get("content", "")
        elif event_type == "done":
            break
        elif event_type == "error":
            response_text = event.get("content", "错误: " + response_text)
            break

    sys.stderr.flush()

    return ChatResponse(
        response=response_text,
        session_id=request.session_id,
        agent_id=request.agent_id
    )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """聊天接口（流式）"""
    async def generate() -> AsyncIterator[str]:
        async for event in agent_manager.astream(
            request.message,
            session_id=request.session_id,
            agent_id=request.agent_id,
        ):
            import json
            chunk = ChatStreamChunk(
                type=event.get("type", ""),
                content=event.get("content", "")
            )
            yield f"data: {chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str, agent_id: str = "main"):
    """删除会话"""
    await agent_manager.session_manager.delete_session(session_id, agent_id)
    return {"message": f"会话 {session_id} 已删除"}


@app.post("/sessions/{session_id}/reset")
async def reset_session(session_id: str, agent_id: str = "main"):
    """重置会话"""
    await agent_manager.session_manager.reset_session(session_id, agent_id)
    return {"message": f"会话 {session_id} 已重置"}


if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8080,
        reload=True
    )
