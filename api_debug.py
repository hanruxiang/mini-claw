#!/usr/bin/env python3
"""mini-claw API - 逐步添加功能"""

import logging
import sys
from pathlib import Path

# 完全禁用日志
logging.basicConfig(level=logging.CRITICAL)
logging.disable(logging.CRITICAL)

# 禁用所有第三方库的日志
for name in ['httpx', 'httpcore', 'openai', 'langchain', 'uvicorn', 'fastapi']:
    logging.getLogger(name).setLevel(logging.CRITICAL)
    logging.getLogger(name).propagate = False

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Step 1: 导入 src 模块
sys.path.insert(0, str(Path(__file__).parent / "src"))
print("✅ 路径已添加")

# Step 2: 导入配置
try:
    from src.config import Config
    print("✅ Config 导入成功")
    config = Config.load()
    print(f"✅ 配置已加载，模型: {config.agent_defaults.model}")
except Exception as e:
    print(f"❌ Config 导入失败: {e}")
    config = None

app = FastAPI()

# 静态文件
static_dir = Path(__file__).parent / "static"
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
        return {"message": "mini-claw API"}


@app.get("/health")
async def health():
    return {"status": "ok", "model": config.agent_defaults.model if config else "none"}


# 全局 agent_manager
agent_manager = None


@app.on_event("startup")
async def startup():
    global agent_manager
    print("🚀 启动中...")

    if config is None:
        print("❌ 配置未加载")
        return

    try:
        from src.agent_manager import AgentManager
        print("✅ AgentManager 导入成功")

        agent_manager = AgentManager(config)
        print("✅ AgentManager 初始化成功")
    except Exception as e:
        print(f"❌ AgentManager 初始化失败: {e}")
        import traceback
        traceback.print_exc()


@app.post("/chat")
async def chat(request: ChatRequest):
    """聊天接口"""
    global agent_manager

    if agent_manager is None:
        raise HTTPException(status_code=503, detail="服务未就绪")

    # 调用 astream
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
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8082, log_level="info")
