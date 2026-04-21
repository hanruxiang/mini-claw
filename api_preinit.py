#!/usr/bin/env python3
"""mini-claw API - 预初始化版本"""

import logging
import sys
from pathlib import Path

# 完全禁用所有日志
logging.basicConfig(level=logging.CRITICAL)
logging.disable(logging.CRITICAL)

# 强制关闭所有日志记录器
logging.root.handlers = []
logging.root.setLevel(logging.CRITICAL)

for name in list(logging.Logger.manager.loggerDict.keys()):
    logger = logging.getLogger(name)
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.CRITICAL)

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# 导入
sys.path.insert(0, str(Path(__file__).parent / "src"))

# 在导入后立即禁用日志
import src.config
import src.agent_manager
src.config.logger = logging.getLogger(src.config.__name__).addHandler(logging.NullHandler())
src.agent_manager.logger = logging.getLogger(src.agent_manager.__name__).addHandler(logging.NullHandler())

from src.config import Config
from src.agent_manager import AgentManager

# 直接在这里初始化
print("正在初始化 Agent...")
config = Config.load()
agent_manager = AgentManager(config)
print(f"✅ Agent 已初始化，模型: {config.agent_defaults.model}")

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


@app.get("/")
async def root():
    try:
        return FileResponse(static_dir / "index.html")
    except:
        return {"message": "mini-claw API", "visit": "http://localhost:8084"}


@app.get("/health")
async def health():
    return {"status": "ok", "model": config.agent_defaults.model}


@app.post("/chat")
async def chat(request: ChatRequest):
    """聊天接口"""
    try:
        response_text = ""

        # 直接同步调用
        import asyncio
        loop = asyncio.get_event_loop()

        async def collect():
            text = ""
            async for event in agent_manager.astream(
                request.message,
                session_id=request.session_id,
                agent_id=request.agent_id,
            ):
                if event.get("type") == "token":
                    text = event.get("content", "")
                elif event.get("type") == "done":
                    break
                elif event.get("type") == "error":
                    text = event.get("content", "错误")
                    break
            return text

        response_text = await loop.create_task(collect())

        return ChatResponse(
            response=response_text,
            session_id=request.session_id,
            agent_id=request.agent_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8084,
        log_level="critical",
        access_log=False,
        timeout_keep_alive=300
    )
