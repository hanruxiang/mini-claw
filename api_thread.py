#!/usr/bin/env python3
"""mini-claw API - 使用线程池避免阻塞"""

import asyncio
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# 禁用日志
logging.basicConfig(level=logging.CRITICAL)
logging.disable(logging.CRITICAL)
for name in logging.root.manager.loggerDict:
    logging.getLogger(name).setLevel(logging.CRITICAL)

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# 导入
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import Config
from src.agent_manager import AgentManager

# 配置
config = Config.load()
executor = ThreadPoolExecutor(max_workers=4)
static_dir = Path(__file__).parent / "static"

# FastAPI
app = FastAPI(title="mini-claw API")

try:
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
except:
    pass


class ChatRequest(BaseModel):
    message: str
    session_id: str = "main"
    agent_id: str = "main"


class ChatResponse(BaseModel):
    response: str
    session_id: str
    agent_id: str


# 在线程中运行的异步函数
def run_astream_sync(manager, message, session_id, agent_id):
    """在新的事件循环中运行 astream"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        response = loop.run_until_complete(
            _astream_async(manager, message, session_id, agent_id)
        )
        return response
    finally:
        loop.close()


async def _astream_async(manager, message, session_id, agent_id):
    """异步收集 astream 结果"""
    response_text = ""
    async for event in manager.astream(message, session_id=session_id, agent_id=agent_id):
        if event.get("type") == "token":
            response_text = event.get("content", "")
        elif event.get("type") == "done":
            break
        elif event.get("type") == "error":
            response_text = event.get("content", "发生错误")
            break
    return response_text


@app.get("/")
async def root():
    try:
        return FileResponse(static_dir / "index.html")
    except:
        return {"message": "mini-claw API", "visit": "http://localhost:8083"}


@app.get("/health")
async def health():
    return {"status": "ok", "model": config.agent_defaults.model}


# 全局 agent_manager
agent_manager = None


@app.on_event("startup")
async def startup():
    global agent_manager
    agent_manager = AgentManager(config)


@app.post("/chat")
async def chat(request: ChatRequest):
    if agent_manager is None:
        raise HTTPException(status_code=503, detail="服务未就绪")

    # 在线程池中运行
    loop = asyncio.get_event_loop()
    response_text = await loop.run_in_executor(
        executor,
        run_astream_sync,
        agent_manager,
        request.message,
        request.session_id,
        request.agent_id
    )

    return ChatResponse(
        response=response_text,
        session_id=request.session_id,
        agent_id=request.agent_id
    )


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8083,
        log_level="critical",
        access_log=False
    )
