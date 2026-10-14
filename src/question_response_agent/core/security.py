"""
安全工具：密码哈希+JWT签发与校验
JWT将客户端发送过来的数据通过JWT算法进行加密，由三部分组成：
    Header(头部)  :包含token类型和采用的加密算法
    Payload（负载）：存放要加密的有效信息
    Signature（签名）：对信息进行加密签名
"""

from datetime import datetime,timedelta,timezone
from jose import JWTError,jwt
from passlib.context import CryptContext

from question_response_agent.core.config import settings


#----密码哈希器----
pwd_context = CryptContext(schemes=["bcrypt"],deprecated="auto")

def hash_password(plain_password:str)->str:
    """
    把明文密码哈希后存数据库

    :param plain_password:客户端发送的原始密码数据
    :return: 哈希后的数值
    """
    return pwd_context.hash(plain_password)

def verify_password(plain_password:str,hashed_password:str)->bool:
    """
    验证明文密码和数据库里的哈希是否匹配
    :param plain_password: 明文密码
    :param hashed_password: 数据库存的密码
    :return: bool
    """
    return pwd_context.verify(plain_password,hashed_password)

#----JWT----
def create_access_token(user_id:int):
    """
    登录成功后给用户签发一张JWT

    Payload:
        -sub:subject,token发给谁，里面存放用户id
        -exp:expiration过期时间
    :param user_id:
    :return: JWT
    """
    expire = datetime.now(timezone.utc)+timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub":str(user_id),
        "exp":expire
    }
    return jwt.encode(payload,settings.jwt_secret,algorithm=settings.jwt_algorithm)

def decode_access_token(token:str)->int:
    """
    校验JWT：成功返回用户id，失败抛出JWTError
    :param token:
    :return: user_id | JWTError
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )
        user_id_str:str | None = payload.get("sub")
        if user_id_str is None:
            raise JWTError("token里面没有JWT相关字段")
        return int(user_id_str)
    except JWTError:
        raise










