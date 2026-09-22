"""
对话接口的请求/响应数据结构
边界处理：
    输出长度直接由pydantic限制
    空白字符由field_validator自定义字段验证器进行验证
"""

from datetime import datetime
from pydantic import BaseModel,Field,field_validator

class ChatRequest(BaseModel):
    message:str = Field(
        min_length=1,
        max_length=2000,
        description="用户提出的问题文本"
    )
    conversation_id:int | None = Field(
        default=None,
        description="会话窗口的id"
    )
    scene:str = Field(
        default="chat",
        max_length=32,
        description="根据提示词模版设定的会话场景chat/qa"
    )


    """
    定义字段验证器，在pydantic内部验证逻辑执行完毕之后运行，默认模式为after
    """
    @field_validator("message")
    @classmethod
    def message_not_blank(cls,v:str)->str:
        """
        去掉message字段值中出现的首位空白
        :param v: 字段值
        :return: 不带空白字符的message
        """
        v = v.strip()
        if not v:
            raise ValueError("消息内容不能全是空白字符")
        return v

class ChatResponse(BaseModel):
    """
    定义模型响应后，返回的结构化数据模型
    """
    conversation_id:int = Field(description="本次会话所属的会话ID")
    message_id:int = Field(description="指的是ai回复后，消息存在messages表中的id")
    reply:str = Field(description="ai回复的内容")
    created_at:datetime = Field(description="ai生成消息的时间")













