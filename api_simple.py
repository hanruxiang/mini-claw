#!/usr/bin/env python3
"""mini-claw API 服务 - 简化版"""

import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

# 禁用日志
logging.disable(logging.CRITICAL)

from src.config import Config
from src.agent_manager import AgentManager

# 全局配置
config = Config.load()
agent_manager = None

# 静态文件目录
static_dir = Path(__file__).parent / "static"

# 请求/响应模型
class ChatRequest(BaseModel):
    message: str
    session_id: str = "main"
    agent_id: str = "main"

class ChatResponse(BaseModel):
    response: str
    session_id: str
    agent_id: str

app = FastAPI(title="mini-claw API")

# 挂载静态文件
try:
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
except:
    pass


@app.on_event("startup")
async def startup():
    global agent_manager
    agent_manager = AgentManager(config)
    print("✅ mini-claw API 服务已启动")
    print(f"📁 工作目录: {config.workspace_dir}")
    print(f"🤖 模型: {config.agent_defaults.model}")


@app.get("/")
async def root():
    """主页"""
    try:
        return FileResponse(static_dir / "index.html")
    except:
        return {"message": "mini-claw API", "visit": "http://localhost:8080"}


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "model": config.agent_defaults.model}


@app.get("/test-simple")
async def test_simple():
    """简单测试"""
    return {"message": "test", "data": [1, 2, 3]}


@app.post("/chat")
async def chat(request: ChatRequest):
    """聊天接口"""
    global agent_manager

    if agent_manager is None:
        raise HTTPException(status_code=503, detail="服务未就绪")

    # 快速返回测试
    return ChatResponse(
        response="这是一个测试回复",
        session_id=request.session_id,
        agent_id=request.agent_id
    )

    response_text = ""

    try:
        async for event in agent_manager.astream(
            request.message,
            session_id=request.session_id,
            agent_id=request.agent_id,
        ):
            event_type = event.get("type", "")

            if event_type == "token":
                response_text = event.get("content", "")
            elif event_type == "done":
                break
            elif event_type == "error":
                response_text = event.get("content", "发生错误")
                break

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(
        response=response_text,
        session_id=request.session_id,
        agent_id=request.agent_id
    )


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="error")
