"""
鉴权路由：注册接口主要实现注册、登录、获取当前用户信息的功能
"""

from fastapi import APIRouter,HTTPException,status,Depends
from fastapi.security import OAuth2PasswordRequestForm
from question_response_agent.schemas.auth import UserOut,UserCreate,TokenResponse
from sqlalchemy.ext.asyncio import AsyncSession

from question_response_agent.services import auth_service
from question_response_agent.services.auth_service import (
UserAlreadyExistsError,     #错误类型：用户已存在
InvalidCredentialsError     #错误类型：账号密码错误
)
from question_response_agent.db.session import get_db
from question_response_agent.core.deps import get_current_user
from question_response_agent.models.user import User



router = APIRouter(prefix="/auth",tags=["鉴权"])

@router.post(
    path="/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED
)
async def register(user_in:UserCreate,db:AsyncSession = Depends(get_db)):
    """
    注册：接收用户传给后端的数据，返回创建好的用户信息

    :param user_in: 用户传过来的结构化数据
    :param db:数据库session
    :return:创建好的用户信息
    """
    try:
        return await auth_service.register(user_in=user_in,db=db)
    except UserAlreadyExistsError as e :
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=str(e))

@router.post("/login",response_model=TokenResponse)
async def login(
        #接收登录请求中的账号密码
        form_data:OAuth2PasswordRequestForm =Depends(OAuth2PasswordRequestForm),
        db:AsyncSession = Depends(get_db)
):
    """
    定义登录模块，接收表单数据，返回JWT
    """
    #1.登录校验，验证用户提供的密码
    try:
        user = await auth_service.authenticate(
            email=form_data.username,
            password=form_data.password,
            db=db
        )
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate":"Bearer"}
        )

    #2.回传token(JWT)
    token = auth_service.issue_token(user=user)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
async def read_me(current_user: User = Depends(get_current_user)):
    """测试登录态的接口：必须带有效 token 才能访问，返回当前用户信息。"""
    return current_user





