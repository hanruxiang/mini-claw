"""LLM 提供商模块"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """LLM 提供商抽象基类"""

    @abstractmethod
    def get_model(
        self,
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> ChatOpenAI:
        """获取模型实例"""


class OpenAIProvider(LLMProvider):
    """OpenAI 提供商"""

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.base_url = base_url

    def get_model(
        self,
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> ChatOpenAI:
        return ChatOpenAI(
            model=model_id,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )


class DeepSeekProvider(LLMProvider):
    """DeepSeek 提供商"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com/v1"):
        self.api_key = api_key
        self.base_url = base_url

    def get_model(
        self,
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> ChatOpenAI:
        return ChatOpenAI(
            model=model_id,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )


class OllamaProvider(LLMProvider):
    """Ollama 本地提供商"""

    def __init__(self, base_url: str = "http://localhost:11434/v1"):
        self.base_url = base_url
        self.api_key = "ollama"  # Ollama 不需要 API key，但需要占位

    def get_model(
        self,
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> ChatOpenAI:
        return ChatOpenAI(
            model=model_id,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )


class QwenProvider(LLMProvider):
    """通义千问提供商"""

    def __init__(self, api_key: str, base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"):
        self.api_key = api_key
        self.base_url = base_url

    def get_model(
        self,
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> ChatOpenAI:
        # 使用 OpenAI 兼容接口
        return ChatOpenAI(
            model=model_id,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )


class LLMProviderFactory:
    """LLM 提供商工厂"""

    _providers: dict[str, LLMProvider] = {}

    @classmethod
    def register(cls, name: str, provider: LLMProvider) -> None:
        """注册提供商"""
        cls._providers[name] = provider

    @classmethod
    def get(cls, name: str) -> LLMProvider | None:
        """获取提供商"""
        return cls._providers.get(name)

    @classmethod
    def create_from_config(cls, config: dict) -> None:
        """从配置创建提供商"""
        for provider_id, provider_config in config.items():
            api_key = provider_config.api_key
            base_url = provider_config.base_url

            if provider_id == "openai":
                cls.register("openai", OpenAIProvider(api_key or "", base_url))
            elif provider_id == "deepseek":
                cls.register("deepseek", DeepSeekProvider(api_key or "", base_url))
            elif provider_id == "ollama":
                cls.register("ollama", OllamaProvider(base_url))
            elif provider_id == "qwen":
                cls.register("qwen", QwenProvider(api_key or "", base_url))


def get_model(
    model_id: str,
    provider_name: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    **kwargs: Any,
) -> ChatOpenAI:
    """获取模型实例的便捷函数"""
    from ..config import get_config

    config = get_config()

    # 如果没有指定提供商，尝试自动检测
    if provider_name is None:
        provider_name = config.get_provider_for_model(model_id)

    if provider_name is None:
        raise ValueError(f"无法找到模型 {model_id} 对应的提供商")

    provider = LLMProviderFactory.get(provider_name)
    if provider is None:
        raise ValueError(f"提供商 {provider_name} 未注册")

    return provider.get_model(model_id, temperature, max_tokens, **kwargs)
