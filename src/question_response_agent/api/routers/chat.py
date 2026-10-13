"""
对话路由：POST/chat

asyncio.wait_for：LLM是外部依赖，必须设置超时时间，不能让请求挂死
"""
import asyncio

from fastapi import APIRouter,Depends,HTTPException,status
from question_response_agent.schemas.chat import ChatResponse,ChatRequest
from sqlalchemy.ext.asyncio import AsyncSession
from question_response_agent.models.user import User
from question_response_agent.core.deps import get_current_user
from question_response_agent.db.session import get_db
from question_response_agent.services import chat_service
from question_response_agent.core.config import  settings
from question_response_agent.services.chat_service import (
ConversationNotFoundError,
LLMInvocationError
)

from fastapi.responses import StreamingResponse
from question_response_agent.core.rate_limit import rate_limit

router = APIRouter(prefix="/chat",tags=["对话"])

@router.post("",response_model=ChatResponse)
async def chat(
        req:ChatRequest,
        db:AsyncSession = Depends(get_db),
        current_user:User = Depends(get_current_user),
        _:None = Depends(rate_limit),
)->ChatResponse:
    """
    定义单轮会话接口，注意此接口需登录才能够访问，Depends(get_current_user)

    :param req: 请求信息
    :param db:  数据库连接
    :param current_user:获取登录后的用户
    :return:模型输出响应ChatResponse
    """
    try:
        return await asyncio.wait_for(
            chat_service.handle_chat(db,current_user,req),
            timeout=settings.llm_timeout_seconds
        )
    except ConversationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f'模型响应超时，请稍后重试'
        )
    except LLMInvocationError as e :
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"模型服务异常{e}"
        )

@router.post("/stream")
async def chat_stream(
        req:ChatRequest,
        db:AsyncSession = Depends(get_db),
        current_user:User = Depends(get_current_user),
        _:None = Depends(rate_limit)
):
    try:
        conv = await chat_service.prepare_stream(db,current_user,req)
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=404,detail=str(e))

    return StreamingResponse(
        chat_service.stream_reply(db,conv,req.message,req.scene,current_user.id),
        media_type="text/event-stream",
        headers={
            "cache-Control":"no-cache",
            "X-Accel-Buffering":"no"
        }
    )








