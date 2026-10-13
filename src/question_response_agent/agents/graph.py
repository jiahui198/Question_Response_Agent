from langgraph.graph import StateGraph,MessagesState,START,END
from question_response_agent.agents.tools.registry import load_tools
from question_response_agent.agents.llm import get_llm
from langchain_core.messages import ToolMessage
from langgraph.errors import GraphRecursionError

#用来检查运行时对象、函数等的基本信息
import inspect

def _make_tool_node(tools:list,ctx:dict):
    """
    自定义工具执行节点，替代框架的ToolNode节点，解决工具参数只能由模型传输的问题
    工具失败降级策略：工具多次调用失败后执行降级兜底机制。
    :param tools:可用工具列表
    :param ctx: 运行时上下文字典例如：用户ID、数据库连接等
    :return:工具节点
    """
    tools_map = {t.name:t for t in tools}

    async def _invoke_with_retry(tool,args:dict,retries:int = 1)->str:
        """
        定义工具重试策略函数。

        :param tool:执行工具
        :param args:工具参数
        :param retries:重试次数
        :return:工具执行成功结果/失败结果
        """
        for attempt in range(retries+1):
            try:
                out = await tool.ainvoke(args)
                return str(out)
            except Exception :
                return "工具执行失败，请基于已有知识直接回答用户"
        return "工具执行失败，请基于已有知识直接回答用户"

    async def tool_node(state:MessagesState)->dict:
        """
        工具节点执行主流程函数，将返回工具执行的结果ToolMessage

        :param state: 图状态
        :return: 返回工具执行dict
        """
        last = state["messages"][-1]
        results = []
        for call in last.tool_calls:
            tool = tools_map.get(call["name"])
            if tool is None:
                results.append(ToolMessage(
                    content=f"工具不存在：{tool['name']}",
                    tool_call_id = call["id"]
                ))
                continue
            #只注工具签名里声明的上下文参数
            fn = getattr(tool,"coroutine",None) or getattr(tool,"func",None)
            sig = inspect.signature(fn)
            #检查传入的上下文字典，看里面是否有我们工具需要的参数，有就提取出来
            inject = {k:v for k,v in ctx.items() if k in sig.parameters}
            #将模型生成的参数信息和程序的参数注入结合起来
            out = await _invoke_with_retry(tool,{**call["args"],**inject})
            results.append(ToolMessage(content=out,tool_call_id=call["id"]))
        return {"messages":results}
    return tool_node


def build_agent_graph(user_role,scene:str,ctx:dict | None = None):
    """
    按照角色+场景构建agent图（工具动态加载，图也是运行时构建的）

    :param ctx:程序运行时上下文
    :param user_role:用户角色身份
    :param scene: 场景
    """
    ctx = ctx or {}
    tools = load_tools(user_role,scene)
    llm = get_llm()
    #模型绑定工具，让模型知道可用哪些工具
    llm_with_tools = llm.bind_tools(tools=tools)

    async def agent_node(state:MessagesState)->dict:
        ai_msg = await llm_with_tools.ainvoke(state["messages"])
        return {"messages":[ai_msg]}

    def should_continue(state:MessagesState)->str:
        """
        条件边：最后一条消息有tool_calls->去tools节点，没有->结束
        """
        last = state["messages"][-1]
        if last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(MessagesState)
    graph.add_node("agent",agent_node)
    graph.add_node("tools",_make_tool_node(tools=tools,ctx=ctx))
    graph.add_edge(START,"agent")
    #添加条件边，返回tools节点就走tools节点，返回END节点就走END节点
    graph.add_conditional_edges("agent",should_continue,{'tools':'tools',END:END})
    graph.add_edge("tools","agent")     #工具结果再次回到agent做总结

    return graph.compile()





