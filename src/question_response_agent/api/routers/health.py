"""
健康检查路由:验证服务器本身和数据库连接是否正常
"""
from fastapi import APIRouter,Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from question_response_agent.db.session import get_db

#APIRouter:路由的分组容器，最后统一挂到APP上
router = APIRouter(tags=["健康检查"])

@router.get("/health")
async def health():
    """
    最简健康检查，服务器没问题就会返回数据
    """
    return {"status":"ok","service":"question-response-agent"}

@router.get("/health/db")
async def health_db(db:AsyncSession = Depends(get_db)):
    """
    数据库健康检查：
        向数据库发送一条查询数据，验证整条链路
    """

    result = await db.execute(text("SELECT 1"))
    value = result.scalar()
    return {"status":"ok","database":"connected","query_result":value}
