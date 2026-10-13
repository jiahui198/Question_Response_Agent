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
def _get_llm(model_name:str) -> ChatTongyi:
    """
    返回一个 ChatTongyi 实例（单例，进程内复用）。

    :return: ChatTongyi 实例，可调用 .invoke / .ainvoke
    """
    return ChatTongyi(
        model=model_name,
        dashscope_api_key=settings.dashscope_api_key,
        temperature=0.7,                         # 对话场景偏发散
        streaming=True,                          # 开启流式，供 astream() 逐 token 推送
    )


#新增路由模型代码，根据角色+场景动态选择模型
def get_llm(user_role:str | None = None,scene:str | None = None)->ChatTongyi:
    """
    按照场景+角色路由到对应的模型：选择合适的模型
    :param user_role:用户角色
    :param scene:场景
    :return:模型实例
    """
    if user_role is None or scene is None:
        return _get_llm(settings.llm_default_model)
    model = settings.llm_model_routes.get((user_role,scene),settings.llm_default_model)
    return _get_llm(model_name=model)





