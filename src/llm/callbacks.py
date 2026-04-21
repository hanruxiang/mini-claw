"""LLM 回调处理器 - 用于记录完整的请求体"""

import json
import logging
from typing import Any, Dict, List, Optional, Sequence, Union
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import LLMResult
from langchain_core.prompt_values import ChatPromptValue

logger = logging.getLogger(__name__)


class LLMRequestLogger(BaseCallbackHandler):
    """记录 LLM 请求和响应的完整内容"""

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any,
    ) -> None:
        """当 LLM 开始处理时调用"""
        logger.info("=" * 60)
        logger.info("【LLM API 请求 JSON】")

        # 尝试解析输入以构建类似 OpenAI API 的请求格式
        for i, prompt in enumerate(prompts):
            try:
                # 尝试解析 prompt（可能是字符串或 ChatPromptValue）
                if isinstance(prompt, str):
                    # 简单字符串格式
                    logger.info(json.dumps({
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": 4096
                    }, ensure_ascii=False, indent=2))
                else:
                    # 尝试转换为字符串并显示
                    logger.info(f"Prompt {i+1} (类型: {type(prompt).__name__}):")
                    logger.info(str(prompt)[:2000])
            except Exception as e:
                logger.info(f"Prompt {i+1} (raw): {str(prompt)[:1000]}")

        logger.info("=" * 60)

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        **kwargs: Any,
    ) -> None:
        """当聊天模型开始处理时调用（这个方法会捕获到消息列表）"""
        logger.info("=" * 60)
        logger.info("【LLM API 请求 JSON (完整)】")

        # 获取模型名称
        model_name = kwargs.get("metadata", {}).get("model_name", "deepseek-chat")

        for i, msg_list in enumerate(messages):
            try:
                # 构建 OpenAI API 格式的请求
                api_messages = []
                for msg in msg_list:
                    if isinstance(msg, HumanMessage):
                        api_messages.append({"role": "user", "content": msg.content})
                    elif isinstance(msg, AIMessage):
                        api_messages.append({"role": "assistant", "content": msg.content})
                    elif isinstance(msg, SystemMessage):
                        api_messages.append({"role": "system", "content": msg.content})
                    else:
                        api_messages.append({"role": "user", "content": str(msg.content)})

                request_json = {
                    "model": model_name,
                    "messages": api_messages,
                    "temperature": 0.7,
                    "max_tokens": 4096
                }

                logger.info(json.dumps(request_json, ensure_ascii=False, indent=2))

            except Exception as e:
                logger.info(f"Messages {i+1} (error): {e}")
                for msg in msg_list:
                    logger.info(f"  - {type(msg).__name__}: {str(msg.content)[:200]}")

        logger.info("=" * 60)

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """当 LLM 完成处理时调用"""
        logger.info("=" * 60)
        logger.info("【LLM API 响应 JSON】")

        for i, generations in enumerate(response.generations):
            for j, gen in enumerate(generations):
                # 构建 OpenAI API 格式的响应
                response_json = {
                    "choices": [{
                        "index": j,
                        "message": {
                            "role": "assistant",
                            "content": gen.text
                        },
                        "finish_reason": "stop"
                    }]
                }

                # 添加 token 使用情况
                if hasattr(gen, 'generation_info') and gen.generation_info:
                    info = gen.generation_info
                    if 'token_usage' in info:
                        response_json["usage"] = info['token_usage']

                logger.info(json.dumps(response_json, ensure_ascii=False, indent=2))

        logger.info("=" * 60)

    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """当 LLM 出错时调用"""
        logger.error(f"LLM 错误: {error}")
