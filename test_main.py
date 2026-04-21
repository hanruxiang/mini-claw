#!/usr/bin/env python3
"""简化版测试程序"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import Config
from src.agent_manager import AgentManager


async def run_console():
    config = Config.load()
    agent_manager = AgentManager(config)

    print('mini-claw 控制台')
    print('输入 /exit 退出\n')

    while True:
        try:
            user_input = input('> ').strip()

            if not user_input:
                continue

            if user_input in ['/exit', '/quit']:
                print('再见！')
                break

            print('思考中...', flush=True)

            response = ''
            async for event in agent_manager.astream(user_input, session_id='test-main', agent_id='main'):
                if event.get('type') == 'token':
                    response = event.get('content', '')
                elif event.get('type') == 'done':
                    break

            print(f'\n{response}\n')

        except KeyboardInterrupt:
            print('\n使用 /exit 退出')
        except EOFError:
            break


if __name__ == '__main__':
    asyncio.run(run_console())
