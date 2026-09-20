from datetime import datetime

from sqlalchemy import String,DateTime,Boolean,Integer
from sqlalchemy.orm import Mapped,mapped_column
from question_response_agent.db.base import Base

class User(Base):
    """
    定义用户表结构
    """
    __tablename__ ="users"

    #主键
    id:Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True)

    #业务字段
    username:Mapped[str] = mapped_column(String(64),unique=True,index=True,nullable=False)
    email:Mapped[str] = mapped_column(String(128),unique=True,index=True,nullable=False)
    hashed_password:Mapped[str] = mapped_column(String(256),nullable=False)

    #状态
    is_active:Mapped[bool] = mapped_column(Boolean,default=True,nullable=False)

    #时间戳
    created_at:Mapped[datetime] = mapped_column(DateTime,default = datetime.utcnow,nullable=False)
    updated_at:Mapped[datetime] = mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow,nullable=False)
    