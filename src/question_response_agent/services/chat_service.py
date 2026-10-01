"""
对话业务逻辑：组装LCEL链（动态提示词 |LLM）调用 --> 消息落库
"""
import json
from collections.abc import AsyncGenerator

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
from langchain_core.messages import HumanMessage,AIMessage
from sqlalchemy import func


MEMORY_WINDOW=6 #设置窗口大小：最近6条消息
SUMMARY_THRESHOLD = 12  #设置消息条数阈值


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


"""
本部分用于设计agent的会话压缩，将长上下文借助llm进行压缩
"""
async def summarize_history(
        messages:list[Message],
        existing_summary:str | None
)->str:
    """
    把消息内容列表压缩成摘要

    :param messages: 消息列表
    :param existing_summary:已有对话摘要
    :return:新摘要
    """
    content_parts = [f"{m.role}:{m.content}" for m in messages]
    if existing_summary:
        prompt_text = (
            f"已有对话摘要：\n{existing_summary}\n\n"
            f"新增对话摘要\n"+"\n".join(content_parts)+"\n\n"
            "请更新摘要，保留关键信息（用户姓名、偏好、事实、重要结论），控制在200字以内"
        )
    else:
        prompt_text = (
            "请把以下对话压缩成摘要，保留关键信息"
            "（用户姓名、偏好、事实、重要结论），控制在200字以内：\n\n"
            + "\n".join(content_parts)
        )
    llm = get_llm()
    resp = await llm.ainvoke(prompt_text)
    return resp.content

async def maybe_summary(
        db:AsyncSession,
        conv:Conversation,
        window:int = MEMORY_WINDOW
)->str | None:
    """
    检测是否触发摘要：
    消息总数超过阈值时，把更早的消息压缩成摘要写回;
    没到阈值就返回先有摘要（可能为None）。

    :param db:数据库连接session
    :param conv:会话
    :param window:窗口大小
    :return:摘要/None
    """
    count_stmt = select(func.count()).select_from(Message).where(Message.conversation_id==conv.id)
    total = (await db.execute(count_stmt)).scalar_one()
    if total <=window:
        return conv.summary

    #取窗口之外的更早的消息
    stmt = (
        select(Message)
        .where(Message.conversation_id == conv.id)
        #排序按照时间从最早到最近的时间排序，由小到大
        .order_by(Message.created_at.asc(),Message.id.asc())
        .limit(total-window)
    )
    old_msgs = list((await db.execute(stmt)).scalars().all())

    new_summary = await summarize_history(messages=old_msgs,existing_summary=conv.summary)
    conv.summary=new_summary
    await db.commit()
    return new_summary

"""
本部分用于设计agent的记忆功能，将对话的历史消息与摘要进行拼接
"""
async def build_messages_with_memory(
        db:AsyncSession,
        conversation_id:int,
        user_input:str,
        window:int = MEMORY_WINDOW
)->dict:
    """
    拉取最近window条历史消息.同时检测是否需要摘要机制

    :param db: 数据库连接session
    :param conversation_id:会话id
    :param user_input:用户输入
    :param window:窗口大小
    :return:{"history": [...], "user_input": ..., "role": ...}
    """
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        #按照时间降序排列，由最近的到最早的
        .order_by(Message.created_at.desc(),Message.id.desc())
        .limit(window)
        .offset(1)      #跳过最近一条的用户消息（已随消息模版发送）
    )
    rows = (await db.execute(stmt)).scalars().all()
    rows = list(reversed(rows))

    history=[]
    for m in rows:
        if m.role =="user":
            history.append(HumanMessage(content=m.content))
        elif m.role =="assistant":
            history.append(AIMessage(content=m.content))
    #检测是否需要摘要，把结果注入模板变量
    conv_stmt = select(Conversation).where(Conversation.id == conversation_id)
    conv =(await db.execute(conv_stmt)).scalar_one()
    summary = await maybe_summary(db,conv,window)
    summary_text = f"【历史摘要】{summary}" if summary else ""

    return {
        "history":history,
        "user_input":user_input,
        "role":ROLE_STUDENT,
        "summary":summary_text
    }

async def handle_chat(db:AsyncSession,user:User,req:ChatRequest)->ChatResponse:
    """
    主流程函数：会话就绪->存用户消息->获取或者创建summary->LCEL链生成回复->存AI消息

    :param db: 数据库连接
    :param user: 用户信息
    :param req: 用户的输入问题请求
    :return: 响应输出
    """
    conv = await get_or_create_conversation(db,user,req.conversation_id)
    if conv.title =="新会话":
        conv.title = req.message[:20]
        await db.commit()


    #messages表中存储用户消息
    await save_message(db,conv.id,role="user",content=req.message)

    input_dict = await build_messages_with_memory(db,conv.id,req.message)
    #LCEL链：动态提示词|LLM
    chain = get_prompt_template(ROLE_STUDENT,req.scene) | get_llm()

    try:
        ai_msg = await chain.ainvoke(
            input_dict
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


"""
以下模块为定义实现客户端的流式输出
"""
async def prepare_stream(db:AsyncSession,user:User,req:ChatRequest)->Conversation:
    """
    定义流式输出的准备阶段，获取或创建会话，并保存用户的问题，title标题。
    整体逻辑与handle_chat的逻辑一致

    :param db: 数据库连接
    :param user:用户信息
    :param req:请求信息
    :return:会话|创建会话
    """
    conv = await get_or_create_conversation(db,user,req.conversation_id)
    if conv.title =="新会话":
        conv.title=req.message[:20]
        await db.commit()

    await save_message(db,conv.id,role="user",content=req.message)
    return conv

async def stream_reply(
        db:AsyncSession,
        conversation_id:int,
        message:str,
        scene:str
)->AsyncGenerator:
    """
    大模型的相应流式出处到前端阶段：
        让模型流式返回数据给后端:async for chunk in model.astream,
        后端为前端流式推送数据yield

    :param db: 数据库连接
    :param conversation_id: 会话id
    :param message: 会话消息内容
    :param scene: 场景
    :return: 异步生成器
    """
    collected:list[str]=[]
    input_dict = await build_messages_with_memory(db,conversation_id,message)
    chain = get_prompt_template(ROLE_STUDENT,scene) | get_llm()
    try:
        async for chunk in chain.astream(input_dict):
            text = chunk.content
            if not text:
                continue
            collected.append(text)
            #向前端推送流式消息
            yield f"data:{json.dumps({'type':'delta','content':text},ensure_ascii=False)}\n\n"
    except Exception as e :
        yield f"data: {json.dumps({'type': 'error', 'message': '模型服务异常，请稍后重试'}, ensure_ascii=False)}\n\n"
        return

    # 落库
    assistant_msg = await save_message(db,conversation_id,role="assistant",content="".join(collected))
    yield f"data:{json.dumps({'type':'done','message_id':assistant_msg.id},ensure_ascii=False)}\n\n"



