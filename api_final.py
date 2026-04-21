#!/usr/bin/env python3
"""mini-claw API - 工作版本"""

import logging
import sys
from pathlib import Path
from typing import AsyncIterator

# 设置 NullHandler 防止日志阻塞
logging.root.addHandler(logging.NullHandler())
for name in ['httpx', 'httpcore', 'openai', 'langchain', 'uvicorn', 'fastapi', 'src']:
    logging.getLogger(name).addHandler(logging.NullHandler())
    logging.getLogger(name).propagate = False

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
agent_manager = None
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
        return {"message": "mini-claw API", "visit": "http://localhost:8082"}


@app.get("/health")
async def health():
    return {"status": "ok", "model": config.agent_defaults.model}


@app.on_event("startup")
async def startup():
    global agent_manager
    agent_manager = AgentManager(config)


@app.post("/chat")
async def chat(request: ChatRequest):
    if agent_manager is None:
        raise HTTPException(status_code=503, detail="服务未就绪")

    response_text = ""
    try:
        async for event in agent_manager.astream(
            request.message,
            session_id=request.session_id,
            agent_id=request.agent_id,
        ):
            if event.get("type") == "token":
                response_text = event.get("content", "")
            elif event.get("type") == "done":
                break
            elif event.get("type") == "error":
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
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8082,
        log_level="critical",
        access_log=False
    )
