"""
限流依赖，限制但用户每分钟频繁的请求
"""
from fastapi import Depends,HTTPException,status

from question_response_agent.core.deps import get_current_user
from question_response_agent.core.redis import get_redis
from question_response_agent.models.user import User

RATE_LIMIT_PER_MINUTE = 20   #单用户每分钟最大请求量

async def rate_limit(current_user:User = Depends(get_current_user))->None:
    """
    固定窗口限流：
    key=rate:{user_id},首次计数时设置60秒过期，超限抛429.
    redis不可用时降级放行（打印警告不阻断业务）

    :param current_user: 用户信息
    """
    r = get_redis()
    key = f"rate:{current_user.id}"
    try:
        count = await r.incr(key)
        if count == 1 :
            await r.expire(key,60)
        if count > RATE_LIMIT_PER_MINUTE:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后再试"
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f'redis不可用，限流降级放行：{e}')








