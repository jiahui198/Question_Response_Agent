"""
临时脚本，用于测试创建模型
"""
import asyncio
from question_response_agent.agents.llm import get_llm

async def main():
    llm = get_llm()
    resp = await llm.ainvoke("你好，用一句话介绍一下你自己")
    print("=====模型生成=====")
    print(resp.content)   # ChatTongyi.ainvoke 返回 AIMessage，取 .content


if __name__ == "__main__":
    asyncio.run(main())