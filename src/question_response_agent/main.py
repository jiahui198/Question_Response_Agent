"""
FastAPI 应用入口。
启动方式：
    uv run uvicorn question_response_agent
"""
from fastapi import FastAPI
from question_response_agent.api.routers import health,auth
app = FastAPI(
    title="question-response-agent",
    version="0.1.0",
    description="基于FastAPI+Langgraph的智能体对话服务"
)

#把health路由组挂到app上
app.include_router(health.router)
app.include_router(auth.router)

@app.get("/")
async def root():
    """
    根路径，用来验证服务
    """
    return {"messages":"hello,fastapi"}