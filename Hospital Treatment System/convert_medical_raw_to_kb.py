"""
读取本地的 medical_raw.json（44MB），直接转换为 KB markdown 文件
跳过网络下载，直接处理已有数据
使用二进制读取 + 行分割，避免编码问题
"""
import json
import os
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
RAW_PATH = os.path.join(BASE, 'medical_raw.json')
KB_DIR = os.path.join(BASE, 'kb', 'medical_basics')
os.makedirs(KB_DIR, exist_ok=True)

# 1. 读取本地文件（二进制流式，逐行处理）
print(f'📖 读取 {RAW_PATH} ...')
size_mb = os.path.getsize(RAW_PATH) / 1024 / 1024
print(f'   大小: {size_mb:.1f} MB')

diseases = defaultdict(lambda: {
    'symptom': [], 'check': [], 'drug': [], 
    'cure_department': [], 'acompany': [], 
    'desc': '', 'cause': '', 'prevent': '',
})

count = 0
buffer = b''

with open(RAW_PATH, 'rb') as f:
    while True:
        chunk = f.read(65536)  # 64KB
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

print(f'📄 共处理 {count} 条记录 → {len(diseases)} 种独立疾病')

# 2. 按首字母分组
groups = defaultdict(list)
for name in diseases:
    first = name[0] if name else '0'
    if ord(first) < 0x4e00:
        first = '0'
    groups[first].append(name)

# 3. 生成 Markdown 文件
total_chunks = 0
for first_char in sorted(groups.keys()):
    names = groups[first_char]
    for i in range(0, len(names), 20):
        batch = names[i:i+20]
        filename = f'疾病知识_{first_char}{i // 20}.md'
        filepath = os.path.join(KB_DIR, filename)
        
        content_lines = []
        for n in sorted(batch):
            info = diseases[n]
            content_lines.append(f'# {n}')
            
            if info['desc']:
                content_lines.append(f'\n## 简介\n{info["desc"][:500]}')
            
            s = list(set(info['symptom']))
            if s:
                # 简单过滤明显非症状的词
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
        
        total_chunks += len(batch)
        print(f'  📝 {filename}: {len(batch)} 种疾病')

print(f'\n✅ 生成完成！共 {len(groups)} 组、{total_chunks} 种疾病知识 → {KB_DIR}')
