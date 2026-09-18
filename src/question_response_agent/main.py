"""
FastAPI 应用入口。
启动方式：
    uv run uvicorn question_response_agent
"""
from fastapi import FastAPI

app = FastAPI(
    title="question-response-agent",
    version="0.1.0",
    description="基于FastAPI+Langgraph的智能体对话服务"
)

@app.get("/")
async def root():
    """
    根路径，用来验证服务跑起来
    :return: {'message':"hello,FastAPI!"}
    """
    return {"message":"Hello,FastAPI"}