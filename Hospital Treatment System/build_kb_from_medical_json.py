"""下载并转换医学知识图谱数据为 KB Markdown 格式"""
import json
import urllib.request
import os

BASE = os.path.dirname(os.path.abspath(__file__))
RAW_PATH = os.path.join(BASE, 'medical_raw.json')
KB_DIR = os.path.join(BASE, 'kb', 'medical_basics')

# 1. 下载
print('📥 下载 medical.json ...')
url = 'https://raw.githubusercontent.com/liuhuanyong/QASystemOnMedicalKG/master/data/medical.json'
urllib.request.urlretrieve(url, RAW_PATH)
size_kb = os.path.getsize(RAW_PATH) / 1024
print(f'✅ 下载完成: {size_kb:.0f}KB')

# 2. 读取
with open(RAW_PATH, 'r', encoding='utf-8') as f:
    raw = f.read()

# JSON 是 MongoDB 格式，每行一个 JSON 对象
lines = raw.strip().split('\n')
print(f'📄 共 {len(lines)} 条记录')

# 3. 分类整理
diseases = {}  # name -> {info}
for line in lines:
    line = line.strip()
    if not line:
        continue
    try:
        obj = json.loads(line)
    except:
        continue
    
    name = obj.get('name', '')
    if not name:
        continue
    
    if name not in diseases:
        diseases[name] = {
            'symptom': [],
            'check': [],
            'drug': [],
            'department': '',
            'cure_department': [],
            'acompany': [],
        }
    
    d = diseases[name]
    # 症状
    if 'symptom' in obj:
        d['symptom'].append(obj['symptom'])
    # 检查
    if 'check' in obj:
        d['check'].append(obj['check'])
    # 药品
    if 'drug' in obj:
        d['drug'].append(obj['drug'])
    # 科室
    if 'cure_department' in obj:
        d['cure_department'].append(obj['cure_department'])
    # 并发症
    if 'acompany' in obj:
        d['acompany'].append(obj['acompany'])

print(f'🏥 共整理 {len(diseases)} 种疾病信息')

# 4. 生成 Markdown 文件（按拼音首字母分组）
groups = {}
for name in diseases:
    first = name[0] if name else '0'
    if ord(first) < 0x4e00:
        first = '0'
    groups.setdefault(first, []).append(name)

os.makedirs(KB_DIR, exist_ok=True)

# 先删除旧的 KB markdown（保留现有的几个核心文件）
existing = ['肺炎简介', '医院科室介绍', '就医导诊指南', '常见疾病知识', '常用药品知识']
# 保留它们，补充新文件

total_chunks = 0
for first_char in sorted(groups.keys()):
    names = groups[first_char]
    # 每 15 种病一个文件
    file_idx = 0
    for i in range(0, len(names), 20):
        batch = names[i:i+20]
        filename = f'疾病知识_{first_char}{file_idx}.md'
        filepath = os.path.join(KB_DIR, filename)
        
        content = []
        for n in sorted(batch):
            info = diseases[n]
            content.append(f'# {n}')
            
            s = list(set(info['symptom']))
            if s:
                content.append(f'\n## 症状\n- {"、".join(s[:10])}')
            
            c = list(set(info['check']))
            if c:
                content.append(f'\n## 检查\n- {"、".join(c[:8])}')
            
            d = list(set(info['drug']))
            if d:
                content.append(f'\n## 常用药品\n- {"、".join(d[:8])}')
            
            dept = list(set(info['cure_department']))
            if dept:
                content.append(f'\n## 就诊科室\n- {dept[0]}')
            
            ac = list(set(info['acompany']))
            if ac:
                content.append(f'\n## 并发症\n- {"、".join(ac[:5])}')
            
            content.append('')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content))
        
        chunks = len(batch)
        total_chunks += chunks
        print(f'  📝 {filename}: {chunks} 种疾病')

print(f'\n✅ 生成完成，共 {len(groups)} 组、{total_chunks} 种疾病知识')

# 清理下载的 JSON
os.remove(RAW_PATH)
print('🧹 已清理 raw JSON')
