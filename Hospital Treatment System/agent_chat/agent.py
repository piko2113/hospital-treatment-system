"""
Agent 核心：ReAct 循环
使用 DeepSeek API 的 Function Calling 能力做意图识别 → 工具调用 → 生成回答
按 session_id 隔离对话历史，避免多用户串号。
"""

import json
import os
import re
from typing import List, Dict, Optional

from openai import OpenAI

from .tools import TOOL_REGISTRY, get_tool_descriptions

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("⚠️ 未设置 DEEPSEEK_API_KEY 环境变量")

SYSTEM_PROMPT = """你是一个专业的AI医疗助手，帮助用户解答健康相关问题。

## 核心原则
1. **知识来源**：优先从知识库检索的信息回答；不要编造医学事实。
2. **免责声明**：涉及诊断、治疗建议时，必须声明"以上信息仅供参考，不能替代专业医疗诊断"。
3. **回答风格**：简洁、清晰、有条理。使用中文，适当使用换行和分段。
4. **不确定性**：如果不确定或知识库中没有相关信息，明确告知用户你不知道。

## 工具使用规则
- 当用户提到症状/疾病/就医问题时，优先用 search_knowledge 检索医学知识库。
- 当用户上传CT图片时，先用 ct_detect_nodules 检测结节位置，再用 ct_recognize 判断良恶性。
- 当用户询问论坛相关内容时，用 search_forum 搜索论坛。
- 你可以组合多个工具来回答一个完整的问题。
- 调用工具时，参数务必准确完整。

## 回答格式
- 先给出直接答案
- 然后补充详细信息（如果有）
- 最后加上免责声明（如果需要）

## 安全限制
- 绝对不提供处方药的具体用药剂量
- 绝对不承诺治疗效果
- 遇到紧急症状（如剧烈胸痛、大出血），务必建议立即就医
"""

# ── 多 session 隔离 ──────────────────────────────────
# key = session_id, value = 对话消息列表
_sessions: Dict[str, List[Dict]] = {}

# 每个 session 保留的最大对话轮数（超过则截断）
MAX_EXCHANGES = 20


def _get_history(session_id: str) -> List[Dict]:
    """获取指定 session 的对话历史，不存在则初始化。"""
    if session_id not in _sessions:
        _sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return _sessions[session_id]


def _trim_history(session_id: str):
    """截断超长的对话历史，保留系统提示 + 最近 MAX_EXCHANGES 轮。"""
    history = _sessions.get(session_id)
    if not history:
        return
    # 第一条是 system prompt，保留
    exchanges = history[1:]  # 去掉 system
    if len(exchanges) > MAX_EXCHANGES * 2:  # 每轮包含 user + assistant 两条
        keep = exchanges[-(MAX_EXCHANGES * 2):]
        _sessions[session_id] = [history[0]] + keep


def _get_client():
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")


def _build_functions():
    """将工具注册表转换为 OpenAI Function Calling 格式。"""
    functions = []
    for tool in TOOL_REGISTRY.values():
        properties = {}
        required = []
        for pname, pinfo in tool['parameters'].items():
            param_type = pinfo.get('type', 'string')
            if 'default' not in pinfo:
                required.append(pname)
            schema_type = {'string': 'string', 'int': 'integer', 'float': 'number'}.get(param_type, 'string')
            properties[pname] = {
                'type': schema_type,
                'description': pinfo.get('description', ''),
            }
        functions.append({
            'type': 'function',
            'function': {
                'name': tool['name'],
                'description': tool['description'],
                'parameters': {
                    'type': 'object',
                    'properties': properties,
                    'required': required,
                },
            },
        })
    return functions


def _call_tool(function_name: str, arguments: Dict) -> str:
    """执行工具调用并返回结果。"""
    tool = TOOL_REGISTRY.get(function_name)
    if not tool:
        return json.dumps({'error': f'未知工具: {function_name}'}, ensure_ascii=False)

    try:
        result = tool['fn'](**arguments)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({'error': str(e)}, ensure_ascii=False)


def reset_conversation(session_id: str):
    """重置指定 session 的对话历史。"""
    if session_id in _sessions:
        del _sessions[session_id]
    # 下一次调用 _get_history 时会重新初始化


def chat(user_message: str, session_id: str, user_image_path: Optional[str] = None) -> str:
    """
    主入口：处理用户消息，返回 AI 回答。
    支持 ReAct 循环：LLM → 工具调用 → 结果 → LLM → ...
    session_id 用于隔离不同用户的对话历史。
    """
    client = _get_client()
    functions = _build_functions()
    history = _get_history(session_id)

    # 如果用户上传了图片，在消息中附加上下文
    user_content = user_message
    if user_image_path:
        user_content += f"\n\n[用户上传了CT影像: {user_image_path}]"

    history.append({"role": "user", "content": user_content})

    # ReAct 循环（最多5轮工具调用）
    max_rounds = 5
    for _round in range(max_rounds):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=history,
                tools=functions,
                tool_choice="auto",
                temperature=0.3,
            )
        except Exception as e:
            return f"抱歉，我暂时无法回答，遇到错误: {str(e)}"

        message = response.choices[0].message

        # 没有工具调用 → 直接返回回答
        if not message.tool_calls:
            history.append({
                "role": "assistant",
                "content": message.content or "",
            })
            _trim_history(session_id)
            return message.content or "..."

        # 有工具调用
        assistant_msg = {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ],
        }
        history.append(assistant_msg)

        # 执行每个工具调用
        for tc in message.tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            tool_result = _call_tool(fn_name, fn_args)

            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_result,
            })

    # 超过最大工具调用轮数，强制 LLM 总结
    try:
        final = client.chat.completions.create(
            model="deepseek-chat",
            messages=history,
            temperature=0.3,
        )
        final_content = final.choices[0].message.content or ""
        history.append({
            "role": "assistant",
            "content": final_content,
        })
        _trim_history(session_id)
        return final_content
    except Exception as e:
        return f"处理超时，请稍后重试。错误: {str(e)}"


# ── 简单意图检测（无需 LLM 调用的快速判断） ──────────

_CT_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}


def detect_user_intent(message: str, has_image: bool = False) -> str:
    """快速检测用户意图（用于前端展示）。"""
    if has_image:
        return 'ct_recognize'
    if any(kw in message for kw in ['ct', '影像', '图片', '片子', '识别']):
        return 'ct_recognize'
    if any(kw in message for kw in ['挂什么科', '哪个科', '就医', '去哪里', '急诊']):
        return 'triage'
    if any(kw in message for kw in ['论坛', '文章', '讨论']):
        return 'forum'
    return 'knowledge'
