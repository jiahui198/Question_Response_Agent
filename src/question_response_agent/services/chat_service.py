"""
对话业务逻辑：组装LCEL链（动态提示词 |LLM）调用 --> 消息落库
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from question_response_agent.models.user import User
from question_response_agent.models.conversation import Conversation
from question_response_agent.models.messages import Message
from question_response_agent.schemas.chat import ChatRequest, ChatResponse
from question_response_agent.agents.prompts.system_prompts import (
get_prompt_template,
ROLE_STUDENT
)
from question_response_agent.agents.llm import get_llm


#----业务异常----
class LLMInvocationError(Exception):
    """
    定义大模型调用失败错误异常
    """
class ConversationNotFoundError(Exception):
    """
    会话不存在或不属于当前用户
    """

async def get_or_create_conversation(
        db:AsyncSession,
        user:User,
        conversation_id:int|None
)->Conversation:
    """
    拿到本次对话所属会话id：不传id就新建会话，传就判断归属

    :param db: 数据库连接
    :param user: 用户表数据
    :param conversation_id: 会话id
    """

    if conversation_id is None:
        conv = Conversation(user_id=user.id)
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return conv
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()

    if conv is None or conv.user_id != user.id:
        raise ConversationNotFoundError("会话不存在")
    return conv

async def save_message(
        db:AsyncSession,
        conversation_id:int,
        role:str,
        content:str
)->Message:
    """
    此函数实现保存用户一个会话下面多条的消息内容,把消息写进message表中

    :param db:  数据库连接
    :param conversation_id: 消息对应的会话id
    :param role: 角色身份,rols | assistant
    :param content: 消息内容
    """
    msg = Message(conversation_id=conversation_id,role=role,content=content)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    return msg

async def handle_chat(db:AsyncSession,user:User,req:ChatRequest)->ChatResponse:
    """
    主流程函数：会话就绪->存用户消息->LCEL链生成回复->存AI消息

    :param db: 数据库连接
    :param user: 角色身份
    :param req: 用户的输入问题请求
    :return: 响应输出
    """
    conv = await get_or_create_conversation(db,user,req.conversation_id)
    if conv.title =="新会话":
        conv.title = req.message[:20]
        await db.commit()


    #messages表中存储用户消息
    await save_message(db,conv.id,role="user",content=req.message)

    #LCEL链：动态提示词|LLM
    chain = get_prompt_template(ROLE_STUDENT,req.scene) | get_llm()

    try:
        ai_msg = await chain.ainvoke(
            {"user_input":req.message,"role":ROLE_STUDENT}
        )
    except Exception as e :
        raise LLMInvocationError(f"llm调用失败{e}") from e

    #存ai回复
    assistant_msg = await save_message(db,conv.id,role="assistant",content=ai_msg.content)

    return ChatResponse(
        conversation_id=conv.id,
        message_id = assistant_msg.id,
        reply = ai_msg.content,
        created_at = assistant_msg.created_at
    )

