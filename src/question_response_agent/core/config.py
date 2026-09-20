"""
本文件是使用pydantic_settings库中类方法读取.env环境配置，以便程序运行。
    继承BaseSetting类，并使用SettingsConfigDict定义文件读取路径和读取方式；
    之后使用lru_cache装饰器将运行返回的配置变量放在缓存中。
"""

#lru_cache缓存装饰器
from functools import lru_cache

#BaseSettings一个基类，继承它就能自动从.env文件中读取环境变量并赋值给类属性
#SettingsConfigDict，用来配置baseSetting的行为
from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    """
    应用配置类
    """
    model_config = SettingsConfigDict(
        env_file=".env",            #配置文件路径
        env_file_encoding="utf-8",   #文件解析格式utf-8
        case_sensitive=False,
        extra="ignore",              #多写字段不报错
    )

    #-----应用基本信息-----
    app_name:str = "question-response-agent"
    app_env:str = "dev"
    app_host:str = "0.0.0.0"
    app_port :int = 8000

    #-----MYSQL-----
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "question_response_agent"

    @property
    def mysql_url(self)->str:
        """
        将上面的mysql配置信息，拼接成SQLAlchemy能用的异步MySQL连接串。

        格式：格式：mysql+aiomysql://用户名:密码@主机:端口/数据库名?charset=utf8mb4
        :return: mysql的异步连接串
        """
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )
    #-----Redis-----
    redis_host:str = "127.0.0.1"
    redis_port:int = 6379
    redis_password:str = ""
    redis_db:int = 0

    #----JWT----
    jwt_secrete:str = "please_change_me" #秘钥
    jwt_algorithm:str = "HS256"          #算法
    jwt_expire_minutes:int = 1440        #有效期

    #------LLM-------
    dashscope_api_key:str = ""
    llm_model:str = "qwen-plus"

@lru_cache
def get_settings()->Settings:
    """
    单例：整个进程只创建一次Settings对象，缓存起来复用

    用法：from question_response_agent.core.config import settings
    """
    return Settings()

settings = get_settings()







