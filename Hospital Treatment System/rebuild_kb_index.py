"""
重建 KB 索引（独立版，不需要 Django/MySQL）
扫描 kb/medical_basics/ 下所有 .md 文件，构建 TF-IDF 索引
"""
import os
import re
import pickle
from pathlib import Path
from collections import defaultdict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_DIR = os.path.join(BASE_DIR, 'kb', 'medical_basics')
INDEX_DIR = os.path.join(BASE_DIR, 'chroma_db')
INDEX_PATH = os.path.join(INDEX_DIR, 'kb_index.pkl')

os.makedirs(INDEX_DIR, exist_ok=True)

def chunk_text(text, chunk_size=400, overlap=40):
    """将长文本按段落 + 长度切块。"""
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
    """简单中文预处理"""
    text = re.sub(r'[^\u4e00-\u9fff\w\s，。！？、；：""''（）]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

print(f'📂 扫描知识库目录: {KB_DIR}')
md_files = sorted(Path(KB_DIR).rglob("*.md"))
print(f'   找到 {len(md_files)} 个 .md 文件')

documents = []
for md_file in md_files:
    content = md_file.read_text(encoding='utf-8', errors='ignore')
    filename = md_file.relative_to(KB_DIR).as_posix()
    chunks = chunk_text(content)
    for i, chunk in enumerate(chunks):
        documents.append({
            'id': f"{filename}::chunk_{i}",
            'content': chunk,
            'source': filename,
        })
    print(f'  {filename}: {len(chunks)} 个块')

print(f'\n📊 共 {len(documents)} 个文档块，开始构建 TF-IDF 索引...')

texts = [preprocess_chinese(d['content']) for d in documents]

vectorizer = TfidfVectorizer(
    analyzer='char',
    ngram_range=(2, 4),
    max_features=5000,
    sublinear_tf=True,
)

tfidf_matrix = vectorizer.fit_transform(texts)

data = {
    'documents': documents,
    'vectorizer': vectorizer,
    'matrix': tfidf_matrix,
}

with open(INDEX_PATH, 'wb') as f:
    pickle.dump(data, f)

print(f'✅ 索引已保存: {INDEX_PATH}')
print(f'   文档块数: {len(documents)}')
print(f'   特征数: {tfidf_matrix.shape[1]}')

# 测试检索
print('\n--- 测试检索 ---')
test_queries = ['肺炎', '糖尿病', '肚子疼', '高血压', '骨折']
for q in test_queries:
    query_vec = vectorizer.transform([preprocess_chinese(q)])
    scores = cosine_similarity(query_vec, tfidf_matrix)[0]
    top_idx = np.argsort(scores)[::-1][:3]
    results = []
    for idx in top_idx:
        if scores[idx] > 0:
            results.append(f"{documents[idx]['source']} (score={scores[idx]:.4f})")
    print(f'  "{q}" → {", ".join(results) if results else "未找到"}')
