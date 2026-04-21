#!/usr/bin/env python3
"""mini-claw 命令行界面 - 工作版本"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import Config
from src.agent_manager import AgentManager


async def run_cli():
    """运行命令行界面"""

    # 加载配置
    config = Config.load()
    print(f"🤖 mini-claw AI 助手")
    print(f"📁 工作目录: {config.workspace_dir}")
    print(f"🧠 模型: {config.agent_defaults.model}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 创建 Agent Manager
    agent_manager = AgentManager(config)

    session_id = "cli-main"
    agent_id = "main"

    print("输入消息开始对话，输入 /exit 退出\n")

    while True:
        try:
            # 获取用户输入
            user_input = input("> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['/exit', '/quit', 'quit']:
                print("👋 再见！")
                break

            # 显示思考状态
            print("🤔 ", end="", flush=True)

            # 调用 astream
            response = ""
            start_time = __import__('time').time()

            async for event in agent_manager.astream(
                user_input,
                session_id=session_id,
                agent_id=agent_id,
            ):
                if event.get("type") == "token":
                    if not response:  # 第一次收到 token
                        print("\r" + " " * 20 + "\r", end="")  # 清除思考状态
                    response = event.get("content", "")
                elif event.get("type") == "error":
                    response = event.get("content", "发生错误")
                    break

            elapsed = __import__('time').time() - start_time

            # 显示响应
            if response:
                print(f"\n🤖 助手 (耗时 {elapsed:.1f}秒):")
                print(f"{response}\n")
            else:
                print("\n❌ 没有收到响应\n")

        except KeyboardInterrupt:
            print("\n\n使用 /exit 退出")
        except EOFError:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}\n")


if __name__ == "__main__":
    try:
        asyncio.run(run_cli())
    except KeyboardInterrupt:
        print("\n\n👋 程序已退出")
