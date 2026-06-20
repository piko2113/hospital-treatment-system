"""
从旧版索引升级到新版：添加词级 TF-IDF（jieba）
"""
import pickle
import os
import re
import numpy as np
import jieba
from sklearn.feature_extraction.text import TfidfVectorizer

BASE = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE, 'chroma_db', 'kb_index.pkl')

def preprocess_chinese(text):
    text = re.sub(r'[^\u4e00-\u9fff\w\s，。！？、；：""''（）]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def tokenize_with_jieba(text):
    return ' '.join([w for w in jieba.lcut(text) if len(w.strip()) > 0])

print('📂 加载已有索引...')
with open(INDEX_PATH, 'rb') as f:
    old = pickle.load(f)

docs = old['documents']
print(f'文档块数: {len(docs)}')

# 已有 char vectorizer
old_vec = old.get('vectorizer') or old.get('char_vectorizer')
char_matrix = old.get('matrix') or old.get('char_matrix')
print(f'char矩阵: {char_matrix.shape}')

# 构建 word TF-IDF
print('🔨 构建词级 TF-IDF（jieba 分词）...')
texts = [preprocess_chinese(d['content']) for d in docs]
word_texts = [tokenize_with_jieba(t) for t in texts]
word_vectorizer = TfidfVectorizer(
    analyzer='word',
    token_pattern=r'(?u)\b\w+\b',
    max_features=5000,
    sublinear_tf=True,
)
word_matrix = word_vectorizer.fit_transform(word_texts)
print(f'word矩阵: {word_matrix.shape}')

# 保存新格式
data = {
    'documents': docs,
    'char_vectorizer': old_vec,
    'char_matrix': char_matrix,
    'word_vectorizer': word_vectorizer,
    'word_matrix': word_matrix,
}
with open(INDEX_PATH, 'wb') as f:
    pickle.dump(data, f)

size_kb = os.path.getsize(INDEX_PATH) / 1024
print(f'✅ 保存成功: {size_kb:.0f} KB')

# 测试
print('\n--- 测试检索 ---')
HYBRID_WEIGHT_CHAR = 0.4
HYBRID_WEIGHT_WORD = 0.3
HYBRID_WEIGHT_EXPAND = 0.3

MEDICAL_SYNONYMS = {
    '肚子疼': ['腹痛', '肚子痛', '腹部疼痛', '胃疼'],
    '头疼': ['头痛', '头部疼痛', '偏头痛'],
    '发烧': ['发热', '高热', '体温升高'],
    '咳嗽': ['咳', '干咳', '咳痰'],
    '咳血': ['咯血', '咳出血', '痰中带血'],
    '拉肚子': ['腹泻', '拉稀', '水样便'],
    '便秘': ['大便困难', '排便困难', '大便干燥'],
    '恶心': ['想吐', '反胃', '干呕'],
    '头晕': ['眩晕', '头昏', '昏沉'],
    '胸闷': ['胸痛', '胸部不适', '呼吸困难', '气短'],
    '乏力': ['疲劳', '没劲', '无力', '疲倦'],
    '高血压': ['血压高', '高压', '血压升高'],
    '糖尿病': ['血糖高', '高血糖'],
}

def expand_query(query):
    expanded = [query]
    for word, synonyms in MEDICAL_SYNONYMS.items():
        if word in query:
            expanded.extend(synonyms)
    return ' '.join(set(expanded))

from sklearn.metrics.pairwise import cosine_similarity

test_queries = ['肺炎', '糖尿病', '肚子疼', '高血压', '骨折', '咳嗽', '头疼', '胸口闷', '一直发烧', '拉肚子']

for q in test_queries:
    q_char = preprocess_chinese(q)
    q_char_vec = old_vec.transform([q_char])
    char_scores = cosine_similarity(q_char_vec, char_matrix)[0]
    
    word_scores = np.zeros(len(docs))
    q_word = tokenize_with_jieba(q_char)
    try:
        q_word_vec = word_vectorizer.transform([q_word])
        word_scores = cosine_similarity(q_word_vec, word_matrix)[0]
    except:
        pass
    
    expand_scores = np.zeros(len(docs))
    expanded = expand_query(q)
    if expanded != q:
        e_char = preprocess_chinese(expanded)
        e_vec = old_vec.transform([e_char])
        expand_scores = cosine_similarity(e_vec, char_matrix)[0]
    
    def norm(s):
        m = s.max()
        return s / m if m > 0 else s
    
    combined = (HYBRID_WEIGHT_CHAR * norm(char_scores)
                + HYBRID_WEIGHT_WORD * norm(word_scores)
                + HYBRID_WEIGHT_EXPAND * norm(expand_scores))
    
    top_idx = np.argsort(combined)[::-1][:2]
    top_char_idx = np.argsort(char_scores)[::-1][:1]
    
    hybrid_results = [
        f"{docs[idx]['source']} (H={combined[idx]:.3f}, C={char_scores[idx]:.3f})"
        for idx in top_idx if combined[idx] > 0
    ]
    char_result = docs[top_char_idx[0]]['source'] if char_scores[top_char_idx[0]] > 0 else '未找到'
    
    print(f'  "{q}"')
    print(f'    Hybrid: {hybrid_results[0] if hybrid_results else "未找到"}')
    print(f'    纯TF-IDF: {char_result}')
