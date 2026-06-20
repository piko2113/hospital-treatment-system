"""
Agent Chat 视图
"""

import os
import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from .models import ChatHistory
from .agent import chat, reset_conversation, detect_user_intent
from .rag_engine import build_kb
from .tools import get_tool_descriptions, ct_recognize, ct_detect_nodules


def chat_page(request):
    """渲染对话页面。"""
    from home.models import Topic
    topics = Topic.objects.all()
    return render(request, "chat.html", {"topics": topics})


def check_kb(request):
    """检查知识库状态。"""
    from .rag_engine import check_kb_status
    try:
        info = check_kb_status()
        return JsonResponse({'status': 'ready', **info})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})


@csrf_exempt
def api_chat(request):
    """对话 API：接收用户消息，返回 AI 回答。"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = {}

        message = data.get('message', '').strip()
        action = data.get('action', 'chat')

        # 确保 session 存在（用于隔离对话历史）
        if not request.session.session_key:
            request.session.save()  # 强制创建 session
        session_id = request.session.session_key

        if not message and action != 'new_session':
            return JsonResponse({'error': '请输入消息'}, status=400)

        # 操作分发
        if action == 'new_session':
            reset_conversation(session_id)
            return JsonResponse({'reply': '你好！我是AI医疗助手，有什么可以帮你的？\n\n你可以问我：\n- 症状相关的问题（如"发烧咳嗽挂什么科"）\n- 疾病知识（如"什么是肺炎"）\n- 上传CT影像让我识别\n- 论坛相关的问题'})

        if action == 'detect_intent':
            intent = detect_user_intent(message)
            return JsonResponse({'intent': intent})

        # 默认：对话
        try:
            reply = chat(message, session_id=session_id)
            # 保存对话记录（仅登录用户）
            username = request.session.get('s_name_001', '')
            if username and action != 'new_session':
                try:
                    ChatHistory.objects.create(
                        username=username,
                        question=message,
                        answer=reply,
                    )
                except Exception:
                    pass  # 保存失败不影响对话
            return JsonResponse({'reply': reply})
        except Exception as e:
            return JsonResponse({'error': f'处理出错: {str(e)}'}, status=500)

    return JsonResponse({'error': '仅支持 POST'}, status=405)


@csrf_exempt
def api_ct_image(request):
    """CT 图片上传 + 识别 API。"""
    if request.method == 'POST':
        image = request.FILES.get('image')
        if not image:
            return JsonResponse({'error': '请上传图片'}, status=400)

        model_name = request.POST.get('model', 'resnet50')

        from home.views import handle_uploaded_file
        image_url, image_abs_path = handle_uploaded_file(image)

        # 1. 肺炎分类（旧）
        result = ct_recognize(image_abs_path, model_name=model_name)
        result['image_url'] = image_url

        # 2. YOLO 肺结节检测（新）
        nodule_result = ct_detect_nodules(image_abs_path)
        result['nodule_detection'] = nodule_result

        return JsonResponse(result)

    return JsonResponse({'error': '仅支持 POST'}, status=405)


@csrf_exempt
def api_history(request):
    """返回当前登录用户的最近 3 条提问记录。"""
    if request.method == 'GET':
        username = request.session.get('s_name_001', '')
        if not username:
            return JsonResponse({'history': []})
        records = ChatHistory.objects.filter(username=username).order_by('-created_at')[:3]
        data = []
        for r in records:
            data.append({
                'question': r.question,
                'answer': (r.answer or '')[:100],
                'time': r.created_at.strftime('%m-%d %H:%M'),
            })
        return JsonResponse({'history': data})
    return JsonResponse({'error': '仅支持 GET'}, status=405)
