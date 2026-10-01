"""
会话路由，用来管理会话：
    获取单个用户所有会话
    获取单个会话下所有消息
    修改会话标题
    删除会话
"""
from fastapi import APIRouter,HTTPException,Query,status,Depends
from question_response_agent.schemas.conversation import (
ConversationListResponse,
ConversationListItem,
ConversationDetailResponse,
MessageOut,
ConversationUpdateRequest
)
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from question_response_agent.db.session import get_db
from question_response_agent.models.user import User
from question_response_agent.core.deps import get_current_user
from question_response_agent.services import conversation_service
from question_response_agent.services.chat_service import ConversationNotFoundError



router = APIRouter(prefix="/conversations",tags=["会话管理"])

@router.get("",response_model=ConversationListResponse)
async def list_conversations(
        page:Annotated[int,Query(ge=1,description="页码，从1开始")]=1,
        page_size:Annotated[int,Query(ge=1,le=100,description="每页条数1-100")]=20,
        db:AsyncSession = Depends(get_db),
        current_user:User = Depends(get_current_user)
)->ConversationListResponse:
    """
    分页列出当前用户的会话，按照最近更新的时间进行排序

    :param page: 页码
    :param page_size:页面大小，分页大小
    :param db: 数据库连接session
    :param current_user: 获取登录后的用户
    :return:用户会话列表
    """
    rows,total = await conversation_service.list_conversations(
        db=db,
        user=current_user,
        page=page,
        page_size=page_size
    )

    return ConversationListResponse(
        items=[ConversationListItem.model_validate(row) for row in rows],
        total = total,
        page=page,
        page_size=page_size
    )

@router.get("/{conversation_id}",response_model=ConversationDetailResponse)
async def get_conversation(
        conversation_id:int,
        db:AsyncSession = Depends(get_db),
        current_user:User = Depends(get_current_user)
)->ConversationDetailResponse:
    """
    获取用户的某个会话的会话元信息和整个消息历史列表

    :param conversation_id: 会话id
    :param db: 数据库连接session
    :param current_user: 已登录用户
    :return:用户某个会话的元信息
    """
    try:
        conv = await conversation_service.get_owned_conversation(
            db=db,
            user=current_user,
            conversation_id=conversation_id
        )
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail=str(e))

    messages = await conversation_service.get_conversation_message(db,conversation_id)

    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        summary=conv.summary,
        created_at = conv.created_at,
        updated_at = conv.updated_at,
        messages = [MessageOut.model_validate(m) for m in messages]
    )


@router.put("/{conversation_id}",response_model=ConversationListItem)
async def update_conversation_title(
        conversation_id:int,
        req:ConversationUpdateRequest,
        db:AsyncSession = Depends(get_db),
        current_user:User = Depends(get_current_user)
)->ConversationListItem:
    """
    修改会话标题。

    :param conversation_id:会话Id
    :param req:修改标题请求
    :param db:数据库连接session
    :param current_user:已登录用户
    :return:新修改后的会话标题
    """
    try:
        conv = await conversation_service.update_title(
            db=db,
            user=current_user,
            conversation_id=conversation_id,
            new_title=req.title
        )
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail=str(e))
    return ConversationListItem.model_validate(conv)

@router.delete("/{conversation_id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
        conversation_id:int,
        db:AsyncSession = Depends(get_db),
        current_user :User= Depends(get_current_user)
):
    """
    删除会话和全部消息。成功返回204无内容

    :param conversation_id: 会话Id
    :param db: 数据库连接session
    :param current_user: 已登录用户
    """
    try:
        await conversation_service.delete_conversation(
            db=db,
            conversation_id=conversation_id,
            user=current_user
        )
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail=str(e))















