"""
YOLOv8 肺结节检测推理脚本
用训练好的模型检测 CT 切片中的结节
"""

import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import fix_nms

from PIL import Image
import numpy as np
from ultralytics import YOLO

class LungNoduleDetector:
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = os.path.join(
                os.path.dirname(__file__),
                'runs', 'yolov8n_nodule', 'weights', 'best.pt'
            )
        
        if os.path.exists(model_path):
            self.model = YOLO(model_path)
            print(f"模型加载成功: {model_path}")
        else:
            print(f"警告: 模型不存在 {model_path}")
            print("请先运行 train_yolo.py 训练模型")
            self.model = None
    
    def detect(self, image_path, conf=0.25, iou=0.45):
        """
        检测 CT 切片中的结节
        
        参数:
            image_path: CT 切片路径 (PNG/JPG) 或 numpy array
            conf: 置信度阈值
            iou: NMS 的 IoU 阈值
        
        返回:
            results: YOLO 检测结果
        """
        if self.model is None:
            return None
        
        results = self.model(image_path, conf=conf, iou=iou)
        return results
    
    def detect_nodules(self, image_path, conf=0.25, iou=0.45):
        """
        检测并返回结构化结果
        
        返回:
            list of dict: [{ 'bbox': [x1,y1,x2,y2], 'confidence': 0.87, 'class': 'nodule' }, ...]
        """
        results = self.detect(image_path, conf, iou)
        if results is None or len(results) == 0:
            return []
        
        nodules = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf_val = round(box.conf[0].item(), 4)
                nodules.append({
                    'bbox': [x1, y1, x2, y2],
                    'confidence': conf_val,
                    'class': 'nodule'
                })
        
        return nodules

if __name__ == '__main__':
    # 测试
    detector = LungNoduleDetector()
    print("检测器初始化完成")
