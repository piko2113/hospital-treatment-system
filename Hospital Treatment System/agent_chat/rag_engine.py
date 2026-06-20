"""
RAG 引擎：知识库构建 + 混合检索（Hybrid Search）
TF-IDF 字符级（精准） + TF-IDF 词级（jieba 分词） + 同义词扩展
无需 torch / 神经网络，纯 sklearn + jieba 实现
"""

import os
import re
import pickle
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import jieba


# ── 配置 ──────────────────────────────────────────────

# 混合权重
HYBRID_WEIGHT_CHAR = 0.4    # 字符级 TF-IDF（精准匹配）
HYBRID_WEIGHT_WORD = 0.3    # 词级 TF-IDF（jieba 分词理解）
HYBRID_WEIGHT_EXPAND = 0.3  # 同义词扩展（语义兜底）

# ── 医学同义词词典 ──────────────────────────────────

MEDICAL_SYNONYMS = {
    # 症状
    '肚子疼': ['腹痛', '肚子痛', '腹部疼痛', '胃疼', '胃痛'],
    '头疼': ['头痛', '头部疼痛', '偏头痛', '脑壳疼'],
    '发烧': ['发热', '高热', '低温', '体温升高'],
    '咳嗽': ['咳', '干咳', '咳痰', '阵咳'],
    '咳血': ['咯血', '咳出血', '痰中带血'],
    '流鼻涕': ['流涕', '鼻塞', '鼻炎', '鼻漏'],
    '拉肚子': ['腹泻', '拉稀', '水样便', '稀便'],
    '便秘': ['大便困难', '排便困难', '大便干燥', '大便不通'],
    '恶心': ['想吐', '反胃', '干呕', '呕吐'],
    '头晕': ['眩晕', '天旋地转', '头昏', '昏沉'],
    '胸闷': ['胸痛', '胸部不适', '胸口疼', '呼吸困难', '气短'],
    '乏力': ['疲劳', '没劲', '无力', '疲倦', '困倦'],
    '腰疼': ['腰痛', '腰部疼痛', '腰酸', '腰肌劳损'],
    '关节疼': ['关节痛', '关节疼痛', '关节肿', '关节炎'],
    '皮疹': ['红疹', '出疹子', '皮肤红点', '斑丘疹'],
    '失眠': ['睡不着', '入睡困难', '早醒', '睡眠差'],
    '消瘦': ['变瘦', '体重下降', '体重减轻', '暴瘦'],
    '水肿': ['浮肿', '肿胀', '肿', '水泡'],
    '心悸': ['心慌', '心跳加速', '心跳快', '心律不齐'],
    # 检查
    'CT': ['ct检查', '计算机断层扫描', '胸部ct'],
    '血常规': ['血检', '血液检查', '查血', '血象'],
    '心电图': ['心电', 'ecg', '心脏检查'],
    'B超': ['超声', '彩超', 'b超检查', '超声波'],
    '胃镜': ['胃镜检查', '消化道内镜'],
    # 常见简称
    '高血压': ['血压高', '高压', '血压升高', '高血压病'],
    '糖尿病': ['血糖高', '高血糖', '消渴'],
    '冠心病': ['冠状动脉硬化', '心脏病', '心肌缺血'],
    '肺炎': ['肺部感染', '肺部炎症', '肺感染'],
    '乙肝': ['乙型肝炎', '乙肝病毒', '肝炎'],
    '感冒': ['上呼吸道感染', '伤风', '着凉'],
    '慢阻肺': ['copd', '慢性阻塞性肺疾病'],
    '艾滋病': ['hiv', '获得性免疫缺陷综合征'],
    '中风': ['脑卒中', '脑梗', '脑梗死', '脑出血'],
}


def expand_query(query: str) -> str:
    """扩展查询：加入同义词，扩大召回。"""
    expanded = [query]
    for word, synonyms in MEDICAL_SYNONYMS.items():
        if word in query:
            expanded.extend(synonyms)
        else:
            # 如果同义词出现在查询中，补充原词
            for syn in synonyms:
                if syn in query:
                    expanded.append(word)
                    break
    return ' '.join(set(expanded))


# ── 文档分块 ──────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 40) -> List[str]:
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


def preprocess_chinese(text: str) -> str:
    """保留中文字符、英文字母、数字和常用标点。"""
    text = re.sub(r'[^\u4e00-\u9fff\w\s，。！？、；：""''（）]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def tokenize_with_jieba(text: str) -> str:
    """用 jieba 分词，空格分隔。"""
    words = jieba.lcut(text)
    # 去掉单字符词（标点等）
    words = [w for w in words if len(w.strip()) > 0]
    return ' '.join(words)


# ── 知识库管理器 ──────────────────────────────────────

class LocalKnowledgeBase:
    """
    本地知识库，Hybrid Search：
    字符级 TF-IDF + 词级 TF-IDF (jieba) + 同义词扩展
    """

    def __init__(self, persist_dir: str = None):
        if persist_dir is None:
            from django.conf import settings
            persist_dir = getattr(settings, 'AGENT_CHAT_PERSIST_DIR', './kb_index')

        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.persist_dir / 'kb_index.pkl'

        # 文档存储
        self.documents: List[Dict] = []

        # 字符级 TF-IDF（原方案）
        self.char_vectorizer = TfidfVectorizer(
            analyzer='char',
            ngram_range=(2, 4),
            max_features=5000,
            sublinear_tf=True,
        )

        # 词级 TF-IDF（jieba 分词）
        self.word_vectorizer = TfidfVectorizer(
            analyzer='word',
            token_pattern=r'(?u)\b\w+\b',
            max_features=5000,
            sublinear_tf=True,
        )

        self._fitted = False
        self._char_matrix = None
        self._word_matrix = None

        # 加载已有索引
        self._load()

    def _load(self):
        if self.index_path.exists():
            try:
                with open(self.index_path, 'rb') as f:
                    data = pickle.load(f)
                self.documents = data['documents']
                self.char_vectorizer = data['char_vectorizer']
                self._char_matrix = data['char_matrix']
                self._fitted = True

                # 兼容旧版（没有 word 索引的，回退到纯 char）
                self.word_vectorizer = data.get('word_vectorizer', self.word_vectorizer)
                self._word_matrix = data.get('word_matrix', None)
            except Exception:
                pass

    def _save(self):
        data = {
            'documents': self.documents,
            'char_vectorizer': self.char_vectorizer,
            'char_matrix': self._char_matrix,
            'word_vectorizer': self.word_vectorizer,
            'word_matrix': self._word_matrix,
        }
        with open(self.index_path, 'wb') as f:
            pickle.dump(data, f)

    def add_documents(self, docs: List[Dict]):
        self.documents.extend(docs)
        self._rebuild_index()

    def _rebuild_index(self):
        """重建 TF-IDF 索引（字符级 + 词级）。"""
        if not self.documents:
            return

        texts = [preprocess_chinese(d['content']) for d in self.documents]

        # 字符级
        self._char_matrix = self.char_vectorizer.fit_transform(texts)

        # 词级（jieba 分词）
        word_texts = [tokenize_with_jieba(t) for t in texts]
        self._word_matrix = self.word_vectorizer.fit_transform(word_texts)

        self._fitted = True
        self._save()

    def search(self, query: str, top_k: int = 4) -> List[Dict]:
        """
        混合检索：字符级 + 词级 + 同义词扩展
        """
        if not self._fitted or not self.documents:
            return []

        # ── 1. 字符级 TF-IDF ──
        query_clean = preprocess_chinese(query)
        query_char_vec = self.char_vectorizer.transform([query_clean])
        char_scores = cosine_similarity(query_char_vec, self._char_matrix)[0]

        # ── 2. 词级 TF-IDF（jieba） ──
        word_scores = np.zeros(len(self.documents))
        if self._word_matrix is not None:
            query_word = tokenize_with_jieba(query_clean)
            try:
                query_word_vec = self.word_vectorizer.transform([query_word])
                word_scores = cosine_similarity(query_word_vec, self._word_matrix)[0]
            except Exception:
                pass

        # ── 3. 同义词扩展检索 ──
        expand_scores = np.zeros(len(self.documents))
        expanded = expand_query(query)
        if expanded != query:
            expand_clean = preprocess_chinese(expanded)
            expand_vec = self.char_vectorizer.transform([expand_clean])
            expand_scores = cosine_similarity(expand_vec, self._char_matrix)[0]

        # ── 4. 融合评分 ──
        # 归一化
        def norm(s):
            m = s.max()
            return s / m if m > 0 else s

        char_norm = norm(char_scores)
        word_norm = norm(word_scores)
        expand_norm = norm(expand_scores)

        combined = (
            HYBRID_WEIGHT_CHAR * char_norm
            + HYBRID_WEIGHT_WORD * word_norm
            + HYBRID_WEIGHT_EXPAND * expand_norm
        )

        # ── 5. 取 top_k ──
        top_indices = np.argsort(combined)[::-1][:top_k]
        results = []
        for idx in top_indices:
            if combined[idx] > 0:
                results.append({
                    'content': self.documents[idx]['content'],
                    'source': self.documents[idx].get('source', '未知来源'),
                    'score': round(float(combined[idx]), 4),
                    '_char': round(float(char_scores[idx]), 4),
                    '_word': round(float(word_scores[idx]), 4),
                    '_expand': round(float(expand_scores[idx]), 4),
                })
        return results

    def count(self) -> int:
        return len(self.documents)


# ── Embedding 检索器（OpenAI API） ──────────────────

EMBEDDING_MODEL = 'text-embedding-v2'
EMBEDDING_DIM = 1536
EMBEDDING_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'

# 代理（如 Clash）
EMBEDDING_PROXY = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy') or None

# 融合权重：Embedding 语义 + TF-IDF 精确
HYBRID_EMBEDDING_WEIGHT = 0.5
HYBRID_TFIDF_WEIGHT = 0.5


class EmbeddingRetriever:
    """
    基于 OpenAI Embedding API 的语义检索器。
    将文档块编码为向量并缓存本地，运行时不需要 torch。
    """

    def __init__(self, persist_dir: str = None):
        if persist_dir is None:
            from django.conf import settings
            persist_dir = getattr(settings, 'AGENT_CHAT_PERSIST_DIR', './kb_index')

        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.persist_dir / 'embeddings_cache.pkl'

        self.doc_ids: List[str] = []
        self.vectors: np.ndarray = None  # (n_docs, 1536)
        self._client = None

        self._load_cache()

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            # 优先用 DASHSCOPE_API_KEY，若没有则尝试 OPENAI_API_KEY
            api_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("未设置 DASHSCOPE_API_KEY 或 OPENAI_API_KEY")
            kwargs = {
                'api_key': api_key,
                'base_url': EMBEDDING_BASE_URL,
            }
            if EMBEDDING_PROXY:
                import httpx
                kwargs['http_client'] = httpx.Client(proxy=EMBEDDING_PROXY)
            self._client = OpenAI(**kwargs)
        return self._client


    def _load_cache(self):
        """从磁盘加载缓存的 Embedding。"""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'rb') as f:
                    data = pickle.load(f)
                self.doc_ids = data['doc_ids']
                self.vectors = data['vectors']
                print(f"✅ 加载 {len(self.doc_ids)} 条 Embedding 缓存")
            except Exception as e:
                print(f"⚠️ Embedding 缓存加载失败: {e}")
                self.doc_ids = []
                self.vectors = None

    def _save_cache(self):
        """持久化 Embedding 到磁盘。"""
        data = {
            'doc_ids': self.doc_ids,
            'vectors': self.vectors,
        }
        with open(self.cache_path, 'wb') as f:
            pickle.dump(data, f)
        print(f"✅ Embedding 缓存已保存 ({len(self.doc_ids)} 条)")

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """调用 OpenAI API 获取一批文本的 Embedding 向量。"""
        client = self._get_client()
        all_embeddings = []
        batch_size = 25  # DashScope 限制 max=25
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                resp = client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=batch,
                    timeout=30,
                )
                ordered = [None] * len(batch)
                for item in resp.data:
                    ordered[item.index] = item.embedding
                for emb in ordered:
                    if emb is not None:
                        all_embeddings.append(emb)
            except Exception as e:
                print(f"⚠️ OpenAI API 调用失败: {e}")
                print("⚠️ Embedding 功能不可用，将使用 TF-IDF 纯文本检索")
                # 返回空数组触发降级
                return np.array([])
        return np.array(all_embeddings, dtype=np.float32)

    def build_index(self, documents: List[Dict]):
        """基于文档列表重建 Embedding 索引。

        documents: [{'id': str, 'content': str, ...}, ...]
        """
        if not documents:
            self.doc_ids = []
            self.vectors = None
            self._save_cache()
            return

        print(f"🔄 正在生成 {len(documents)} 条文档的 Embedding（调用 {EMBEDDING_MODEL}）...")
        texts = [d['content'] for d in documents]
        ids = [d['id'] for d in documents]

        vectors = self.embed_texts(texts)
        if len(vectors) == 0:
            print("⚠️ Embedding 全部失败，跳过保存")
            self.doc_ids = []
            self.vectors = None
            return

        self.vectors = vectors
        self.doc_ids = ids
        self._save_cache()
        print(f"✅ Embedding 索引构建完成，维度 {self.vectors.shape}")

    def add_documents(self, new_docs: List[Dict]):
        """增量添加新文档的 Embedding。"""
        existing_ids = set(self.doc_ids)
        to_add = [d for d in new_docs if d['id'] not in existing_ids]

        if not to_add:
            return

        texts = [d['content'] for d in to_add]
        ids = [d['id'] for d in to_add]

        print(f"🔄 增量 Embedding {len(to_add)} 条文档...")
        new_vectors = self.embed_texts(texts)

        if self.vectors is None:
            self.vectors = new_vectors
            self.doc_ids = ids
        else:
            self.vectors = np.vstack([self.vectors, new_vectors])
            self.doc_ids.extend(ids)

        self._save_cache()

    def search(self, query: str, top_k: int = 4) -> List[Dict]:
        """对查询进行语义检索，返回按相似度排序的结果。"""
        if self.vectors is None or len(self.doc_ids) == 0:
            return []

        query_vec = self.embed_texts([query])  # (1, dim)
        scores = cosine_similarity(query_vec, self.vectors)[0]

        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append({
                    'content': '',  # 不存 content，由外面补充
                    'id': self.doc_ids[idx],
                    'score': round(float(scores[idx]), 4),
                    '_source': 'embedding',
                })
        return results

    def count(self) -> int:
        return len(self.doc_ids) if self.doc_ids else 0


# ── 全局实例 ──────────────────────────────────────────

_kb = None
_embedding = None


def get_kb() -> LocalKnowledgeBase:
    global _kb
    if _kb is None:
        from django.conf import settings
        persist_dir = getattr(settings, 'AGENT_CHAT_PERSIST_DIR', './kb_index')
        _kb = LocalKnowledgeBase(persist_dir=persist_dir)
    return _kb


# ── 构建知识库 ─────────────────────────────────────────

def build_kb(md_dir: str = None, force_rebuild: bool = False):
    """扫描 MD 目录，构建或更新知识库。"""
    if md_dir is None:
        from django.conf import settings
        md_dir = getattr(settings, 'AGENT_CHAT_KB_DIR', './kb')

    md_path = Path(md_dir)
    md_files = list(md_path.rglob("*.md"))

    if not md_files:
        print(f"⚠️ 在 {md_dir} 下未找到 .md 文件")
        return

    kb = get_kb()

    new_docs = []
    for md_file in md_files:
        content = md_file.read_text(encoding='utf-8')
        filename = md_file.relative_to(md_path).as_posix()
        chunks = chunk_text(content)
        print(f"  {filename}: {len(chunks)} 个块")

        for i, chunk in enumerate(chunks):
            chunk_id = f"{filename}::chunk_{i}"
            new_docs.append({
                'id': chunk_id,
                'content': chunk,
                'source': filename,
            })

    if force_rebuild or not new_docs:
        kb.documents = new_docs
        kb._rebuild_index()
        # 同步重建 Embedding 索引
        emb = get_embedding()
        emb.build_index(new_docs)
        print(f"✅ 索引重建完成，共 {len(kb.documents)} 个文档块")
    else:
        kb.add_documents(new_docs)
        emb = get_embedding()
        emb.add_documents(new_docs)
        print(f"✅ 增量更新完成，共 {len(kb.documents)} 个文档块")


# ── 公开检索接口 ──────────────────────────────────────

def get_embedding() -> EmbeddingRetriever:
    global _embedding
    if _embedding is None:
        from django.conf import settings
        persist_dir = getattr(settings, 'AGENT_CHAT_PERSIST_DIR', './kb_index')
        _embedding = EmbeddingRetriever(persist_dir=persist_dir)
    return _embedding


def search_kb(query: str, top_k: int = 4) -> List[Dict]:
    """搜索知识库——TF-IDF + Embedding 融合检索。
    如果 Embedding API 不可用，自动降级为纯 TF-IDF。
    """
    kb = get_kb()

    # 1. TF-IDF 检索（取 2 倍候选）
    tfidf_results = kb.search(query, top_k=top_k * 2)

    # 2. Embedding 语义检索（尝试，失败则降级）
    embedding_results = []
    try:
        emb = get_embedding()
        if emb.vectors is None or emb.count() == 0:
            if kb.documents:
                print("🔄 首次使用，尝试在线构建 Embedding 索引...")
                emb.build_index(kb.documents)
        if emb.vectors is not None:
            embedding_results = emb.search(query, top_k=top_k * 2)
    except Exception as e:
        print(f"⚠️ Embedding 检索不可用，降级为纯 TF-IDF: {e}")

    if not embedding_results:
        return [{
            'content': r['content'],
            'source': r.get('source', '未知来源'),
            'score': round(r['score'], 4),
        } for r in tfidf_results[:top_k] if r['score'] > 0]

    # 3. 合并 TF-IDF 和 Embedding 结果，去重
    seen = set()
    combined = []

    for r in tfidf_results:
        key = r.get('content', '')[:100]
        if key not in seen:
            seen.add(key)
            combined.append({
                'content': r['content'],
                'source': r.get('source', '未知来源'),
                'score': round(HYBRID_EMBEDDING_WEIGHT * 0 + HYBRID_TFIDF_WEIGHT * r['score'], 4),
                '_type': 'tfidf',
            })

    for r in embedding_results:
        idx = int(r['id'])
        if idx < len(kb.documents):
            doc = kb.documents[idx]
            key = doc.get('content', '')[:100]
            if key not in seen:
                seen.add(key)
                combined.append({
                    'content': doc['content'],
                    'source': doc.get('source', '未知来源'),
                    'score': round(HYBRID_EMBEDDING_WEIGHT * r['score'] + 0, 4),
                    '_type': 'embedding',
                })
            else:
                # 已经在 TF-IDF 结果中，提升分数
                for item in combined:
                    if item['content'][:100] == key:
                        boost = HYBRID_EMBEDDING_WEIGHT * r['score']
                        item['score'] = round(item['score'] + boost, 4)
                        break

    # 4. 按分数排序，取 top_k
    combined.sort(key=lambda x: x['score'], reverse=True)
    return [{
        'content': r['content'],
        'source': r['source'],
        'score': round(r['score'], 4),
    } for r in combined[:top_k] if r['score'] > 0]


def check_kb_status():
    """检查知识库状态。"""
    kb = get_kb()
    emb = get_embedding()
    return {
        'doc_count': kb.count(),
        'has_tfidf': kb._fitted,
        'embedding_count': emb.count(),
    }


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'secondweb.settings')
    django.setup()

    md_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kb')
    print(f"正在构建知识库，源目录: {md_dir}")
    build_kb(md_dir, force_rebuild=True)
