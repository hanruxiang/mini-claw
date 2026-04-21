#!/usr/bin/env python3
"""mini-claw 初始化脚本

创建工作目录和默认配置文件
"""

import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import Config, get_config
from src.prompts.system import create_default_agent_files


def init_workspace() -> None:
    """初始化工作目录"""

    # 加载配置
    try:
        config = Config.load()
    except FileNotFoundError:
        print("❌ 配置文件 config.yaml 未找到")
        print("请先创建配置文件")
        return

    # 创建工作目录
    workspace_dir = config.workspace_dir
    workspace_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ 工作目录: {workspace_dir}")

    # 为每个 Agent 创建默认文件
    for agent in config.agents:
        agent_dir = config.get_agent_dir(agent.id)
        print(f"\n📝 初始化 Agent: {agent.name} ({agent.id})")

        create_default_agent_files(agent_dir)

        print(f"   - SOUL.md")
        print(f"   - IDENTITY.md")
        print(f"   - HEARTBEAT.md")
        print(f"   - MEMORY.md")
        print(f"   - memory/")
        print(f"   - skills/")
        print(f"   - sessions/")

    print("\n✨ 初始化完成！")
    print(f"\n下一步:")
    print(f"  1. 配置 .env 文件，添加 API keys")
    print(f"  2. 运行: python main.py")


if __name__ == "__main__":
    init_workspace()
