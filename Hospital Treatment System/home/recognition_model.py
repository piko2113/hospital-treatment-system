"""
统一模型管理模块
- 延迟加载 / 缓存两种模型（MobileNetV2、ResNet50）
- TensorFlow 仅在真正需要时导入（访问识别页面不触发 TF 加载）
- 与 test.py / test_restnet.py 独立，Web 端专用
"""

import os

# ── 常量 ──────────────────────────────────────────────
LABELS_NAME = ['COVID', 'nonCOVID']
CHINESE_NAME = ['疑似肺炎', '状态正常']
IMAGE_HEIGHT, IMAGE_WIDTH = 224, 224

# 模型注册表
MODEL_REGISTRY = {
    'mobilenetv2': {
        'display': 'MobileNetV2（轻量快速）',
        'class_name': 'MobileNetV2',
        'package': 'tf.keras.applications',
        'checkpoint': './lung.ckpt',
    },
    'resnet50': {
        'display': 'ResNet50（高精度）',
        'class_name': 'ResNet50',
        'package': 'tf.keras.applications',
        'checkpoint': './lung_restnet.ckpt',
    },
    'ensemble': {
        'display': 'MobileNetV2 + ResNet50 集成（加权平均）',
        'is_virtual': True,
    },
}

# 延迟创建的 TF 模块引用（首次用到时注入）
_tf = None
_models = {}


def _ensure_tf():
    """按需加载 TensorFlow。"""
    global _tf
    if _tf is None:
        import tensorflow as tf
        _tf = tf


def _build_model(backbone_name):
    """构建模型结构并加载权重（内部调用，确保 _tf 已就绪）。"""
    _ensure_tf()
    info = MODEL_REGISTRY.get(backbone_name)
    if info is None:
        raise ValueError(f"未知模型：{backbone_name}，可选：{list(MODEL_REGISTRY.keys())}")
    if info.get('is_virtual'):
        raise RuntimeError(f"{backbone_name} 为虚拟模型（集成），无需单独构建，请使用 ensemble_predict()")

    checkpoint_path = info['checkpoint']
    backbone_cls = getattr(_tf.keras.applications, info['class_name'])

    backbone = backbone_cls(
        input_shape=(IMAGE_HEIGHT, IMAGE_WIDTH, 3),
        include_top=False,
    )
    backbone.trainable = False

    model = _tf.keras.Sequential([
        backbone,
        _tf.keras.layers.GlobalAveragePooling2D(),
        _tf.keras.layers.Dense(len(LABELS_NAME), activation='softmax'),
    ])

    model.compile(
        optimizer=_tf.keras.optimizers.Adam(),
        loss='sparse_categorical_crossentropy',
        metrics=["accuracy"],
    )

    ckpt_index = checkpoint_path + '.index'
    if os.path.exists(ckpt_index):
        model.load_weights(checkpoint_path)
    else:
        print(f"⚠️ [recognition_model] 未找到权重文件：{checkpoint_path}，模型可能未训练")

    return model


def preprocess_image(image_path):
    """加载并预处理单张图片，返回 (1, 224, 224, 3) 张量。"""
    _ensure_tf()
    image_raw = _tf.io.read_file(image_path)
    image_tensor = _tf.image.decode_image(image_raw, channels=3, expand_animations=False)
    image_final = _tf.image.resize(image_tensor, [IMAGE_HEIGHT, IMAGE_WIDTH])
    image_final = image_final / 255.0
    image_final = image_final[_tf.newaxis, ...]
    return image_final


def get_model(backbone_name='mobilenetv2', force_reload=False):
    """获取（或加载）指定模型，缓存复用。"""
    if force_reload and backbone_name in _models:
        del _models[backbone_name]
    if backbone_name not in _models:
        _models[backbone_name] = _build_model(backbone_name)
    return _models[backbone_name]


def _checkpoint_exists(backbone_name):
    """检查单个真实模型的 checkpoint 是否存在。"""
    info = MODEL_REGISTRY.get(backbone_name)
    if info is None or info.get('is_virtual'):
        return False
    ckpt = info.get('checkpoint')
    if ckpt is None:
        return False
    return os.path.exists(ckpt + '.index')


def is_model_available(backbone_name):
    """检查指定模型是否可用。虚拟模型（ensemble）需要子模型全部就绪。"""
    info = MODEL_REGISTRY.get(backbone_name)
    if info is None:
        return False
    if info.get('is_virtual'):
        # 集成模型需要两个子模型都训练完成
        return _checkpoint_exists('mobilenetv2') and _checkpoint_exists('resnet50')
    return _checkpoint_exists(backbone_name)


def get_available_models():
    """返回当前可用的模型列表（不加载 TF，仅检查文件）。"""
    available = []
    for key, info in MODEL_REGISTRY.items():
        available.append({
            'key': key,
            'display': info['display'],
            'available': is_model_available(key),
        })
    return available


def predict(image_path, backbone_name='mobilenetv2'):
    """对单张图片进行预测，返回 (中文标签, 置信度)。"""
    if not is_model_available(backbone_name):
        raise RuntimeError(
            f"❌ {MODEL_REGISTRY[backbone_name]['display']} 的权重文件不存在，"
            f"请先运行训练脚本。"
        )

    model = get_model(backbone_name)
    image_tensor = preprocess_image(image_path)
    result = model.predict(image_tensor, verbose=0)
    max_prob_index = int(result.argmax())
    confidence = float(result[0][max_prob_index])
    label = CHINESE_NAME[max_prob_index]
    return label, confidence


def ensemble_predict(image_path, weights=None):
    """
    加权平均集成预测：同时使用 MobileNetV2 + ResNet50。

    weights: dict, 默认 {'mobilenetv2': 0.4, 'resnet50': 0.6}
            ResNet50 精度通常更高，默认权重更大。
    返回 (中文标签, 置信度)
    """
    if weights is None:
        weights = {'mobilenetv2': 0.4, 'resnet50': 0.6}

    if not is_model_available('ensemble'):
        raise RuntimeError(
            "❌ 集成模型不可用，请确保 MobileNetV2 和 ResNet50 均已训练完成。"
        )

    model_mobilenet = get_model('mobilenetv2')
    model_resnet = get_model('resnet50')
    image_tensor = preprocess_image(image_path)

    pred_mobilenet = model_mobilenet.predict(image_tensor, verbose=0)
    pred_resnet = model_resnet.predict(image_tensor, verbose=0)

    # 加权平均 softmax 概率
    ensemble_prob = weights['mobilenetv2'] * pred_mobilenet + weights['resnet50'] * pred_resnet

    max_prob_index = int(ensemble_prob.argmax())
    confidence = float(ensemble_prob[0][max_prob_index])
    label = CHINESE_NAME[max_prob_index]
    return label, confidence
