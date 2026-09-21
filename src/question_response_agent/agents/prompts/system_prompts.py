"""
此文件实现动态提示词模版库，动态加载我们的提示词
"""

from langchain_core.prompts import (
ChatPromptTemplate,
SystemMessagePromptTemplate,
HumanMessagePromptTemplate
)

#----常亮----
SCENE_CHAT = "chat"
SCENE_QA = "qa"

#用户身份
ROLE_STUDENT = "student"
ROLE_PROFESSIONAL ="professional"

#----模版定义----

#学生+自由对话
_TPL_STUDENT_CHAT =ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(
        "你是一个耐心的AI学习助手。"
        "当前对话身份：{role}。"
        "请用通俗易懂的中文回答，适当的举例子帮助理解。"
        "如果用户问的是编程问题，优先给出代码示例并加注释。"
    ),
    HumanMessagePromptTemplate.from_template(
        "{user_input}"
    )
])

#学生+知识问答
_TPL_STUDENT_QA = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(
        "你是一个严谨的AI问答助手。"
        "当前对话身份：{role}。"
        "回答知识类问题时：\n"
        "1.先给出直接答案\n"
        "2.再补充原理/背景\n"
        "3.如果有多种说法要明确区分\n"
        "4.不确定的内容要诚实说明"
    ),
    HumanMessagePromptTemplate.from_template("{user_input}")
])

#专业人士+自由对话
_TPL_PRO_CHAT = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(
        "你是一个AI助手。"
        "当前对话身份：{role}。"
        "请用简洁、专业的语言回答，避免冗余铺垫。"
        "输出要有结构，必要时分点。"
    ),
    HumanMessagePromptTemplate.from_template("{user_input}")
])

#路由，快速选型提示词
_TEMPLATES:dict[tuple[str,str],ChatPromptTemplate] = {
    (ROLE_STUDENT,SCENE_CHAT):_TPL_STUDENT_CHAT,
    (ROLE_STUDENT,SCENE_QA) :_TPL_STUDENT_QA,
    (ROLE_PROFESSIONAL,SCENE_CHAT):_TPL_PRO_CHAT
}

_DEFAULT_TEMPLATE = _TPL_STUDENT_CHAT

def build_chat_prompt(
        user_input:str,
        user_role:str = ROLE_STUDENT ,
        scene:str = SCENE_CHAT
)->ChatPromptTemplate:
    """
    根据用户身份和场景生成相对应的提示词

    :param user_inout:用户问题输入
    :param user_role: 用户角色
    :param scene: 场景：聊天/问答
    :return: 提示词
    """
    tpl = _TEMPLATES.get((user_role,scene),_DEFAULT_TEMPLATE)

    return tpl.partial(role=user_role).format_messages(user_input=user_input)






