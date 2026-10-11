"""
Redis 客户端单例：进程内单例，供限流/缓存等场景信息
"""
from functools import lru_cache

import redis.asyncio as aioredis

from question_response_agent.core.config import settings

@lru_cache
def get_redis()->aioredis.Redis:
    """
    返回一步Redis客户端（单例）
    显示创建连接池：
                max_connections      最大连接数
                decode_response=True 返回值是str
    """
    pool = aioredis.ConnectionPool(
        host = settings.redis_host,
        port = settings.redis_port,
        password=settings.redis_password or None,
        db = settings.redis_db,
        max_connections=50,          #设置连接池最大连接处50
        decode_responses = True,     #redis直接返回字符串
        health_check_interval = 30   #每30秒做一次健康检查，发现死连接
    )
    return aioredis.Redis(connection_pool=pool)