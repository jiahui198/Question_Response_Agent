"""
会话管理业务逻辑：列表分页/详情/改标题/删除

所有的查询都带user_id进行过滤
查别人的会话一律抛ConversationNotFoundError
"""
from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import AsyncSession

from question_response_agent.models.user import User
from question_response_agent.models.conversation import Conversation
from question_response_agent.models.messages import Message
from question_response_agent.services.chat_service import ConversationNotFoundError

async def list_conversations(
    db:AsyncSession,
    user:User,
    page:int,
    page_size:int
)->tuple[list[Conversation],int]:
    """
    分页查询当前用户的会话列表。按最近更新倒序，（将最近的对话历史放前面）

    :param db:  数据库连接session
    :param user: 用户表
    :param page: 页面序号
    :param page_size: 页面大小
    :return: 当前页的会话ORM对象列表，总数
    """
    #查询该用户下的所有会话消息数量：SELECT count(*) FROM conversations WHERE user_id = ?
    count_stmt = select(func.count()).select_from(Conversation).where(Conversation.user_id == user.id)
    total = (await db.execute(count_stmt)).scalar_one()

    #查询当前页,分页查询
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())       #降序排序
        .limit(page_size)
        .offset((page-1)*page_size)
    )

    rows = (await db.execute(stmt)).scalars().all()
    return list(rows),total

async def get_owned_conversation(
        db:AsyncSession,
        user:User,
        conversation_id:int
)->Conversation:
    """
    按会话id取单个会话并校验归属。

    :param db: 数据库连接session
    :param user: 用户表
    :param conversation_id: 会话id
    :return:conversation
    """
    stmt = select(Conversation).where(Conversation.id==conversation_id)
    conv = (await db.execute(stmt)).scalar_one_or_none()

    if conv is None or conv.user_id != user.id:
        raise ConversationNotFoundError("会话不存在")
    return conv

async def get_conversation_message(
        db:AsyncSession,
        conversation_id:int,
)->list[Message]:
    """
    获取单个会话的完整消息列表

    :param db:数据库连接session
    :param conversation_id: 会话id
    :return: 消息列表 list[Message]
    """
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(),Message.id.asc())
    )

    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)

async def update_title(
        db:AsyncSession,
        user:User,
        conversation_id:int,
        new_title:str
)->Conversation:
    """
    修改会话标题

    :param db:数据库连接session
    :param user: 用户表
    :param conversation_id: 会话id
    :param new_title: 新标题内容
    :return: 会话
    """
    conv = await get_owned_conversation(db=db,user=user,conversation_id=conversation_id)
    conv.title = new_title.strip()
    await db.commit()
    await db.refresh(conv)
    return conv

async def delete_conversation(
        db:AsyncSession,
        user:User,
        conversation_id:int
)->None:
    """
    按会话Id删除指定会话

    :param db: 数据库连接session
    :param user: 用户表
    :param conversation_id: 会话id
    :return: None
    """

    conv = await get_owned_conversation(db=db,user=user,conversation_id=conversation_id)
    await db.delete(conv)
    await db.commit()







