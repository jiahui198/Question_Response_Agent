"""
FastAPI 应用入口。
启动方式：
    uv run uvicorn question_response_agent
"""
from fastapi import FastAPI
from question_response_agent.api.routers import health,auth,chat,conversations

from contextlib import asynccontextmanager
from question_response_agent.db.session import init_db
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(app:FastAPI):
    """
    创建异步上下文管理器，启动时自动创建数据库
    :param app:
    :return:
    """
    #启动时：建表（已存在则跳过，幂等）
    await init_db()
    yield

app = FastAPI(
    title="question-response-agent",
    version="0.1.0",
    description="基于FastAPI+Langgraph的智能体对话服务",
    lifespan=lifespan
)

#把health路由组挂到app上
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.mount("/",StaticFiles(directory= "front" , html= True),name="front")

@app.get("/")
async def root():
    """
    根路径，用来验证服务
    """
    return {"messages":"hello,fastapi"}