from datetime import datetime

from sqlalchemy import String,DateTime,Integer,ForeignKey,Text,Float
from sqlalchemy.orm import Mapped,mapped_column
from question_response_agent.db.base import Base

class UserMemory(Base):
    """
    用户长期记忆表
    """
    __tablename__ = "user_memories"
    id:Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True)

    user_id:Mapped[int] = mapped_column(Integer,ForeignKey("users.id",ondelete="CASCADE"),nullable=False,index=True)

    #记忆分类：preference（偏好）/fact（事实）/goal（目标）
    memory_type:Mapped[str] = mapped_column(String(32),default="fact",nullable=False)

    #记忆内容
    content:Mapped[str] = mapped_column(Text,nullable=False)

    #重要性分数0-1，后期检索时按分数排序
    importance:Mapped[float] = mapped_column(Float,default=0.5,nullable=False)

    created_at:Mapped[datetime] = mapped_column(DateTime,default=datetime.utcnow,nullable=False)
    updated_at:Mapped[datetime] = mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow,nullable=False)


