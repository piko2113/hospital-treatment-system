"""
重写 KB 知识库：按科室分类到子文件夹
然后重建 TF-IDF 索引
"""
import json
import os
import re
import pickle
import shutil
from pathlib import Path
from collections import defaultdict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
RAW_PATH = os.path.join(BASE, 'medical_raw.json')
KB_DIR = os.path.join(BASE, 'kb', 'medical_basics')
INDEX_DIR = os.path.join(BASE, 'chroma_db')
INDEX_PATH = os.path.join(INDEX_DIR, 'kb_index.pkl')

# ── 科室 → 主分类映射 ──────────────────────────────
def get_main_category(departments):
    """根据科室列表判断疾病的主分类"""
    dept_str = ' '.join(departments) if departments else ''
    
    # 按优先级判断
    if any(kw in dept_str for kw in ['儿科', '小儿']):
        return '儿科'
    if any(kw in dept_str for kw in ['妇产', '妇科', '产科', '生殖']):
        return '妇产科'
    if any(kw in dept_str for kw in ['眼科', '耳鼻喉', '口腔', '五官']):
        return '五官科'
    if any(kw in dept_str for kw in ['皮肤', '性病']):
        return '皮肤性病科'
    if any(kw in dept_str for kw in ['精神', '心理', '精神病']):
        return '精神心理科'
    if any(kw in dept_str for kw in ['肿瘤', '癌']):
        return '肿瘤科'
    if any(kw in dept_str for kw in ['急诊', '中毒']):
        return '急诊与中毒'
    if any(kw in dept_str for kw in ['传染', '感染', '结核', '肝病']):
        return '传染感染科'
    if any(kw in dept_str for kw in ['中医', '针灸']):
        return '中医科'
    if any(kw in dept_str for kw in ['骨科', '骨伤']):
        return '骨科'
    if any(kw in dept_str for kw in ['外科', '烧伤', '整形', '泌尿外', '胸外', '神外', '普外']):
        return '外科'
    if any(kw in dept_str for kw in ['内科', '呼吸', '消化', '心内', '心血管', '内分泌', '肾内', '血液', '风湿', '神经内', '免疫']):
        return '内科'
    
    return '其他'

# ── 读取数据 ──────────────────────────────────────
print(f'📖 读取医疗数据...')
size_mb = os.path.getsize(RAW_PATH) / 1024 / 1024

diseases = defaultdict(lambda: {
    'symptom': [], 'check': [], 'drug': [],
    'cure_department': [], 'acompany': [],
    'desc': '', 'cause': '', 'prevent': '', 'category': '',
})

count = 0
with open(RAW_PATH, 'rb') as f:
    buffer = b''
    while True:
        chunk = f.read(65536)
        if not chunk:
            break
        buffer += chunk
        while b'\n' in buffer:
            line, buffer = buffer.split(b'\n', 1)
            line = line.decode('utf-8', errors='ignore').strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except:
                continue
            name = obj.get('name', '')
            if not name:
                continue
            d = diseases[name]
            if not d['desc'] and obj.get('desc'):
                d['desc'] = obj.get('desc')
            if not d['cause'] and obj.get('cause'):
                d['cause'] = obj.get('cause')
            if not d['prevent'] and obj.get('prevent'):
                d['prevent'] = obj.get('prevent')
            if not d['category'] and obj.get('category'):
                d['category'] = obj.get('category')
            if obj.get('symptom'):
                s = obj['symptom']
                d['symptom'].extend(s if isinstance(s, list) else [s])
            if obj.get('check'):
                c = obj['check']
                d['check'].extend(c if isinstance(c, list) else [c])
            if obj.get('drug'):
                drug = obj['drug']
                d['drug'].extend(drug if isinstance(drug, list) else [drug])
            if obj.get('recommand_drug'):
                rd = obj['recommand_drug']
                d['drug'].extend(rd if isinstance(rd, list) else [rd])
            if obj.get('cure_department'):
                dept = obj['cure_department']
                d['cure_department'].extend(dept if isinstance(dept, list) else [dept])
            if obj.get('acompany'):
                ac = obj['acompany']
                d['acompany'].extend(ac if isinstance(ac, list) else [ac])
            count += 1
            if count % 5000 == 0:
                print(f'  已处理 {count} 条...')

print(f'📄 共 {count} 条记录 → {len(diseases)} 种疾病')

# ── 按分类分组 ──────────────────────────────────────
categories = defaultdict(list)  # category -> [(disease_name, info)]
for name, info in diseases.items():
    cat = get_main_category(info['cure_department'])
    categories[cat].append((name, info))

# 打印分类统计
print(f'\n📊 分类统计:')
for cat in sorted(categories.keys()):
    print(f'  {cat}: {len(categories[cat])} 种疾病')

# ── 删除旧的自动生成文件（保留 5 个手动文件） ─────
print(f'\n🧹 清理旧文件...')
manual_files = {'肺炎简介.md', '医院科室介绍.md', '就医导诊指南.md', '常用药品知识.md', '常见疾病知识.md'}
for old_file in Path(KB_DIR).rglob('疾病知识_*.md'):
    old_file.unlink()
    print(f'  ✂ 删除: {old_file.name}')

# ── 写入新文件 ──────────────────────────────────────
print(f'\n📝 写入分类知识库...')
total_diseases = 0
cat_order = ['内科', '外科', '骨科', '儿科', '妇产科', '五官科', '皮肤性病科',
             '肿瘤科', '精神心理科', '传染感染科', '急诊与中毒', '中医科', '其他']

for cat in cat_order:
    if cat not in categories:
        continue
    items = sorted(categories[cat], key=lambda x: x[0])  # 按疾病名排序
    cat_dir = os.path.join(KB_DIR, cat)
    os.makedirs(cat_dir, exist_ok=True)
    
    file_idx = 0
    for i in range(0, len(items), 20):
        batch = items[i:i+20]
        filename = f'{cat}{file_idx}.md'
        filepath = os.path.join(cat_dir, filename)
        
        content_lines = []
        for n, info in batch:
            content_lines.append(f'# {n}')
            if info['desc']:
                content_lines.append(f'\n## 简介\n{info["desc"][:500]}')
            s = list(set(info['symptom']))
            if s:
                s = [x for x in s if len(x) <= 8]
                content_lines.append(f'\n## 症状\n- {"、".join(s[:12])}')
            c = list(set(info['check']))
            if c:
                content_lines.append(f'\n## 检查\n- {"、".join(c[:10])}')
            d = list(set(info['drug']))
            if d:
                content_lines.append(f'\n## 常用药品\n- {"、".join(d[:8])}')
            dept = list(set(info['cure_department']))
            if dept:
                content_lines.append(f'\n## 就诊科室\n- {dept[0]}')
            ac = list(set(info['acompany']))
            if ac:
                content_lines.append(f'\n## 并发症\n- {"、".join(ac[:5])}')
            if info['prevent']:
                content_lines.append(f'\n## 预防\n{info["prevent"][:300]}')
            content_lines.append('')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content_lines))
        total_diseases += len(batch)
        file_idx += 1
    
    print(f'  📁 {cat}/ → {file_idx} 个文件, {len(items)} 种疾病')

print(f'\n✅ 分类完成！共 {total_diseases} 种疾病')

# ── 重建 TF-IDF 索引 ──────────────────────────────
print(f'\n🔨 重建 TF-IDF 索引...')

def chunk_text(text, chunk_size=400, overlap=40):
    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) < chunk_size:
            current += para + "\n"
        else:
            if current:
                chunks.append(current.strip())
            current = para + "\n"
    if current:
        chunks.append(current.strip())
    if not chunks:
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i:i + chunk_size].strip()
            if chunk:
                chunks.append(chunk)
    return chunks

def preprocess_chinese(text):
    text = re.sub(r'[^\u4e00-\u9fff\w\s，。！？、；：""''（）]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

md_files = sorted(Path(KB_DIR).rglob("*.md"))
print(f'   扫描到 {len(md_files)} 个 .md 文件')

documents = []
for md_file in md_files:
    content = md_file.read_text(encoding='utf-8', errors='ignore')
    # 用相对路径做 source，保留文件夹结构
    rel_path = md_file.relative_to(KB_DIR).as_posix()
    chunks = chunk_text(content)
    for i, chunk in enumerate(chunks):
        documents.append({
            'id': f"{rel_path}::chunk_{i}",
            'content': chunk,
            'source': rel_path,
        })

print(f'   共 {len(documents)} 个文档块')

texts = [preprocess_chinese(d['content']) for d in documents]
vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2, 4), max_features=5000, sublinear_tf=True)
tfidf_matrix = vectorizer.fit_transform(texts)

os.makedirs(INDEX_DIR, exist_ok=True)
with open(INDEX_PATH, 'wb') as f:
    pickle.dump({'documents': documents, 'vectorizer': vectorizer, 'matrix': tfidf_matrix}, f)

print(f'✅ 索引已保存: {INDEX_PATH} ({len(documents)} 块, {tfidf_matrix.shape[1]} 特征)')

# 测试检索
print(f'\n--- 测试检索 ---')
test_queries = ['肺炎', '糖尿病', '肚子疼', '高血压', '骨折', '咳嗽', '头疼']
for q in test_queries:
    query_vec = vectorizer.transform([preprocess_chinese(q)])
    scores = cosine_similarity(query_vec, tfidf_matrix)[0]
    top_idx = np.argsort(scores)[::-1][:3]
    results = []
    for idx in top_idx:
        if scores[idx] > 0.05:
            results.append(f"{documents[idx]['source']} (score={scores[idx]:.4f})")
    print(f'  "{q}" → {", ".join(results[:2]) if results else "未找到"}')
