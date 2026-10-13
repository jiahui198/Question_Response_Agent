"""
对话业务逻辑：组装LCEL链（动态提示词 |LLM）调用 --> 消息落库
"""
import json,re
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from question_response_agent.models.user import User
from question_response_agent.models.conversation import Conversation
from question_response_agent.models.messages import Message
from question_response_agent.models.user_memory import UserMemory
from question_response_agent.schemas.chat import ChatRequest, ChatResponse
from question_response_agent.agents.prompts.system_prompts import (
get_prompt_template,
ROLE_STUDENT
)
from question_response_agent.agents.llm import get_llm
from langchain_core.messages import HumanMessage,AIMessage,SystemMessage,AIMessageChunk
from langgraph.errors import GraphRecursionError
from question_response_agent.agents.graph import build_agent_graph
from question_response_agent.agents.prompts.system_prompts import build_system_messages
from sqlalchemy import func,select



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
本部分设计agent的长期记忆：跨会话的用户偏好/事实，新开一个会话也能记得
"""
async def extract_memories(
        db:AsyncSession,
        user_id:int,
        messages:list[Message]
)->int:
    """
    用llm从消息列表中抽取事实，写入user_memories表，返回新增记忆数

    :param db:数据库连接session
    :param user_id:用户ID
    :param messages:待抽取的消息列表
    :return:新增记忆数
    """
    if not messages:
        return 0
    dialog = "\n".join(f"{m.role}:{m.content}" for m in messages)

    prompt_text = (
        "请从以下对话中抽取用户的长期事实信息"
        "(如姓名、职业、技能、偏好、目标、重要约束等)\n"
        "以JSON数组形式返回,每项包含 memory_type 和 content 两个字段。\n"
        "memory_type 取值: profile(身份) / preference(偏好) / fact(事实) / goal(目标)\n"
        "无事实就返回空数组 []\n"
        "对话内容：\n" + dialog
    )

    llm = get_llm()
    resp = await llm.ainvoke(prompt_text)
    text = resp.content.strip()
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return 0
    try:
        items = json.loads(m.group(0))
    except json.JSONDecodeError:
        return 0

    #写入user_memories表
    added = 0
    for it in items:
        if not it.get("content"):
            continue
        mem = UserMemory(
            user_id=user_id,
            memory_type=it.get("memory_type","fact"),
            content=it['content'],
            importance=5
        )
        db.add(mem)
        added+=1
    if added:
        await db.commit()
    return added

async def load_user_memories(
        db:AsyncSession,
        user_id:int,
        limit:int = 10
)->str:
    """
    加载用户长期记忆，拼成文本注入prompt

    :param db: 数据库连接session
    :param user_id: 用户id
    :param limit:抽取记忆条数
    :return:拼接好的长期记忆文本
    """
    stmt = (
        select(UserMemory)
        .where(UserMemory.user_id == user_id)
        #按照创建时间降序排序
        .order_by(UserMemory.created_at.desc())
        .limit(limit)
    )
    rows = list((await db.execute(stmt)).scalars().all())

    if not rows:
        return ""

    lines = []
    type_map = {
        "profile":"用户身份",
        "preference":"用户偏好",
        "fact":"用户事实",
        "goal":"用户目标"
    }
    for m in rows:
        label = type_map.get(m.memory_type,m.memory_type)
        lines.append(f"{label}:{m.content}")
    return "【跨会话记忆】\n" + "\n".join(lines)+"\n"


"""
本部分用于设计agent的会话压缩，将长上下文借助llm进行压缩，生成摘要
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
    if total <= SUMMARY_THRESHOLD:
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


async def build_agent_messages(
        db:AsyncSession,
        conv:Conversation,
        user_input :str,
        scene:str,
        window:int = MEMORY_WINDOW
)->list:
    """
    组装agent输入消息列表：System（身份+长期记忆+会话摘要）+最近窗口历史+本次用户输入

    :param db: 数据库连接session
    :param conv: 本次会话
    :param user_input: 用户输入
    :param scene: 场景
    :param window: 总结摘要窗口大小
    :return:系统提示词
    """
    stmt =  (
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.desc(),Message.id.desc())
        .limit(window)
        .offset(1)
    )
    rows = list(reversed((await db.execute(stmt)).scalars().all()))

    history=[]
    for m in rows:
        if m.role == "user":
            history.append(HumanMessage(content=m.content))
        elif m.role =="assistant":
            history.append(AIMessage(content=m.content))

    summary = await maybe_summary(db,conv,window)
    summary_text = f"【会话摘要】{summary}\n" if summary else ""
    memories_text = await load_user_memories(db,conv.user_id)
    system = build_system_messages(ROLE_STUDENT,scene,memories_text,summary_text)
    return [system,*history,HumanMessage(content=user_input)]


"""
以下模块主要实现基本的对话，不含有流式输出
"""
async def handle_chat(db:AsyncSession,user:User,req:ChatRequest)->ChatResponse:
    """
    主流程函数：会话就绪->存用户消息->组装agent消息->Langgraph生成回复->存AI消息->抽取长期记忆

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

    messages = await build_agent_messages(db,conv,req.message,req.scene)
    #生成graph图
    graph = build_agent_graph(ROLE_STUDENT,req.scene,ctx={"db":db,"user_id":user.id})

    try:
        result = await graph.ainvoke(
            {"messages":messages},
            config={"recursion_limit":10}  #设置agent-tool最大循环次数为10次
        )
    except GraphRecursionError as e:
        raise LLMInvocationError("回复生成过于复杂,请稍后重试") from e
    except Exception as e :
        raise LLMInvocationError(f"agent调用失败{e}") from e

    ai_msg = result["messages"][-1]

    #存ai回复
    assistant_msg = await save_message(db,conv.id,role="assistant",content=ai_msg.content)

    #新增，抽取消息历史中的事实，存入user_memories中
    recent_stmt = (
        select(Message)
        .where(Message.conversation_id==conv.id)
        .order_by(Message.created_at.desc(),Message.id.desc())
        .limit(6)
    )
    recent = list(reversed(list((await db.execute(recent_stmt)).scalars().all())))
    #将历史消息抽取存入user_memories表中
    await extract_memories(db, user.id, recent)

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
        conv:Conversation,
        message:str,
        scene:str,
        user_id:int
)->AsyncGenerator:
    """
    大模型的相应流式出处到前端阶段：
        让模型流式返回数据给后端:async for chunk in graph.astream,
        后端为前端流式推送数据yield

    :param db: 数据库连接
    :param conv: 会话
    :param message: 会话消息内容
    :param scene: 场景
    :return: 异步生成器
    """
    collected:list[str]=[]
    messages = await build_agent_messages(db,conv,message,scene)
    graph = build_agent_graph(ROLE_STUDENT,scene,ctx={"db":db,"user_id":user_id})
    try:
        async for chunk,_meta in graph.astream(
                {"messages":messages},
                config={"recursion_limit":10},
                stream_mode="messages"
        ):
            if not isinstance(chunk,AIMessageChunk):
                continue
            text = chunk.content
            if not text:
                continue
            collected.append(text)
            yield f"data: {json.dumps({ 'type' : 'delta' , 'content' :text} ,ensure_ascii=False)}\n\n"
    except Exception:
        yield f"data: {json.dumps({'type': 'error', 'message': '模型服务异常，请稍后重试'}, ensure_ascii=False)}\n\n"
        return
    assistant_msg = await save_message(db, conv.id, role="assistant", content="".join(collected))
    yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg.id}, ensure_ascii=False)}\n\n"

