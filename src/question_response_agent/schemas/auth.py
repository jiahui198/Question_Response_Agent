"""
本文件主要定义前后端传数据时严格的数据结构
"""
from datetime import datetime

from pydantic import BaseModel,Field,EmailStr,ConfigDict

#----注册请求----
class UserCreate(BaseModel):
    """
    定义用户传过来的格式化数据，并做数据校验
    """
    username:str = Field(min_length=3,max_length=64,description="用户名，3-64字符")
    email :EmailStr = Field(description="邮箱地址")
    password:str = Field(min_length=6,max_length=128,description="用户登录的密码")

#----注册相应----
class UserOut(BaseModel):
    """
    用户注册后，后端返回给前端的数据
    """
    id:int
    username:str = Field(min_length=3,max_length=64,description="用户名称，长度为3-64字符串")
    email:EmailStr
    is_active:bool
    created_at:datetime

    #允许pydantic从普通的python对象中读取属性（sqlalchemy），并自动转换为pydantic模型
    model_config = ConfigDict(
        from_attributes=True
    )

#----登录请求----
class LoginRequest(BaseModel):
    """
    用户登录时接收的数据
    """
    email:EmailStr
    password:str

#----登录相应----
class TokenResponse(BaseModel):
    """
    登录成功后，后端校验后返回JWT token
    """
    access_token:str
    token_type:str = "bearer"














