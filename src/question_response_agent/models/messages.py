from datetime import datetime

from sqlalchemy import String,DateTime,Integer,ForeignKey,Text
from sqlalchemy.orm import Mapped,mapped_column,relationship
from question_response_agent.db.base import Base

class Message(Base):
    """
    定义消息表：一个会话里的每一轮对话
    """
    __tablename__ ="messages"
    id:Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True)

    conversation_id:Mapped[int] = mapped_column(Integer,ForeignKey("conversations.id",ondelete="CASCADE"),nullable=False,index=True)
    role:Mapped[str] = mapped_column(String(16),nullable=False)

    # 消息内容（用户的问题 / AI 的回答），可能很长，用 Text
    content:Mapped[str] = mapped_column(Text,nullable=False)

    token_count:Mapped[int|None] = mapped_column(Integer,nullable=True)

    created_at:Mapped[datetime] = mapped_column(DateTime,default=datetime.utcnow,nullable=False)

    #对话与消息表的双向导航
    conversation:Mapped["Conversation"] = relationship(back_populates="messages")
    