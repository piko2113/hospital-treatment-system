"""
YOLOv8 肺结节检测训练脚本
用于 LUNA16-DP2D 数据集
数据集位置在 datasets/luna16_yolo
训练完成后集成到 Django 项目
"""

import os, sys
sys.path.insert(0, os.path.dirname(__file__))

# 先打 NMS 补丁（torchvision C++ ops 不兼容）
import fix_nms

from ultralytics import YOLO

# 数据集路径
import os as _os
DATA_YAML = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'datasets', 'luna16_yolo', 'dataset.yaml')

# 确认数据存在
assert os.path.exists(DATA_YAML), f"数据集配置不存在: {DATA_YAML}"

# 加载预训练模型
model = YOLO(os.path.join(os.path.dirname(__file__), 'yolov8n.pt'))

print(f"\n{'='*50}")
print(f"开始训练 YOLOv8n 肺结节检测模型")
print(f"数据集: {DATA_YAML}")
print(f"{'='*50}\n")

# 开始训练
results = model.train(
    data=DATA_YAML,
    epochs=200,
    imgsz=512,
    batch=4,
    device='cpu',
    
    # 数据增强
    augment=True,
    hsv_h=0.015,
    hsv_s=0.7,
    hsv_v=0.4,
    degrees=10.0,
    translate=0.2,
    scale=0.5,
    shear=2.0,
    flipud=0.5,
    fliplr=0.5,
    mosaic=0.5,
    mixup=0.1,
    copy_paste=0.3,
    
    # 优化器
    optimizer='AdamW',
    lr0=0.001,
    lrf=0.1,
    momentum=0.937,
    weight_decay=5e-4,
    
    # 早停
    patience=30,
    save_period=10,
    
    # 输出目录
    project=os.path.join(os.path.dirname(__file__), 'runs'),
    name='yolov8n_nodule',
    exist_ok=True,
    
    workers=2,
)

print("\n训练完成！")
print(f"模型保存在: {os.path.join(os.path.dirname(__file__), 'runs', 'yolov8n_nodule', 'weights', 'best.pt')}")
