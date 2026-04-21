"""完整的回调 - 清晰显示 Agent 思考流程"""

import logging
import json
from typing import Any, Dict, List, Union
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)


def format_msg_content(msg: BaseMessage, max_len: int = 80) -> str:
    """格式化消息内容"""
    content = msg.content if hasattr(msg, 'content') else str(msg)
    if len(content) > max_len:
        return content[:max_len] + "..."
    return content


class SimpleCallback(BaseCallbackHandler):
    """显示 Agent 的完整思考流程"""

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        **kwargs
    ) -> None:
        """显示 LLM 要处理什么"""
        msg_list = messages[0] if messages else []

        user_input = None
        tool_context = []

        for msg in msg_list:
            if isinstance(msg, HumanMessage) and not user_input:
                user_input = format_msg_content(msg, 200)
            elif isinstance(msg, AIMessage):
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_name = tc.get('name', 'unknown')
                        tool_args = tc.get('args', {})
                        # 简化参数显示
                        args_str = json.dumps(tool_args, ensure_ascii=False)
                        if len(args_str) > 100:
                            args_str = args_str[:100] + "..."
                        tool_context.append(f"{tool_name}({args_str})")

        if tool_context:
            logger.info(f"🤖 思考: 基于工具返回 [{', '.join(tool_context)}] 继续分析")
        elif user_input:
            logger.info(f"👤 用户输入: {user_input}")

        logger.info("🔵 调用 LLM...")

    def on_chat_model_end(self, response: Any, **kwargs) -> None:
        """聊天模型结束 - 这里能捕获到更多信息"""
        logger.info("🟢 LLM 响应完成")

        # 尝试从响应中提取工具调用或文本
        if hasattr(response, 'generations'):
            for generations in response.generations:
                for gen in generations:
                    if hasattr(gen, 'message') and hasattr(gen.message, 'tool_calls'):
                        if gen.message.tool_calls:
                            for tool in gen.message.tool_calls:
                                name = tool.get('name', 'unknown')
                                args = tool.get('args', {})
                                args_str = json.dumps(args, ensure_ascii=False)
                                if len(args_str) > 100:
                                    args_str = args_str[:100] + "..."
                                logger.info(f"📋 决策: 调用工具 {name}({args_str})")
                            return
                    elif hasattr(gen, 'text'):
                        text = gen.text
                        if text:
                            logger.info(f"💬 生成回答: {text[:100]}{'...' if len(text) > 100 else ''}")

        logger.info("")

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """LLM 结束的备用处理"""
        pass  # 由 on_chat_model_end 处理

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs
    ) -> None:
        tool_name = serialized.get("name", "unknown")
        if len(input_str) > 150:
            input_str = input_str[:150] + "..."
        logger.info(f"🔧 执行工具: {tool_name}")

        # 显示具体命令（如果是 exec）
        try:
            args = json.loads(input_str) if isinstance(input_str, str) else input_str
            if isinstance(args, dict) and 'command' in args:
                logger.info(f"   命令: {args['command']}")
        except:
            pass

    def on_tool_end(self, output: Union[str, BaseMessage], **kwargs) -> None:
        if isinstance(output, str):
            content = output
        elif hasattr(output, "content"):
            content = str(output.content)
        else:
            content = str(output)

        content = content.strip()

        # 处理多行输出
        if '\n' in content:
            lines = content.split('\n')
            if len(lines) > 5:
                logger.info(f"✅ 返回: {lines[0][:100]}")
                logger.info(f"   ... (共 {len(lines)} 行输出)")
            else:
                logger.info(f"✅ 返回:\n   " + "\n   ".join(lines[:5]))
        else:
            if len(content) > 150:
                content = content[:150] + "..."
            logger.info(f"✅ 返回: {content}")

        logger.info("")
