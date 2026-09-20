"""
鉴权业务逻辑，用户的登录和注册在此文件代码下进行验证
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from question_response_agent.core.security import (
create_access_token,
hash_password,
verify_password
)
from question_response_agent.models.user import User
from question_response_agent.schemas.auth import UserCreate

#----自定义业务异常----
class AuthError(Exception):
    """
    业务异常基类。路由层会捕获它转成HTTP错误
    """

class UserAlreadyExistsError(AuthError):
    """
    注册时，返回用户名或邮箱已被占用
    """

class InvalidCredentialsError(AuthError):
    """
    登录时：邮箱不存在或密码不对
    """

#----业务函数----
async def register(user_in:UserCreate,db:AsyncSession):
    """
    注册时，检查用户名邮箱唯一性 -->密码哈希 -->入库

    :param user_in: 用户注册时发送的pydantic结构化信息
    :param db: 数据库异步连接
    """
    #1.检查用户名唯一性
    stmt_username = select(User).where(User.username == user_in.username)
    result1 = await db.execute(stmt_username)

    if result1.scalar_one_or_none() is not None:
        raise UserAlreadyExistsError(f"用户名{user_in.username}已存在")

    #2.检查邮箱唯一性
    stmt_email = select(User).where(User.email ==user_in.email)
    result2 = await db.execute(stmt_email)
    if result2.scalar_one_or_none() is not None:
        raise UserAlreadyExistsError(f"邮箱账号{user_in.email}已存在")

    hashed = hash_password(user_in.password)
    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hashed
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def authenticate(email:str,password:str,db:AsyncSession)->User:
    """
    登录功能校验：按邮箱查用户 --> 校验密码 -->返回User
    :param email:
    :param password:
    :param db:
    :return: user
    """
    stmt = select(User).where(User.email ==email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password,user.hashed_password):
        raise InvalidCredentialsError("邮箱或密码错误")

    if not user.is_active:
        raise InvalidCredentialsError("账号已被禁用")

    return user

def issue_token(user:User)->str:
    """
    给登录后已认证的用户签发JWT
    :param user: models/User
    :return: JWT
    """
    return create_access_token(user.id)






