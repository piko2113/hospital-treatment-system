"""
多模态 Agent：CT 影像识别 + 知识库自动串联

流程：
  用户上传CT图片
    → Step 1: 视觉推理（ResNet50 分类 + YOLOv8 结节检测）
    → Step 2: 构建 RAG 查询（把视觉结果转成自然语言检索词）
    → Step 3: RAG 检索知识库（匹配相关疾病/诊疗方案）
    → Step 4: DeepSeek 生成综合诊断报告
    → 返回结构化结果
"""

import json
import os
from typing import Dict, Any, Optional, List

from openai import OpenAI
import httpx

from .tools import ct_recognize, ct_detect_nodules, search_knowledge

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("⚠️ 未设置 DEEPSEEK_API_KEY 环境变量")

# 代理配置（仅当环境变量显式设置才使用）
_PROXY_URL = os.environ.get("OPENAI_PROXY")


def _create_client():
    """创建 DeepSeek 客户端。如需代理请设置 OPENAI_PROXY 环境变量。"""
    if _PROXY_URL:
        try:
            http_client = httpx.Client(proxies=_PROXY_URL, timeout=120)
            return OpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com",
                http_client=http_client,
            )
        except Exception:
            pass
    return OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
    )

# ── 多模态分析报告系统提示 ──────────────────────────

REPORT_SYSTEM_PROMPT = """你是一个专业的AI医疗影像分析助手。你的任务是根据CT影像分析结果和医学知识库信息，生成一份清晰、专业的综合诊断报告。

## 输出格式要求（严格按此结构输出）

### 📋 影像分析结果
- 分类结果：[正常/异常]
- 置信度：[具体数值]
- 检测到结节：[数量]个
- 结节详情：
  - 结节1：位置、大小、置信度
  - 结节2：...

### 📖 可能的疾病信息
（基于知识库检索结果，列出可能相关的疾病/症状/诊疗建议）
- ...

### 🤖 AI综合建议
（综合影像分析和医学知识，给出建议）
- ...

### ⚠️ 免责声明
以上信息仅供参考，不能替代专业医疗诊断。如有身体不适，请及时就医。

## 规则
1. 如实反映视觉分析结果，不要夸大或缩小。
2. 如果视觉分析不可靠（置信度低），要在报告中明确说明。
3. 知识库内容与视觉结果结合时，要注明"可能"、"建议进一步检查"等措辞。
4. 绝对不要给出确诊结论。
5. 用中文输出，语言通俗易懂。
"""


# ── 核心函数 ──────────────────────────────────────

def build_rag_query(cls_result: Dict, det_result: Dict) -> str:
    """把视觉分析结果转成 RAG 检索用的自然语言查询。"""
    query_parts = []

    # 分类结果
    label = cls_result.get("result", "")
    confidence = cls_result.get("confidence", 0)
    if label == "异常":
        query_parts.append(f"肺部影像学异常，诊断置信度{confidence:.0%}")
    elif label == "正常":
        query_parts.append("肺部CT影像正常")
    else:
        query_parts.append(f"肺部CT影像: {label}")

    # 结节检测
    if det_result.get("success") and det_result.get("count", 0) > 0:
        nodules = det_result.get("nodules", [])
        query_parts.append(f"检出{len(nodules)}个肺结节")
        # 取置信度最高的结节描述
        if nodules:
            top = max(nodules, key=lambda n: n.get("confidence", 0))
            bbox = top.get("bbox", [0, 0, 0, 0])
            size = max(bbox[2] - bbox[0], bbox[3] - bbox[1])
            query_parts.append(f"最大结节大小约{size}像素，置信度{top.get('confidence', 0):.0%}")
    elif det_result.get("success"):
        query_parts.append("未检出肺结节")
    else:
        query_parts.append("结节检测不可用")

    query = " ".join(query_parts)
    return query


def format_visual_summary(cls_result: Dict, det_result: Dict) -> str:
    """生成视觉分析的文本摘要，供 LLM 生成报告时使用。"""
    lines = []

    # 分类结果
    label = cls_result.get("result", "未知")
    confidence = cls_result.get("confidence", 0)
    model = cls_result.get("model", "未知")
    model_name_map = {
        "mobilenetv2": "MobileNetV2（轻量快速）",
        "resnet50": "ResNet50（高精度）",
        "ensemble": "集成模型（加权平均）",
    }
    model_display = model_name_map.get(model, model)
    lines.append(f"分类模型：{model_display}")
    lines.append(f"分类结果：{label}")
    lines.append(f"置信度：{confidence:.4f}（{confidence*100:.2f}%）")

    # 结节检测
    if det_result.get("success"):
        count = det_result.get("count", 0)
        lines.append(f"\n结节检测：")
        lines.append(f"  检出结节：{count}个")
        if count > 0:
            for i, n in enumerate(det_result.get("nodules", []), 1):
                bbox = n.get("bbox", [])
                if len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                    size = max(x2 - x1, y2 - y1)
                    lines.append(f"    结节{i}：位置({x1},{y1})-({x2},{y2})，大小约{size}像素，置信度{n.get('confidence', 0):.1%}")
                else:
                    lines.append(f"    结节{i}：置信度{n.get('confidence', 0):.1%}")
        else:
            lines.append("  未检测到明显结节。")
    else:
        lines.append(f"\n结节检测：不可用（{det_result.get('error', '未知错误')}）")

    return "\n".join(lines)


def generate_report(
    cls_result: Dict,
    det_result: Dict,
    kb_results: List[Dict],
    user_query: str = "",
) -> str:
    """
    使用 DeepSeek 生成综合诊断报告。
    """
    client = _create_client()

    # 格式化视觉结果
    visual_text = format_visual_summary(cls_result, det_result)

    # 格式化知识库结果
    kb_text = ""
    if kb_results:
        kb_text = "知识库检索结果：\n"
        for i, r in enumerate(kb_results, 1):
            kb_text += f"\n--- 结果{i} ---\n"
            kb_text += r.get("content", "")
    else:
        kb_text = "知识库未检索到相关疾病信息。"

    # 构建用户消息
    user_msg = f"""## 用户描述
{user_query if user_query else "用户上传了CT影像，请分析。"}

## 视觉分析结果
{visual_text}

## 医学知识库
{kb_text}

请根据以上信息生成一份完整的影像分析报告。"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": REPORT_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        return response.choices[0].message.content or "报告生成失败。"
    except Exception as e:
        return f"报告生成出错：{str(e)}"


def multimodal_analyze(
    image_path: str,
    user_query: str = "",
    model_name: str = "resnet50",
    conf_threshold: float = 0.25,
) -> Dict[str, Any]:
    """
    多模态分析主入口：CT 识别 + 结节检测 + RAG 检索 + 报告生成。

    参数：
        image_path: CT 图片完整路径
        user_query: 用户输入的文字描述（可选）
        model_name: 分类模型（mobilenetv2 / resnet50）
        conf_threshold: 结节检测置信度阈值

    返回：
        {
            "success": bool,
            "visual": { cls_result + det_result },
            "rag_query": str,
            "kb_results": [...],
            "report": str,
        }
    """
    # ===== Step 1: 视觉推理 =====
    cls_result = ct_recognize(image_path, model_name=model_name)
    det_result = ct_detect_nodules(image_path, conf_threshold=conf_threshold)

    if not cls_result.get("success") and not det_result.get("success"):
        return {
            "success": False,
            "error": f"视觉分析失败。分类错误：{cls_result.get('error')}，检测错误：{det_result.get('error')}",
        }

    # ===== Step 2: 构建 RAG 查询 =====
    rag_query = build_rag_query(cls_result, det_result)

    # ===== Step 3: RAG 检索 =====
    KB_AVAILABLE = False
    try:
        from .rag_engine import search_kb
        kb_raw = search_kb(rag_query, top_k=4)
        KB_AVAILABLE = True
    except Exception:
        kb_raw = []

    # 统一 kb_results 格式
    kb_results = []
    if KB_AVAILABLE:
        if kb_raw:
            for r in kb_raw:
                if isinstance(r, dict):
                    kb_results.append(r)
                elif isinstance(r, str):
                    kb_results.append({"content": r, "source": ""})
                else:
                    kb_results.append({"content": str(r), "source": ""})

    # ===== Step 4: 生成报告 =====
    report = generate_report(cls_result, det_result, kb_results, user_query)

    return {
        "success": True,
        "visual": {
            "classification": cls_result,
            "nodule_detection": det_result,
        },
        "rag_query": rag_query,
        "kb_results_count": len(kb_results),
        "report": report,
    }
