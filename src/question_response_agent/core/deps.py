"""
通用依赖：从请求里的JWT解析出当前登录用户

之后任何需要登录才能访问的接口，只要在参数里写：
    current_user:User = Depends(get_current_user)
FastAPI 就会自动：取 token → 校验 → 查库 → 把 User 对象注入进来。
"""

from fastapi import Depends,HTTPException,status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from question_response_agent.db.session import get_db
from question_response_agent.core.security import decode_access_token
from jose import JWTError
from sqlalchemy import select

from question_response_agent.models.user import User

#tokenurl:即将去此url下读取token，从请求头中提取token
oauth2_schema = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(
        token:str = Depends(oauth2_schema),
        db:AsyncSession = Depends(get_db)
)->User:
    """
    校验token并返回当前用户，任何一步失败都返回401
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="token无效或过期",
        headers={"WWW-Authenticate":"Bearer"}
    )

    #1.解析token,拿到user_id
    try:
        user_id = decode_access_token(token=token)
    except JWTError:
        raise credentials_exception


    #2.查库确认用户真实存在（token合法但用户可能已被删除）
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="账号已被禁用")

    return user







