#!/usr/bin/env python3
"""mini-claw API - Flask 版本"""

import asyncio
import logging
import sys
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# 配置日志 - 只显示关键信息
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)

# 只显示自己模块的 INFO 日志
def setup_logger(name):
    log = logging.getLogger(name)
    log.setLevel(logging.INFO)
    return log

logger = setup_logger(__name__)

# 禁用所有第三方库的日志
for name in ['httpx', 'openai', 'langchain', 'langgraph', 'urllib3', 'asyncio']:
    logging.getLogger(name).setLevel(logging.WARNING)

from flask import Flask, request, jsonify
from flask_cors import CORS

# 导入
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import Config
from src.agent_manager import AgentManager

# 初始化
config = Config.load()
static_dir = Path(__file__).parent / "static"

# 创建 Flask app
app = Flask(__name__)
CORS(app)

# 创建线程池
executor = ThreadPoolExecutor(max_workers=4)

# 全局变量
agent_manager = None
agent_lock = threading.Lock()


def get_agent_manager():
    """获取或创建 AgentManager（线程安全）"""
    global agent_manager
    with agent_lock:
        if agent_manager is None:
            agent_manager = AgentManager(config)
        return agent_manager


def run_astream_in_thread(message, session_id, agent_id):
    """在新线程中运行 astream"""
    # 创建新的事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        agent = get_agent_manager()

        async def collect():
            response = ""
            async for event in agent.astream(message, session_id=session_id, agent_id=agent_id):
                if event.get("type") == "token":
                    response = event.get("content", "")
                elif event.get("type") == "done":
                    break
                elif event.get("type") == "error":
                    response = event.get("content", "错误")
                    break
            return response

        return loop.run_until_complete(collect())
    finally:
        loop.close()


@app.route("/")
def index():
    """主页"""
    try:
        return static_dir.joinpath("index.html").read_text(encoding="utf-8")
    except:
        return "<h1>mini-claw API</h1><p>POST /chat 进行对话</p>"


@app.route("/test")
def test():
    """测试端点"""
    return jsonify({"status": "ok", "message": "API 正常工作"})


@app.route("/health")
def health():
    """健康检查"""
    return jsonify({"status": "ok", "model": config.agent_defaults.model})


@app.route("/chat", methods=["POST"])
def chat():
    """聊天接口"""
    data = request.json
    message = data.get("message", "")
    session_id = data.get("session_id", "main")
    agent_id = data.get("agent_id", "main")

    # 记录请求
    logger = logging.getLogger(__name__)
    logger.info(f"收到请求: session_id={session_id}, message={message[:50]}{'...' if len(message) > 50 else ''}")

    # 在线程池中运行
    import time
    start = time.time()

    future = executor.submit(
        run_astream_in_thread,
        message,
        session_id,
        agent_id
    )

    try:
        response = future.result(timeout=120)  # 2分钟超时
        elapsed = time.time() - start
        logger.info(f"请求完成: session_id={session_id}, elapsed={elapsed:.1f}s, response={response[:100]}{'...' if len(response) > 100 else ''}")
        return jsonify({
            "response": response,
            "session_id": session_id,
            "agent_id": agent_id,
            "elapsed": f"{elapsed:.1f}s"
        })
    except TimeoutError:
        logger.error(f"请求超时: session_id={session_id}")
        return jsonify({"error": "请求超时"}), 504
    except Exception as e:
        logger.error(f"请求错误: session_id={session_id}, error={e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("🚀 mini-claw API 启动中...")
    print(f"📁 工作目录: {config.workspace_dir}")
    print(f"🧠 模型: {config.agent_defaults.model}")
    print(f"🌐 访问: http://localhost:5000")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 预热
    print("正在初始化 AI Agent...")
    get_agent_manager()
    print("✅ Agent 已就绪")

    # 启动服务
    app.run(
        host="127.0.0.1",
        port=5555,
        debug=False,
        use_reloader=False,
        threaded=True
    )
