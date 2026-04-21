#!/usr/bin/env python3
"""mini-claw 控制台入口"""

import asyncio
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import Config
from src.agent_manager import AgentManager


async def run_console() -> None:
    """运行控制台 REPL"""

    # 加载配置
    config = Config.load()

    # 打印欢迎信息
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ███╗   ██╗███████╗██╗  ██╗███████╗██████╗                 ║
║   ████╗  ██║██╔════╝╚██╗██╔╝██╔════╝██╔══██╗                ║
║   ██╔██╗ ██║█████╗   ╚███╔╝ █████╗  ██████╔╝                ║
║   ██║╚██╗██║██╔══╝   ██╔██╗ ██╔══╝  ██╔══██╗                ║
║   ██║ ╚████║███████╗██╔╝ ██╗███████╗██║  ██║                ║
║   ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝                ║
║                                                              ║
║              基于 LangChain/LangGraph 的 AI 助手              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")
    print(f"工作目录: {config.workspace_dir}")
    print(f"当前 Agent: {config.agents[0].name}")
    print("输入 /exit 退出\n")

    # 创建 Agent 管理器
    agent_manager = AgentManager(config)

    # 主循环
    while True:
        try:
            user_input = input("> ").strip()

            if not user_input:
                continue

            if user_input == "/exit":
                print("再见！")
                return

            print("思考中...", flush=True)
            sys.stderr.flush()

            response = ""
            async for event in agent_manager.astream(user_input, session_id="main", agent_id="main"):
                if event.get("type") == "token":
                    response = event.get("content", "")
                elif event.get("type") == "done":
                    break

            if response:
                print(f"\n{response}\n")

        except KeyboardInterrupt:
            print("\n使用 /exit 退出")
        except EOFError:
            break


if __name__ == "__main__":
    asyncio.run(run_console())
