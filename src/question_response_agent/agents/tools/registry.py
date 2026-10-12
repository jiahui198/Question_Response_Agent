"""
工具定义（@tool装饰器）+注册表+动态加载

-@tool:函数docstring->描述，类型签名->参数schema，自动生成
- InjectedToolArg: db/user_id 由运行时注入,不暴露给LLM，不允许llm传参
- TOOL_ACCESS_CONFIG: 角色+场景→可用工具名单,运行时动态加载
"""
from typing import Annotated
from datetime import datetime
from langchain_core.tools import tool,InjectedToolArg
import ast,operator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from question_response_agent.models.user_memory import UserMemory

@tool
async def get_current_time()->str:
    """
    查询当前的日期和时间。当想知道现在几点、今天日期时使用
    :return: 日期和时间
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
async def calculator(expression:str)->str:
    """
    四则运算表达式。当用户需要数学运算时使用，expression为算式字符串
    :param expression: 算式字符串
    :return: 结果值
    """
    _OPS = {
        ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg
    }
    def _safe_eval(node):
        if isinstance(node,ast.Constant) and isinstance(node.value,(int,float)):
            return node.value
        if isinstance(node,ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_safe_eval(node.operand))
        raise ValueError('不支持的表达式')
    try :
        result = _safe_eval(ast.parse(expression, mode= "eval" ).body)
        return f"{expression}={result}"
    except Exception as e:
        return f"计算失败：{e}"

@tool
async def query_my_memories(
        db:Annotated[AsyncSession,InjectedToolArg],
        user_id:Annotated[int,InjectedToolArg]
)->str:
    """
    查询当前用户的长期记忆（姓名、偏好、目标等）。当用户问'你还记得我吗/我叫什么'之类问题使用
    :param db: 数据库连接session
    :param user_id: 用户id
    :return: 用户记忆文本
    """
    stmt = select(UserMemory).where(UserMemory.user_id==user_id).limit(10)
    rows = list((await db.execute(stmt)).scalars().all())
    if not rows:
        return "暂无用于记忆"
    return "".join(f"{m.memory_type}:{m.content}" for m in rows)


TOOLS_REGISTRY: dict = {
    t.name: t for t in [get_current_time, calculator, query_my_memories]
}
#注册表
TOOL_ACCESS_CONFIG = {
    "student":{
        "chat":["get_current_time","calculator","query_my_memories"],
        "qa":["get_current_time"]
    },
    "professional":{
        "chat":["get_current_time","calculator"]
    },
}
_DEFAULT_TOOLS = ["get_current_time"]

def load_tools ( user_role: str , scene: str ) -> list :
    """
    按照身份，场景，动态加载工具列表

    :param user_role: 用户身份
    :param scene: 场景
    :return: 工具列表
    """
    names = TOOL_ACCESS_CONFIG.get(user_role, {}).get(scene, _DEFAULT_TOOLS)
    return [TOOLS_REGISTRY[n] for n in names]

