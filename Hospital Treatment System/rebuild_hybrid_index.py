"""
重建知识库索引（混合检索：字符TF-IDF + 词级TF-IDF + 同义词扩展）
独立运行，不需要 Django/MySQL
"""
import os
import re
import pickle
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import jieba

BASE = os.path.dirname(os.path.abspath(__file__))
KB_DIR = os.path.join(BASE, 'kb', 'medical_basics')
INDEX_DIR = os.path.join(BASE, 'chroma_db')
INDEX_PATH = os.path.join(INDEX_DIR, 'kb_index.pkl')

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

def tokenize_with_jieba(text):
    words = jieba.lcut(text)
    words = [w for w in words if len(w.strip()) > 0]
    return ' '.join(words)

# 1. 扫描 .md 文件
print(f'📂 扫描知识库: {KB_DIR}')
md_files = sorted(Path(KB_DIR).rglob("*.md"))
print(f'   找到 {len(md_files)} 个 .md 文件')

documents = []
for md_file in md_files:
    content = md_file.read_text(encoding='utf-8', errors='ignore')
    rel_path = md_file.relative_to(KB_DIR).as_posix()
    chunks = chunk_text(content)
    for i, chunk in enumerate(chunks):
        documents.append({
            'id': f"{rel_path}::chunk_{i}",
            'content': chunk,
            'source': rel_path,
        })
print(f'📊 共 {len(documents)} 个文档块')

# 2. 构建字符级 TF-IDF
print('🔨 字符级 TF-IDF（精准匹配）...')
texts = [preprocess_chinese(d['content']) for d in documents]
char_vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2, 4), max_features=5000, sublinear_tf=True)
char_matrix = char_vectorizer.fit_transform(texts)
print(f'   特征数: {char_matrix.shape[1]}')

# 2. 构建词级 TF-IDF（jieba）
print('🔨 词级 TF-IDF（jieba 分词）...')
word_texts = [tokenize_with_jieba(t) for t in texts]
word_vectorizer = TfidfVectorizer(analyzer='word', token_pattern=r'(?u)\b\w+\b', max_features=5000, sublinear_tf=True)
word_matrix = word_vectorizer.fit_transform(word_texts)
print(f'   特征数: {word_matrix.shape[1]}')

# 3. 保存
data = {
    'documents': documents,
    'char_vectorizer': char_vectorizer,
    'char_matrix': char_matrix,
    'word_vectorizer': word_vectorizer,
    'word_matrix': word_matrix,
}

os.makedirs(INDEX_DIR, exist_ok=True)
with open(INDEX_PATH, 'wb') as f:
    pickle.dump(data, f)

file_size_mb = os.path.getsize(INDEX_PATH) / 1024 / 1024
print(f'✅ 索引已保存: {INDEX_PATH} ({file_size_mb:.1f} MB)')

# 4. 测试混合检索（复用 rag_engine 的逻辑）
print('\n--- 混合检索测试 ---')

HYBRID_WEIGHT_CHAR = 0.4
HYBRID_WEIGHT_WORD = 0.3
HYBRID_WEIGHT_EXPAND = 0.3

MEDICAL_SYNONYMS = {
    '肚子疼': ['腹痛', '肚子痛', '腹部疼痛', '胃疼'],
    '头疼': ['头痛', '头部疼痛', '偏头痛'],
    '发烧': ['发热', '高热', '体温升高'],
    '咳嗽': ['咳', '干咳', '咳痰'],
    '咳血': ['咯血', '咳出血', '痰中带血'],
    '流鼻涕': ['流涕', '鼻塞', '鼻炎', '鼻漏'],
    '拉肚子': ['腹泻', '拉稀', '水样便'],
    '便秘': ['大便困难', '排便困难', '大便干燥'],
    '恶心': ['想吐', '反胃', '干呕'],
    '头晕': ['眩晕', '头昏', '昏沉'],
    '胸闷': ['胸痛', '胸部不适', '呼吸困难', '气短'],
    '乏力': ['疲劳', '没劲', '无力', '疲倦'],
    '腰疼': ['腰痛', '腰部疼痛', '腰酸'],
    '关节疼': ['关节痛', '关节疼痛'],
    '皮疹': ['红疹', '出疹子', '皮肤红点'],
    '失眠': ['睡不着', '入睡困难'],
    '高血压': ['血压高', '高压', '血压升高'],
    '糖尿病': ['血糖高', '高血糖'],
}

def expand_query(query):
    expanded = [query]
    for word, synonyms in MEDICAL_SYNONYMS.items():
        if word in query:
            expanded.extend(synonyms)
        else:
            for syn in synonyms:
                if syn in query:
                    expanded.append(word)
                    break
    return ' '.join(set(expanded))

def norm(s):
    m = s.max()
    return s / m if m > 0 else s

test_queries = ['肺炎', '糖尿病', '肚子疼', '高血压', '骨折', '咳嗽', '头疼', '胸口闷', '一直发烧', '拉肚子']

for q in test_queries:
    # Char TF-IDF
    q_char = preprocess_chinese(q)
    q_char_vec = char_vectorizer.transform([q_char])
    char_scores = cosine_similarity(q_char_vec, char_matrix)[0]
    
    # Word TF-IDF
    word_scores = np.zeros(len(documents))
    q_word = tokenize_with_jieba(q_char)
    try:
        q_word_vec = word_vectorizer.transform([q_word])
        word_scores = cosine_similarity(q_word_vec, word_matrix)[0]
    except:
        pass
    
    # 同义词扩展
    expand_scores = np.zeros(len(documents))
    expanded = expand_query(q)
    if expanded != q:
        e_char = preprocess_chinese(expanded)
        e_vec = char_vectorizer.transform([e_char])
        expand_scores = cosine_similarity(e_vec, char_matrix)[0]
    
    # 融合
    combined = (HYBRID_WEIGHT_CHAR * norm(char_scores)
                + HYBRID_WEIGHT_WORD * norm(word_scores)
                + HYBRID_WEIGHT_EXPAND * norm(expand_scores))
    
    top_idx = np.argsort(combined)[::-1][:2]
    
    # 纯 char 对比
    top_char_idx = np.argsort(char_scores)[::-1][:1]
    
    hybrid_results = []
    for idx in top_idx:
        if combined[idx] > 0:
            hybrid_results.append(
                f"{documents[idx]['source']} (H={combined[idx]:.3f}, C={char_scores[idx]:.3f})"
            )
    
    char_result = documents[top_char_idx[0]]['source'] if char_scores[top_char_idx[0]] > 0 else '未找到'
    
    print(f'  "{q}"')
    print(f'    Hybrid: {hybrid_results[0] if hybrid_results else "未找到"}')
    print(f'    纯TF-IDF: {char_result}')
