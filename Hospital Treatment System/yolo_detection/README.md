# YOLOv8 肺结节检测模块

## 数据集
LUNA16-DP2D (LUNA16 Diagnostic Preservation 2D)
- 6216 张 CT 切片（512×512）
- 220 张含结节，共 231 个结节标注
- 位置: `C:\Users\DELL\datasets\luna16_yolo\`

## 训练
```bash
python yolo_detection/train_yolo.py
```

## 推理
```python
from yolo_detection.detect import LungNoduleDetector

detector = LungNoduleDetector()
nodules = detector.detect_nodules('ct_slice.png')
for n in nodules:
    print(f"结节位置: {n['bbox']}, 置信度: {n['confidence']}")
```

## 已知问题
- torch 2.5.1 + torchvision 0.15.2 版本不兼容，C++ NMS ops 不可用
- 已用纯 Python NMS 实现打补丁（fix_nms.py）
