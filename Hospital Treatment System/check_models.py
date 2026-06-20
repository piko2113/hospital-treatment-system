"""验证训练结果"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['DJANGO_SETTINGS_MODULE'] = 'secondweb.settings'

import django
django.setup()

from home.recognition_model import is_model_available, get_available_models, IMAGE_HEIGHT, IMAGE_WIDTH

print(f'输入尺寸: {IMAGE_HEIGHT}x{IMAGE_WIDTH}')
print()
for m in get_available_models():
    status = 'OK' if m['available'] else '不可用'
    print(f'  {m["key"]}: {status}')
