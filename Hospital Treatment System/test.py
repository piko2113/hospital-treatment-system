import matplotlib.pyplot as plt
import tensorflow as tf
import matplotlib
import pathlib
import random
import os

'''
模型测试
'''

def get_images():

    images_name = []
    images_list = []
    path = ".\\test_photos"
    if os.path.isdir(path):
        for dir in os.listdir(path):
            for file in os.listdir(path + "\\" + dir):
                if (os.path.isfile(path + "\\" + dir + "\\" + file)):
                    if os.path.splitext(file)[1] == ".png":
                        image_raw = tf.io.read_file(path + "\\" + dir + "\\" + file)
                        image_tensor = tf.image.decode_image(image_raw, channels=3)
                        image_final = tf.image.resize(image_tensor, [224, 224])
                        image_final = image_final / 255.0
                        image_final = image_final[tf.newaxis, ...]
                        images_name.append(path + "\\" + dir + "\\" + file)
                        images_list.append(image_final)
    else:
        # 原始图片
        image_raw = tf.io.read_file(path)
        image_tensor = tf.image.decode_image(image_raw, channels=3)
        image_final = tf.image.resize(image_tensor, [224, 224])
        image_final = image_final / 255.0
        image_final = image_final[tf.newaxis, ...]
        images_name.append(path)
        images_list.append(image_final)
    return images_name, images_list

def get_one_images(img_path):

    images_name = []
    images_list = []
    # 预处理图片
    image_raw = tf.io.read_file(img_path)
    image_tensor = tf.image.decode_image(image_raw, channels=3)
    image_final = tf.image.resize(image_tensor, [224, 224])
    image_final = image_final / 255.0
    image_final = image_final[tf.newaxis, ...]
    images_name.append(img_path)
    images_list.append(image_final)
    return images_name, images_list



def get_label_name(path):
    left = len(path) - 1
    right = len(path) - 1
    flag = 1
    for i in range(len(path) - 1, -1, -1):
        if (path[i] == '\\'):
            if (flag):
                right = i
                flag = 0
            else:
                left = i + 1
                break
    return path[left:right]



labels_name = ['COVID', 'nonCOVID']
chinese_name = ['疑似肺炎', '状态正常']

checkpoint_save_path = "./lung.ckpt"
mobile_net = tf.keras.applications.MobileNetV2(input_shape=(224, 224, 3), include_top=False)




mobile_net.trainable = False

# 构建Keras中Sequential模型
model = tf.keras.Sequential([
    mobile_net,   # 核心层
    tf.keras.layers.GlobalAveragePooling2D(),   # 施加全局平均值池化
    tf.keras.layers.Dense(len(labels_name), activation='softmax')    # 全连接层
])

if os.path.exists(checkpoint_save_path + '.index'):
    print('-------------加载模型-----------------')
    model.load_weights(checkpoint_save_path)

# 分类预测调用函数
def user_predict(img_path=None):
    if img_path is None:
        img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'userimg', 'upload', 'recognition', 'img.png')
    images_name, images_stream = get_one_images(img_path)  # 获取单张图片
    result = model.predict(images_stream[0])               # 载入模型进行预测
    max_prob_index = int(result.argmax())
    confidence = result[0][max_prob_index]
    pre_label = labels_name[int(result.argmax())]          # 获取英文结果
    for i in range(len(chinese_name)):
        if pre_label == labels_name[i]:
            pre_label = chinese_name[i]
            break
    return pre_label, confidence

if __name__ == "__main__":
    test_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'userimg', 'upload', 'recognition', 'img.png')
    print(user_predict(test_path))
# # 获取图片名字列表，图片流列表
# images_name, images_stream = get_images()
# # 各种类图片标签命中
# image_acc = list(0 for i in range(len(labels_name)))
# # 各种类图片计数
# image_count = list(0 for i in range(len(labels_name)))
# # 测试所有图片
# for i in range(len(images_name)):
#     # 换行
#     print()
#     # 测试
#     result = model.predict(images_stream[i])
#     # 实际标签
#     real_label = get_label_name(images_name[i])
#     # 预测得到的标签
#     pre_label = labels_name[int(result.argmax())]
#     # 实际标签与预测得到的标签相同
#     if (real_label == pre_label):
#         image_acc[int(result.argmax())] = image_acc[int(result.argmax())] + 1
#         image_count[int(result.argmax())] = image_count[int(result.argmax())] + 1
#     # 实际标签与预测得到的标签不相同
#     else:
#         # 查找图片实际标签，并对图片计数加一
#         for i in range(len(labels_name)):
#             if (labels_name[i] == real_label):
#                 image_count[i] = image_count[i] + 1
#                 break
#     # 输出最大概率的标签
#     print(images_name[i] + "\n识别结果: " + pre_label)
#     # 输出标签所有概率
#     for j in range(len(labels_name)):
#         print(chinese_name[j] + ": " + str(round(result[0][j] * 100, 2)) + "%")
#
# # 输出全部图片预测的准确率汇总
# print("---------------所有图片统计信息---------------")
# for i in range(len(labels_name)):
#     if (image_count[i]):
#         print(chinese_name[i] + "命中率: " + str(round(image_acc[i] / image_count[i] * 100, 2)) + "%")
#     else:
#         print(chinese_name[i] + "命中率: 0.00%")

