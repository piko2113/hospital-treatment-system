"""Download medical KG JSON and convert to KB markdown files (streaming)"""
import json
import urllib.request
import os
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
KB_DIR = os.path.join(BASE, 'kb', 'medical_basics')
os.makedirs(KB_DIR, exist_ok=True)

url = 'https://raw.githubusercontent.com/liuhuanyong/QASystemOnMedicalKG/master/data/medical.json'
print('Downloading and processing (streaming)...')

response = urllib.request.urlopen(url)
diseases = defaultdict(lambda: {'symptom': [], 'check': [], 'drug': [], 'cure_department': [], 'acompany': []})
count = 0
buffer = b''

while True:
    chunk = response.read(65536)
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
        if obj.get('symptom'):
            d['symptom'].append(obj['symptom'])
        if obj.get('check'):
            d['check'].append(obj['check'])
        if obj.get('drug'):
            d['drug'].append(obj['drug'])
        if obj.get('cure_department'):
            d['cure_department'].append(obj['cure_department'])
        if obj.get('acompany'):
            d['acompany'].append(obj['acompany'])
        count += 1
        if count % 10000 == 0:
            print('  processed %d records...' % count)

print('Total records: %d' % count)
print('Unique diseases: %d' % len(diseases))

# Group by first character
groups = defaultdict(list)
for name in diseases:
    first = name[0] if name else '0'
    if ord(first) < 0x4e00:
        first = '0'
    groups[first].append(name)

# Write markdown files
total = 0
for first_char in sorted(groups.keys()):
    names = sorted(groups[first_char])
    for i in range(0, len(names), 30):
        batch = names[i:i+30]
        fp = os.path.join(KB_DIR, '疾病_%s%d.md' % (first_char, i // 30))
        out_lines = []
        for n in batch:
            info = diseases[n]
            out_lines.append('# ' + n)
            s = list(set(info['symptom']))
            if s:
                out_lines.append('\n## 症状')
                out_lines.append('- ' + '、'.join(s[:10]))
            c = list(set(info['check']))
            if c:
                out_lines.append('\n## 检查')
                out_lines.append('- ' + '、'.join(c[:8]))
            d = list(set(info['drug']))
            if d:
                out_lines.append('\n## 药品')
                out_lines.append('- ' + '、'.join(d[:6]))
            dept = list(set(info['cure_department']))
            if dept:
                out_lines.append('\n## 就诊科室')
                out_lines.append('- ' + dept[0])
            out_lines.append('')
        with open(fp, 'w', encoding='utf-8') as f:
            f.write('\n'.join(out_lines))
        total += len(batch)
        print('  wrote %s (%d diseases)' % (fp, len(batch)))

print('\nDone! %d diseases written to KB.' % total)
