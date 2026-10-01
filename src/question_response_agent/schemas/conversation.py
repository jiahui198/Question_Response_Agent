"""
会话管理接口的请求/响应数据结构
"""
from datetime import datetime

from pydantic import BaseModel,Field,ConfigDict

class MessageOut(BaseModel):
    """
    消息出参：会话详情里的每一条对话记录
    """
    id:int
    role:str = Field(description="user/assistant")
    content:str
    created_at:datetime

    model_config = ConfigDict(
        from_attributes=True
    )

class ConversationListItem(BaseModel):
    """
    会话列表中的单项：列表场景不返回消息正文，只给摘要和标题
    """
    id:int
    title:str
    summary:str | None = Field(default=None,description="长对话压缩后的摘要")
    created_at:datetime
    updated_at:datetime

    model_config = ConfigDict(from_attributes=True)

class ConversationListResponse(BaseModel):
    """
    会话列表分页响应：前端渲染分页需要total
    """
    items:list[ConversationListItem]
    total:int = Field(description="符合条件的会话总数")
    page:int
    page_size:int

class ConversationDetailResponse(BaseModel):
    """
    会话详情：会话元信息+完整消息历史
    """
    id:int
    title:str
    summary:str | None
    created_at:datetime
    updated_at:datetime
    messages:list[MessageOut]

class ConversationUpdateRequest(BaseModel):
    """
    改标题请求：标题做长度边界校验
    """
    title:str = Field(min_length=1,max_length=128,description="新的会话标题")






