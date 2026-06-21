import time

from django.core.files.base import ContentFile
from django.shortcuts import render
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Article, Topic, Comment, User_info, Recognition
from django.http import HttpResponse, HttpResponseRedirect
from urllib.request import urlretrieve
import os
from PIL import Image, ImageDraw, ImageFont
from django.http import JsonResponse
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from datetime import timedelta
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
'''
伪静态化
'''
#这段代码定义了一个名为 `pseudo` 的函数，接受两个参数 `request` 和 `id`。函数的功能是根据传入的 `id` 参数，从指定的 URL 中下载文章，并将其保存到本地文件系统中的指定目录下。
# 具体来说，函数首先通过 `os.path.join` 函数构建了目标文件夹的路径，然后通过一个循环，依次遍历从 0 到 `id` 的范围。
# 在循环内部，它尝试从指定的 URL 中下载文章，并将其保存为一个以文章编号命名的 HTML 文件，文件路径为构建的目标文件夹路径加上文章编号和 `.html` 后缀。
# 如果下载过程中发生异常，则会捕获异常并打印错误信息。最后，函数返回一个 HttpResponse，表示任务完成。

def pseudo(request, id):
    dir_path = os.path.join(BASE_DIR, "templates/staticpage/")
    for i in range(0, int(id)):
        try:
            url = "http://127.0.0.1:8000/article/" + str(i)
            urlretrieve(url, filename=dir_path + str(i) + ".html")
        except Exception as err:
            print(err)
    return HttpResponse("完成")


'''
查询文章列表
带分页功能
'''


def home(request):
    topics = Topic.objects.all()
    articles = Article.objects.all()
    hot = list(Article.objects.annotate(comment_count=Count('comment')).filter(comment_count__gt=3).order_by('-comment_count')[:6])
    paginator = Paginator(articles, 3)  # 每页显示3条数据
    page = request.GET.get('page')  # 获取请求的页数
    try:
        articles = paginator.page(page)  # 获取当前页数的数据列表
    except PageNotAnInteger:  # 如果返回的页码不是数字(空值),返回第一页
        articles = paginator.page(1)
    except EmptyPage:  # 如果页数超出范围,返回最后一页
        articles = paginator.page(paginator.num_pages)
    # 识别统计（聚合查询，避免全表扫描）
    today = timezone.now()
    seven_days_ago = today - timedelta(days=6)

    recents = Recognition.objects.all().order_by('-recognition_date')[:6]
    total = Recognition.objects.count()
    covid_count = Recognition.objects.filter(result__contains='疑似肺炎').count()
    normal_count = total - covid_count

    # 近7天趋势（按日期分组，一条 SQL）
    daily_stats = {}
    for i in range(7):
        day = today - timedelta(days=i)
        daily_stats[day.strftime('%m-%d')] = 0

    daily_qs = (
        Recognition.objects
        .filter(recognition_date__gte=seven_days_ago)
        .annotate(date=TruncDate('recognition_date'))
        .values('date')
        .annotate(count=Count('id'))
    )
    for entry in daily_qs:
        if entry['date']:
            daily_stats[entry['date'].strftime('%m-%d')] = entry['count']

    # 今天识别数
    today_count = Recognition.objects.filter(
        recognition_date__date=today.date()
    ).count()

    # Y 轴：按 10 的倍数步进
    daily_max = max(daily_stats.values()) if daily_stats else 0
    y_max = ((daily_max // 10) + 1) * 10
    if y_max < 10:
        y_max = 10

    return render(request, "index.html", {
        "articles": articles,
        "hot": hot,
        "topics": topics,
        "stats": {
            'total': total,
            'covid': covid_count,
            'normal': normal_count,
            'today': today_count,
        },
        'daily_labels': list(daily_stats.keys()),
        'daily_counts': list(daily_stats.values()),
        'recent_records': recents,
        'y_max': y_max,
    })


'''
注册用户
'''


def register(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect("/")
    if request.method == "POST":
        username = request.POST["username"]
        pwd = request.POST["password"]
        pwd2 = request.POST.get("password2", "")
        email = request.POST["email"]
        nick = request.POST["nickname"]
        phone = request.POST["phone"]

        # 服务端密码确认校验
        if pwd != pwd2:
            return render(request, "register.html", {"error": "两次密码输入不一致"})

        # 服务端密码长度校验（>= 6 位）
        if len(pwd) < 6:
            return render(request, "register.html", {"error": "密码长度不能少于6位"})

        # 使用 Django 密码哈希（不再用 MD5）
        hashed_pwd = make_password(pwd)

        User_info.objects.create(username=username, password=hashed_pwd, email=email,
                                 nickname=nick, phone=phone)
        return HttpResponseRedirect("/login")
    return render(request, "register.html")


'''
用户登录
'''


def login(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect("/")
    if request.method == "POST":
        name = request.POST["username"]
        pwd = request.POST["password"]

        user = authenticate(request, username=name, password=pwd)
        if user is not None:
            auth_login(request, user)
            return HttpResponseRedirect("/")
        else:
            return render(request, "login.html", {"error": "用户名或密码错误"})
    return render(request, "login.html")


'''
用户注销
'''


def logout(request):
    auth_logout(request)
    return HttpResponseRedirect("/")


'''
根据文章ID,展示文章详细信息
'''


def article(request, id):
    topics = Topic.objects.all()
    # 尝试加载静态化页面（相对于templates目录的路径）
    static_page = "staticpage/" + str(id) + ".html"
    static_path = os.path.join(BASE_DIR, "templates", static_page)
    if os.path.exists(static_path):
        return render(request, static_page, {"topics": topics})
    else:
        cur_article = Article.objects.filter(id=id).first()
        if not cur_article:
            return HttpResponseRedirect("/")

        # 下一篇
        next_article = Article.objects.filter(id__gt=id).order_by('id').first()
        # 上一篇
        prev_article = Article.objects.filter(id__lt=id).order_by('-id').first()

        return render(request, "detail.html", {
            "article": cur_article, "topics": topics,
            "nexts": next_article or cur_article,
            "pres": prev_article or cur_article,
        })


'''
发布文章
'''


def post(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/login')
    topics = Topic.objects.values("id", "tname")
    user = User_info.objects.filter(username=request.user.username).first()
    if not user:
        return HttpResponseRedirect('/login')
    user_id = user.id
    if request.method == "POST":
        content = request.POST["content"]
        tid = request.POST["topic_id"]
        title = request.POST["title"]
        brief = request.POST["brief"]
        topic1 = Topic.objects.get(id=tid)
        article1 = Article(title=title, content=content, brief=brief, topic=topic1)
        article1.author = user["nickname"] if user["nickname"] else user["username"]
        article1.save()

        up_image_name = request.POST["up_image"]
        if up_image_name == "":
            return HttpResponseRedirect("/article/" + str(article1.id))
        photo = request.FILES['up_image']
        if photo:
            photo_name = "upload/" + request.FILES.get('up_image').name
            # 确保上传目录存在
            upload_dir = os.path.join(BASE_DIR, 'userimg', 'upload')
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)
            img = Image.open(photo)
            img.save(os.path.join(BASE_DIR, 'userimg', photo_name))
            count = Article.objects.filter(id=article1.id).update(image=photo_name)
            if count:
                print("上传成功")
            else:
                print("上传失败")
        return HttpResponseRedirect("/article/" + str(article1.id))

    return render(request, "post.html", {"topic": topics, })


'''
按照话题查询文章列表
'''


def topic(request, id):
    topics = Topic.objects.all()
    articles = Article.objects.filter(topic_id=id).all()
    paginator = Paginator(articles, 10)  # 每页显示6条数据
    page = request.GET.get('page')  # 获取请求的页数
    try:
        articles = paginator.page(page)  # 获取当前页数的数据列表
    except PageNotAnInteger:  # 如果返回的页码不是数字(空值),返回第一页
        articles = paginator.page(1)
    except EmptyPage:  # 如果页数超出范围,返回最后一页
        articles = paginator.page(paginator.num_pages)
    return render(request, "topics.html", {"articles": articles, "topics": topics, })


'''
评论
'''


def comment(request, id):
    commentator = request.POST.get("commentator", "")
    content = request.POST.get("content", "")
    if not commentator or not content:
        return HttpResponseRedirect("/article/" + str(id))
    user_list = list(User_info.objects.filter(username=commentator).values("id"))
    if not user_list:
        return HttpResponseRedirect("/article/" + str(id))
    commentator_id = user_list[0]["id"]
    Comment.objects.create(content=content, article_id=id, commentator_id=commentator_id)
    return HttpResponseRedirect("/article/"+str(id))


def recognition(request):
    topics = Topic.objects.all()
    # 延迟导入，避免启动时加载 TensorFlow
    from .recognition_model import get_available_models
    models = get_available_models()
    return render(request, "recognition.html", {"topics": topics, "models": models})


def draw_nodule_boxes(image_path, nodules, output_path):
    """在 CT 图片上画出肺结节检测框和置信度。"""
    img = Image.open(image_path).convert('RGB')
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("simhei.ttf", 18)
    except Exception:
        font = ImageFont.load_default()

    for i, n in enumerate(nodules, 1):
        x1, y1, x2, y2 = n['bbox']
        conf = n['confidence']
        # 绿色框（粗线）
        draw.rectangle([x1, y1, x2, y2], outline='lime', width=3)
        # 置信度标签
        label = f"#{i} {conf:.0%}"
        draw.text((x1, max(y1 - 24, 0)), label, fill='lime', font=font)

    img.save(output_path, 'PNG')
    return output_path


def handle_uploaded_file(file): #识别
    upload_dir = os.path.join(BASE_DIR, 'userimg', 'upload', 'recognition')
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)

    # 一次性读取文件内容
    file_content = file.read()

    # 保存最新上传的图片（覆盖，供识别使用）
    latest_path = os.path.join(upload_dir, 'img.png')
    with open(latest_path, 'wb+') as destination:
        destination.write(file_content)

    # 时间戳文件名保存 用于存储记录
    timestamp = str(int(time.time()))
    timestamp_filename = timestamp + '.png'
    timestamp_path = os.path.join(upload_dir, timestamp_filename)
    with open(timestamp_path, 'wb+') as destination:
        destination.write(file_content)

    # 返回URL相对路径（供前端显示）
    url_path = 'userimg/upload/recognition/' + timestamp_filename
    return url_path, latest_path
def upload(request):
    if request.method == 'POST' and request.FILES.get('image'):
        username = request.POST.get("commentator", "")
        model_name = request.POST.get("model", "mobilenetv2")
        image = request.FILES['image']
        # handle_uploaded_file 返回 (url相对路径, 绝对路径)
        image_url, image_abs_path = handle_uploaded_file(image)

        # 延迟导入，避免启动时加载TensorFlow
        from .recognition_model import predict, ensemble_predict, is_model_available

        # 检查所选模型是否可用
        if not is_model_available(model_name):
            return JsonResponse({
                'result': '❌ 所选模型不可用（权重文件缺失），请先运行训练脚本。',
                'image_url': image_url
            })

        # 传入图片绝对路径进行识别
        if model_name == 'ensemble':
            result, confidence = ensemble_predict(image_abs_path)
            print(f"[模型: 集成(MobileNet+ResNet50)] {result}, 置信度: {confidence:.4f}")
        else:
            result, confidence = predict(image_abs_path, backbone_name=model_name)
            print(f"[模型: {model_name}] {result}, 置信度: {confidence:.4f}")

        # YOLO 肺结节检测 + 画框（仅展示标注图，不输出文字）
        conf_threshold = float(request.POST.get('conf_threshold', 0.25))
        annotated_url = ''
        try:
            import sys, os as _os
            base_dir = _os.path.dirname(_os.path.dirname(__file__))
            yolo_dir = _os.path.join(base_dir, 'yolo_detection')
            if _os.path.exists(yolo_dir):
                sys.path.insert(0, base_dir)
                import yolo_detection.detect as yolo_detect
                model_path = _os.path.join(yolo_dir, 'runs', 'yolov8n_nodule', 'weights', 'best.pt')
                if _os.path.exists(model_path):
                    timestamp = str(int(time.time()))
                    upload_dir = _os.path.join(base_dir, 'userimg', 'upload', 'recognition')

                    detector = yolo_detect.LungNoduleDetector(model_path)
                    nodules = detector.detect_nodules(image_abs_path, conf=conf_threshold, iou=0.45)
                    if nodules:
                        annotated_filename = timestamp + '_annotated.png'
                        annotated_abs_path = _os.path.join(upload_dir, annotated_filename)
                        draw_nodule_boxes(image_abs_path, nodules, annotated_abs_path)
                        annotated_url = 'userimg/upload/recognition/' + annotated_filename
        except Exception as e:
            print(f'YOLO 检测异常: {e}')

        # 保存识别记录
        Recognition.objects.create(
            user_id=username,
            result=result,
            image=image_url,
        )

        reply = '有' + str(round(confidence * 100, 2)) + '%的可能性是' + result
        return JsonResponse({
            'result': reply,
            'image_url': image_url,
            'annotated_url': annotated_url,
        })

    topics = Topic.objects.all()
    return render(request, 'recognition.html', {"topics": topics})