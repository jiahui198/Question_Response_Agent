from datetime import datetime

from sqlalchemy import String,DateTime,Integer,ForeignKey,Text
from sqlalchemy.orm import Mapped,mapped_column,relationship
from question_response_agent.db.base import Base

class Conversation(Base):
    """
    会话表：一个用户可以创建多个会话
    """
    __tablename__ = "conversations"
    #外键关联，指向users表的id字段，级联删除，当对应的用户被删除时，该用户的所有会话也会被自动删除
    id:Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True)
    user_id:Mapped[str] = mapped_column(Integer,ForeignKey("users.id",ondelete="CASCADE"),nullable=False,index=True)
    title:Mapped[str] = mapped_column(String(128),default="新会话",nullable=False)

    summary:Mapped[str|None] = mapped_column(Text,nullable=True)

    created_at:Mapped[datetime] = mapped_column(DateTime,default=datetime.utcnow,nullable=False)
    updated_at:Mapped[datetime] = mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow,nullable=False)

    """
    cascade级联操作，控制父对象增删改时对子对象做什么操作
        cascade="save-update,merge,delete,delete-orphan"
        save-update:父对象加入session，关联对象自动加入session
        delete:父对象删除，关联对象一起删
        delete-orphan:孤儿删除，当子对象脱离父对象，子对象自动删除
    """

    #对话与消息表之间建立一对多关系
    messages:Mapped[list["messages"]] = relationship(
        back_populates="conversation",cascade="all,delete-orphan"
    )
