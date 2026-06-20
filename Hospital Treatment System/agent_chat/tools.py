"""
工具层：Agent 可以调用的工具函数
"""

import os
from typing import Dict, Any
from django.conf import settings


# ── 工具 1: CT 影像识别 ─────────────────────────────

def ct_recognize(image_path: str, model_name: str = "resnet50") -> Dict[str, Any]:
    """调用 CT 识别模型，返回识别结果。"""
    try:
        from home.recognition_model import predict, is_model_available
        if not is_model_available(model_name):
            available = [k for k in ['mobilenetv2', 'resnet50'] if is_model_available(k)]
            model_name = available[0] if available else 'mobilenetv2'
            return {
                'success': False,
                'error': f'所选模型不可用，可用模型: {available}',
            }
        label, confidence = predict(image_path, backbone_name=model_name)
        return {
            'success': True,
            'model': model_name,
            'result': label,
            'confidence': round(confidence, 4),
            'description': f'{label}（置信度: {round(confidence * 100, 2)}%）',
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── 工具 2: 搜索知识库 ───────────────────────────────

def search_knowledge(query: str, top_k: int = 4) -> Dict[str, Any]:
    """从医学知识库中检索相关信息。"""
    try:
        from .rag_engine import search_kb
        results = search_kb(query, top_k=top_k)
        if not results:
            return {
                'success': True,
                'results': [],
                'summary': '未找到相关信息。',
            }
        # 拼接上下文
        contexts = []
        sources = set()
        for r in results:
            contexts.append(r['content'])
            if r['source']:
                sources.add(r['source'])
        return {
            'success': True,
            'results': [r['content'] for r in results],
            'sources': list(sources),
            'context': '\n---\n'.join(contexts),
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── 工具 3: 肺结节检测（YOLOv8）───────────────────────

def ct_detect_nodules(image_path: str, conf_threshold: float = 0.25) -> Dict[str, Any]:
    """使用 YOLOv8 模型检测 CT 影像中的肺结节，返回结节位置和置信度。"""
    try:
        from yolo_detection.detect import LungNoduleDetector
        import os
        # 模型路径在项目 yolo_detection 目录下
        model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'yolo_detection')
        model_path = os.path.join(model_dir, 'runs', 'yolov8n_nodule', 'weights', 'best.pt')
        
        if not os.path.exists(model_path):
            return {'success': False, 'error': '肺结节检测模型未训练，请先运行 train_yolo.py'}
        
        detector = LungNoduleDetector(model_path)
        nodules = detector.detect_nodules(image_path, conf=conf_threshold)
        
        if not nodules:
            return {
                'success': True,
                'nodules': [],
                'count': 0,
                'description': '未检测到肺结节。',
            }
        
        desc_parts = []
        for i, n in enumerate(nodules, 1):
            bbox = n['bbox']
            size = max(bbox[2] - bbox[0], bbox[3] - bbox[1])
            desc_parts.append(
                f'结节{i}: 位置({bbox[0]},{bbox[1]})-({bbox[2]},{bbox[3]}), '
                f'大小约{size}像素, 置信度{n["confidence"]:.1%}'
            )
        
        return {
            'success': True,
            'nodules': nodules,
            'count': len(nodules),
            'description': '; '.join(desc_parts),
        }
    except Exception as e:
        return {'success': False, 'error': f'结节检测失败: {str(e)}'}


# ── 工具 4: 查论坛文章 ───────────────────────────────

def search_forum(query: str) -> Dict[str, Any]:
    """从论坛文章中检索相关内容。"""
    try:
        from home.models import Article
        articles = Article.objects.filter(content__icontains=query)[:5]
        if not articles:
            return {
                'success': True,
                'results': [],
                'summary': '论坛中未找到相关文章。',
            }
        results = []
        for a in articles:
            # 截取包含关键词的片段
            content_preview = a.content[:200] if len(a.content) > 200 else a.content
            results.append({
                'id': a.id,
                'title': a.title,
                'author': a.author,
                'preview': content_preview,
            })
        return {
            'success': True,
            'results': results,
            'summary': f'找到 {len(results)} 篇相关文章。',
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── 工具注册表（供 Agent 使用） ──────────────────────

TOOL_REGISTRY = {
    'ct_recognize': {
        'name': 'ct_recognize',
        'description': '对肺部CT影像进行AI识别，判断是否为肺炎。需要用户提供图片文件的路径。',
        'parameters': {
            'image_path': {'type': 'string', 'description': 'CT图片文件的完整路径'},
            'model_name': {
                'type': 'string',
                'description': '使用的模型：mobilenetv2（轻量快速）或 resnet50（高精度），默认resnet50',
                'default': 'resnet50',
            },
        },
        'fn': ct_recognize,
    },
    'search_knowledge': {
        'name': 'search_knowledge',
        'description': '搜索医学知识库，查找疾病症状、治疗方案、药品信息、就医建议等。',
        'parameters': {
            'query': {'type': 'string', 'description': '搜索关键词，尽量完整描述问题'},
            'top_k': {'type': 'int', 'description': '返回结果数量', 'default': 4},
        },
        'fn': search_knowledge,
    },
    'ct_detect_nodules': {
        'name': 'ct_detect_nodules',
        'description': '对肺部CT影像进行YOLOv8肺结节检测，返回结节的位置、大小和置信度。比ct_recognize更精细，可定位多个结节。',
        'parameters': {
            'image_path': {'type': 'string', 'description': 'CT图片文件的完整路径'},
            'conf_threshold': {
                'type': 'float',
                'description': '置信度阈值（0-1），越高越严格，默认0.25',
                'default': 0.25,
            },
        },
        'fn': ct_detect_nodules,
    },
    'search_forum': {
        'name': 'search_forum',
        'description': '搜索论坛中的健康相关讨论文章。',
        'parameters': {
            'query': {'type': 'string', 'description': '搜索关键词'},
        },
        'fn': search_forum,
    },
}


def get_tool_descriptions() -> str:
    """生成工具描述文本，供 LLM 理解可用工具。"""
    lines = []
    for tool in TOOL_REGISTRY.values():
        params_desc = []
        for pname, pinfo in tool['parameters'].items():
            required = '（必填）' if 'default' not in pinfo else f'（可选，默认: {pinfo["default"]}）'
            params_desc.append(f"    - {pname}: {pinfo['description']} {required}")
        params_str = '\n'.join(params_desc)
        lines.append(f"### {tool['name']}")
        lines.append(f"描述: {tool['description']}")
        lines.append(f"参数:\n{params_str}")
    return '\n\n'.join(lines)
