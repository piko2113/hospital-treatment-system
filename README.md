# 🏥 医院就诊影像分析系统

> **AI 赋能的智能医疗辅助平台** — 深度学习影像识别 + YOLOv8 肺结节检测 + RAG 知识库 + Function Calling Agent + 多模态诊断报告

一个集成了 **CT 影像分类、肺结节目标检测、AI 智能问诊、医学知识库检索**的全栈 Django Web 项目。用户上传肺部 CT 即可获得 AI 分析，还能与 Agent 对话咨询症状、检索医学知识。

---

## ✨ 功能总览

| 模块 | 功能 | 技术 |
|------|------|------|
| 🖼️ **CT 影像识别** | 上传 CT → AI 判断疑似肺炎/正常（二分类） | MobileNetV2 / ResNet50 / 集成预测 |
| 🫁 **肺结节检测** | YOLOv8 目标检测，可视化结节位置与置信度 | YOLOv8n + Python NMS |
| 🤖 **AI 医疗助手** | 基于 DeepSeek API 的智能问诊（Function Calling + ReAct） | DeepSeek Chat + 工具注册 |
| 🧪 **多模态诊断** | CT 识别 + 结节检测 + RAG 检索 → LLM 生成综合报告 | 一站式 Pipeline |
| 📚 **RAG 知识库** | 428 个 .md 文档，8358 种疾病，12 科室分类，混合检索 | 字符 TF-IDF + jieba 词级 + 同义词 |
| 👥 **用户系统** | 注册 / 登录 / 个人信息 | Django Auth + 自定义认证 |
| 💬 **论坛社区** | 发布文章、话题分类、评论 | Django ORM |
| 📊 **数据看板** | 识别统计、饼图（肺炎占比）、7 天趋势柱状图 | Chart.js |
| 🔧 **后台管理** | 用户、文章、评论、识别记录管理 | Django Admin + SimpleUI |

---

## 🧠 核心技术栈

### 后端
- **Django 3.2** (Python 3.9)
- **MySQL 8.0** 数据库
- **Django Session** 用户对话隔离

### 深度学习 / AI
| 模型 | 框架 | 输入 | 用途 |
|------|------|------|------|
| **MobileNetV2** | TensorFlow/Keras | 224×224 | 轻量快速分类 |
| **ResNet50** | TensorFlow/Keras | 224×224 | 高精度分类（两阶段训练） |
| **Ensemble（加权平均）** | — | 224×224 | MobileNetV2(0.4) + ResNet50(0.6) |
| **YOLOv8n** | PyTorch + ONNX | 512×512 | 肺结节目标检测（231 个结节标注） |

### LLM / Agent
- **DeepSeek Chat API** — 自然语言推理 + 医疗问答
- **Function Calling** — 4 个注册工具（CT 识别、结节检测、知识库搜索、论坛搜索）
- **ReAct 循环** — Agent 自动选择工具、组合调用、生成回答
- **多模态 Pipeline** — 视觉推理 → RAG 检索 → DeepSeek 综合报告

### RAG 知识引擎
- 数据源：医学知识库，按 12 个科室分类，8358 种疾病
- 混合检索权重：字符 TF-IDF(0.4) + jieba 词级 TF-IDF(0.3) + 同义词扩展(0.3)
- 存储格式：428 个 Markdown 文件（`kb/medical_basics/`）

### 前端
- **Django Templates** + **Amaze UI**（响应式）
- **Chart.js** — 数据可视化（饼图 + 柱状图）
- **毛玻璃导航**、拖拽上传、绿色渐变主题

---

## 🏗️ 项目结构

```
Hospital Treatment System/          ← 项目根目录（嵌套）
├── secondweb/                      ← Django 项目配置
│   ├── settings.py                 ─ 配置（数据库、静/动态文件、App 注册）
│   └── urls.py                     ─ URL 路由
│
├── home/                           ─ 核心 App（用户/论坛/识别）
│   ├── views.py                    ─ 全部页面视图（首页/登录/注册/识别/上传）
│   ├── models.py                   ─ User_info / Topic / Article / Comment / Recognition
│   ├── recognition_model.py        ─ TensorFlow 模型管理（MobileNetV2 / ResNet50 / Ensemble）
│   ├── auth_backend.py             ─ 自定义认证后端
│   └── templatetags/               ─ 自定义模板标签
│
├── agent_chat/                     ─ AI 助手 App（2026-06 新增）
│   ├── views.py                    ─ 聊天页面 & API（chat, ct, multimodal, history）
│   ├── urls.py                     ─ 路由（/chat, /chat/api/, /chat/api/multimodal/ 等）
│   ├── agent.py                    ─ ReAct Agent（Function Calling + 多 session 隔离）
│   ├── tools.py                    ─ 工具注册表（ct_recognize, search_knowledge, ct_detect_nodules, search_forum）
│   ├── multimodal_agent.py         ─ 多模态诊断 Pipeline（全新，2026-06-21）
│   ├── rag_engine.py               ─ RAG 混合检索引擎
│   ├── models.py                   ─ ChatHistory（对话历史）
│   └── templates/
│       └── chat.html               ─ 聊天界面（消息气泡 + CT 上传 + 多模态按钮）
│
├── yolo_detection/                 ─ YOLOv8 肺结节检测模块
│   ├── detect.py                   ─ LungNoduleDetector 推理类
│   ├── train_yolo.py               ─ YOLOv8 训练脚本
│   ├── yolov8n.pt                  ─ 预训练权重
│   └── runs/yolov8n_nodule/        ─ 训练结果（权重 + 指标图 + 混淆矩阵）
│
├── kb/                             ─ 医学知识库
│   └── medical_basics/             ─ 428 个 .md 文件（12 科室分类）
│
├── static/                         ─ 静态文件（CSS/JS/图片）
├── templates/                      ─ 全局模板
│   ├── base.html                   ─ 基础布局（毛玻璃导航 + 绿色渐变）
│   ├── index.html                  ─ 首页（文章列表 + 数据看板）
│   ├── recognition.html            ─ CT 识别页（拖拽上传 + 模型选择 + 阈值滑块）
│   ├── login.html                  ─ 登录
│   ├── register.html               ─ 注册
│   ├── detail.html                 ─ 文章详情
│   ├── post.html                   ─ 发布文章
│   └── topics.html                 ─ 话题分类页
│
├── userimg/upload/recognition/     ─ 上传 CT 图片存储
├── chroma_db/                      ─ ChromaDB 持久化（实验中）
│
├── datasets/                       ─ YOLO 训练数据集
├── output_pic/                     ─ 训练输出图片
├── train_photos/ / test_photos/    ─ 训练/测试图片集
│
├── manage.py                       ─ Django 管理入口
├── train.py                        ─ MobileNetV2 训练脚本
├── train_restnet.py                ─ ResNet50 训练脚本
└── build_kb.py                     ─ 知识库构建
```

---

## 🚀 快速开始

### 环境要求
- **Python 3.8+**
- **MySQL 8.0**（含数据库 `lung_recognition`）
- 环境变量：`DEEPSEEK_API_KEY` / `DB_PASSWORD` / `DJANGO_SECRET_KEY`

### 1️⃣ 配置环境变量

需要设置以下系统环境变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | **必填** |
| `DJANGO_SECRET_KEY` | Django 密钥 | **必填**（任意长随机字符串） |
| `DB_PASSWORD` | MySQL 密码 | **必填** |
| `DB_NAME` | 数据库名 | `lung_recognition` |
| `DB_USER` | 数据库用户 | `root` |
| `DB_HOST` | 数据库地址 | `127.0.0.1` |
| `DB_PORT` | 数据库端口 | `3306` |
| `DJANGO_DEBUG` | 调试模式 | `False`（设为 `True` 开发用） |
| `OPENAI_PROXY` | API 代理地址 | 可选（如 `http://127.0.0.1:7897`） |

### 2️⃣ 运行

```bash
cd "Hospital Treatment System\Hospital Treatment System"

# 数据库迁移
python manage.py migrate

# 构建知识库索引（首次运行）
python build_kb.py

# 启动服务
python manage.py runserver
```

访问 `http://127.0.0.1:8000`

### 3️⃣ 模型训练

```bash
# MobileNetV2 分类模型
python train.py

# ResNet50 分类模型
python train_restnet.py

# YOLOv8 肺结节检测
python yolo_detection/train_yolo.py
```

---

## 🌐 API 接口

### Agent Chat
| 端点 | 方法 | 说明 |
|------|------|------|
| `/chat/` | GET | AI 助手对话页面 |
| `/chat/api/` | POST | 对话 API（`message` + `action` 参数） |
| `/chat/api/ct/` | POST | CT 图片识别（上传 → 分类 + 结节检测） |
| `/chat/api/multimodal/` | POST | 多模态诊断（上传 → 识别 → RAG → 报告） |
| `/chat/api/kb-status/` | GET | 知识库状态检查 |
| `/chat/api/history/` | GET | 最近 3 条对话历史 |

### 核心页面
| 端点 | 说明 |
|------|------|
| `/` | 首页（文章列表 + 数据看板） |
| `/recognition` | CT 影像识别 |
| `/upload` | 图片上传 + 识别 API |
| `/register` / `/login` | 用户注册/登录 |
| `/article/<id>` | 文章详情 |
| `/post` | 发布文章 |
| `/admin/` | 后台管理 |

---

## 🤖 AI 助手使用指南

### 对话模式
在 `/chat` 页面，你可以：
- **问症状**：`"发烧咳嗽挂什么科"` → 检索知识库回答
- **查疾病**：`"什么是肺炎"` → 检索知识库 + LLM 总结
- **CT 分析**：上传图片 → 自动识别 + 结节检测
- **多模态**：上传图片 + 输入症状描述 → 一站式报告

### 工具（Agent 可自动调用）
| 工具 | 功能 |
|------|------|
| `ct_recognize` | CT 影像二分类（疑似肺炎 / 正常） |
| `ct_detect_nodules` | YOLOv8 肺结节检测（位置 + 置信度） |
| `search_knowledge` | 医学知识库检索 |
| `search_forum` | 论坛文章搜索 |

### 多模态 Pipeline
```
用户上传 CT 图片
  → Step 1: ResNet50/YOLOv8 视觉分析
  → Step 2: 视觉结果 → 自然语言查询
  → Step 3: RAG 检索知识库
  → Step 4: DeepSeek 生成综合诊断报告
  → 返回结构化结果
```

---

## 📈 模型性能

| 模型 | 准确率 | 特点 |
|------|--------|------|
| MobileNetV2 | ~87% | 轻量，适合快速初筛 |
| ResNet50 | ~92% | 高精度，两阶段训练（冻结 → 微调） |
| Ensemble（加权平均） | ~93% | MobileNetV2(0.4) + ResNet50(0.6) |
| YOLOv8n | — | 221 训练图 / 10 验证图，Python NMS |

训练策略：两阶段微调 + EarlyStopping + Dropout(0.3) + 数据增强（旋转/翻转/缩放）

---

## 🛠️ 已知问题

- **torch 环境**：Windows 上 `import torch` 挂起，YOLOv8 推理改用纯 Python NMS（`fix_nms.py`）
- **安全短板**：CSRF 豁免、`ALLOWED_HOSTS=['*']`、MD5 密码（已部分修复 → 密码哈希）
- **首页文章**：内容为空（仅 2 条占位）

## 🎯 后续方向

- [ ] PyTorch 重写分类模型（需先解决 torch 环境）
- [ ] 热力图 / 分割图可视化
- [ ] 肺炎多分类（扩充公开数据集）
- [ ] 安全加固（CSRF 保护、Session 安全）
- [ ] 深色模式 & 移动端适配
- [ ] 移动端 PWA 支持

---

## 📄 许可证

本项目仅供学习研究使用。

## 👤 作者

**Piko** — [GitHub](https://github.com/piko2113)

---

> ⚠️ **免责声明**：本项目为个人学习项目，AI 诊断结果仅供参考，不构成医疗建议。如有身体不适，请及时就医。
