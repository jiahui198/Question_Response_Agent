"""
LLM 客户端封装：用 LangChain 的 ChatTongyi 实例化通义千问模型。

设计点：
- 用 langchain_community.chat_models.tongyi.ChatTongyi（你熟悉的方式）
- 工厂函数 get_llm() 返回一个 ChatTongyi 实例，业务层直接 .ainvoke() 调用
- API Key / model 都从 settings 读，不硬编码
"""
from functools import lru_cache

from langchain_community.chat_models.tongyi import ChatTongyi

from question_response_agent.core.config import settings


@lru_cache
def get_llm() -> ChatTongyi:
    """
    返回一个 ChatTongyi 实例（单例，进程内复用）。

    :return: ChatTongyi 实例，可调用 .invoke / .ainvoke
    """
    return ChatTongyi(
        model=settings.llm_model,               # 从 .env 读：qwen-plus
        dashscope_api_key=settings.dashscope_api_key,
        temperature=0.7,                         # 对话场景偏发散
    )
