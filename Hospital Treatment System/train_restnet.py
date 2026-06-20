"""
ResNet50 训练脚本
改进：数据增强 + 微调 + 224输入 + EarlyStopping + LR调度
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import tensorflow as tf
import pathlib
import random
import os

# ── 常量 ──────────────────────────────────────────────
IMAGE_HEIGHT, IMAGE_WIDTH = 224, 224
BATCH_SIZE = 32
EPOCHS_PHASE1 = 10    # 冻结骨干训练
EPOCHS_PHASE2 = 15    # 微调训练
FINE_TUNE_AT = 120    # 解冻 ResNet50 最后约 120 层
FINE_TUNE_LR = 1e-5


def get_paths_labels(data_root):
    all_image_paths = list(data_root.glob('*/*'))
    all_image_paths = [str(path) for path in all_image_paths]
    random.shuffle(all_image_paths)
    label_names = sorted(item.name for item in data_root.glob('*/') if item.is_dir())
    return all_image_paths, label_names


# ── 数据增强 ──────────────────────────────────────────
def augment_image(image, label):
    image = tf.image.random_flip_left_right(image)
    image = tf.keras.layers.RandomRotation(factor=0.08)(image, training=True)
    image = tf.image.random_brightness(image, max_delta=0.2)
    image = tf.image.random_contrast(image, lower=0.8, upper=1.2)
    return image, label


def preprocess_image(image_path):
    image_raw = tf.io.read_file(image_path)
    image = tf.image.decode_image(image_raw, channels=3, expand_animations=False)
    image = tf.image.resize(image, [IMAGE_HEIGHT, IMAGE_WIDTH])
    image = tf.cast(image, tf.float32) / 255.0
    return image


def create_dataset(paths, labels, batch_size=BATCH_SIZE, shuffle_buffer=1000, augment=False):
    AUTOTUNE = tf.data.AUTOTUNE
    ds = tf.data.Dataset.from_tensor_slices((paths, labels))
    ds = ds.shuffle(shuffle_buffer)
    ds = ds.map(lambda img, lbl: (preprocess_image(img), lbl), num_parallel_calls=AUTOTUNE)
    if augment:
        ds = ds.map(augment_image, num_parallel_calls=AUTOTUNE)
    ds = ds.batch(batch_size)
    ds = ds.prefetch(AUTOTUNE)
    return ds


# ── 数据准备 ──────────────────────────────────────────
BASE_DIR = pathlib.Path(__file__).parent.resolve()
data_root = BASE_DIR / "train_photos"
print(f"📂 训练数据: {data_root}")

all_image_paths, label_names = get_paths_labels(data_root)
random.shuffle(all_image_paths)

label_to_index = {name: i for i, name in enumerate(label_names)}
all_labels = [label_to_index[pathlib.Path(p).parent.name] for p in all_image_paths]

images_count = len(all_image_paths)
train_count = int(images_count * 0.8)

print(f"总图片: {images_count} | 训练: {train_count} | 验证: {images_count - train_count}")
print(f"类别: {label_names}")

if images_count == 0:
    print("❌ 未找到训练图片")
    exit(1)

train_paths = all_image_paths[:train_count]
train_labels = all_labels[:train_count]
val_paths = all_image_paths[train_count:]
val_labels = all_labels[train_count:]

train_ds = create_dataset(train_paths, train_labels, shuffle_buffer=train_count, augment=True)
val_ds = create_dataset(val_paths, val_labels, shuffle_buffer=images_count - train_count, augment=False)

# ── 模型构建：Phase 1（冻结骨干） ────────────────────
print("\n🔨 Phase 1: 冻结骨干训练")

backbone = tf.keras.applications.ResNet50(
    input_shape=(IMAGE_HEIGHT, IMAGE_WIDTH, 3),
    include_top=False,
    weights='imagenet',
)
backbone.trainable = False

model = tf.keras.Sequential([
    backbone,
    tf.keras.layers.GlobalAveragePooling2D(),
    tf.keras.layers.Dropout(0.3),
    tf.keras.layers.Dense(len(label_names), activation='softmax'),
])

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=1e-4),
    loss='sparse_categorical_crossentropy',
    metrics=["accuracy"],
)
model.summary()

# ── Phase 1 训练 ──────────────────────────────────────
checkpoint_path = str(BASE_DIR / "lung_restnet.ckpt")
callbacks_phase1 = [
    tf.keras.callbacks.ModelCheckpoint(
        filepath=checkpoint_path, save_weights_only=True, save_best_only=True,
    ),
    tf.keras.callbacks.EarlyStopping(
        monitor='val_loss', patience=3, restore_best_weights=True,
    ),
    tf.keras.callbacks.ReduceLROnPlateau(
        monitor='val_loss', factor=0.5, patience=2, min_lr=1e-6,
    ),
]

train_per_epoch = tf.math.ceil(train_count / BATCH_SIZE).numpy()
val_per_epoch = tf.math.ceil((images_count - train_count) / BATCH_SIZE).numpy()

if os.path.exists(checkpoint_path + '.index'):
    print("  加载已有权重，继续训练...")
    model.load_weights(checkpoint_path)

history1 = model.fit(
    train_ds,
    epochs=EPOCHS_PHASE1,
    steps_per_epoch=train_per_epoch,
    validation_data=val_ds,
    validation_steps=val_per_epoch,
    callbacks=callbacks_phase1,
)

# ── Phase 2：微调 ──────────────────────────────────────
print("\n🔧 Phase 2: 微调骨干网络")

backbone.trainable = True
for layer in backbone.layers[:FINE_TUNE_AT]:
    layer.trainable = False
for layer in backbone.layers[FINE_TUNE_AT:]:
    layer.trainable = True

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=FINE_TUNE_LR),
    loss='sparse_categorical_crossentropy',
    metrics=["accuracy"],
)

callbacks_phase2 = [
    tf.keras.callbacks.ModelCheckpoint(
        filepath=checkpoint_path, save_weights_only=True, save_best_only=True,
    ),
    tf.keras.callbacks.EarlyStopping(
        monitor='val_loss', patience=4, restore_best_weights=True,
    ),
    tf.keras.callbacks.ReduceLROnPlateau(
        monitor='val_loss', factor=0.5, patience=2, min_lr=1e-7,
    ),
]

history2 = model.fit(
    train_ds,
    epochs=EPOCHS_PHASE2,
    steps_per_epoch=train_per_epoch,
    validation_data=val_ds,
    validation_steps=val_per_epoch,
    callbacks=callbacks_phase2,
)

# ── 可视化 ──────────────────────────────────────────────
def plot_history(h1, h2, output_path="restnet_training.png"):
    acc = h1.history['accuracy'] + h2.history['accuracy']
    val_acc = h1.history['val_accuracy'] + h2.history['val_accuracy']
    loss = h1.history['loss'] + h2.history['loss']
    val_loss = h1.history['val_loss'] + h2.history['val_loss']
    split = len(h1.history['accuracy'])

    matplotlib.rcParams['font.family'] = 'SimHei'
    matplotlib.rcParams['font.size'] = 10

    plt.figure(figsize=(12, 4))
    plt.subplot(1, 2, 1)
    plt.plot(acc, label='训练集准确率')
    plt.plot(val_acc, label='验证集准确率')
    plt.axvline(x=split, color='gray', linestyle='--', alpha=0.5, label='开始微调')
    plt.title('准确率')
    plt.xlabel('迭代次数')
    plt.legend()

    plt.subplot(1, 2, 2)
    plt.plot(loss, label='训练集损失率')
    plt.plot(val_loss, label='验证集损失率')
    plt.axvline(x=split, color='gray', linestyle='--', alpha=0.5)
    plt.title('损失率')
    plt.xlabel('迭代次数')
    plt.legend()

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"📊 训练曲线已保存到 {output_path}")

plot_history(history1, history2)
plt.show()
plt.close()

print("\n✅ 训练完成！")
print(f"Phase 1（冻结）: {len(history1.history['accuracy'])} epochs")
print(f"Phase 2（微调）: {len(history2.history['accuracy'])} epochs")
