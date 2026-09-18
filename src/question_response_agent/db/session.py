#类型提示，返回异步生成器
from collections.abc import AsyncGenerator

#create_async_engine用来创建异步数据库引擎
#async_sessionmaker用来创建生产Session的工厂
from sqlalchemy.ext.asyncio import AsyncSession,async_sessionmaker,create_async_engine

from question_response_agent.core.config import settings
from question_response_agent.db.base import Base

#1.创建异步引擎
engine = create_async_engine(
    settings.mysql_url,                 #设置连接字符串
    echo = settings.app_env =="dev",    #dev模式打印每条SQL，方便调试
    pool_pre_ping = True                #连接池里的连接先ping一下，防止mysql主动断开
)

#2.创建session工厂
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,           #指定产品的类型
    expire_on_commit=False         #commit后不自动过期对象
)

async def get_db()->AsyncGenerator[AsyncSession,None]:
    """
    FastAPI依赖注入用：每次请求自动创建session，用完自动关闭
    返回：
        AsyncGenerator(AsyncSession),异步连接对象
    关闭：
        当路由函数使用完session执行完数据库操作后调用session.close
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db()->None:
    """
    异步创建数据库中所有的表
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)




