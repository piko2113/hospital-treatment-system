from django.db import models
from tinymce.models import HTMLField


class User_info(models.Model):
    STATUS = (
        (0, '正常'),
        (1, '已注销'),
    )
    username = models.CharField("用户名", max_length=64)
    nickname = models.CharField("用户昵称", max_length=64, null=True)
    email = models.EmailField("邮箱地址")
    password = models.CharField("密码", max_length=128)
    phone = models.CharField("电话", max_length=24, null=True)
    is_admin = models.BooleanField("是否管理员", default=False)
    status = models.IntegerField("状态", default=0, choices=STATUS)
    last_login = models.DateTimeField("最后登录时间", null=True, blank=True)

    is_authenticated = True
    is_anonymous = False

    def __str__(self):
        return self.username


'''
话题信息
'''


class Topic(models.Model):
    tname = models.CharField("话题名称", max_length=16)
    parent_id = models.IntegerField(default=-1)

    def __str__(self):
        return self.tname


'''
文章数据模型
'''


class Article(models.Model):
    title = models.CharField("标题", max_length=128)
    brief = models.CharField("简介", max_length=512)
    content = models.TextField(verbose_name='文章详情')
    author = models.CharField("作者", max_length=55, default="本站")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, verbose_name="所属话题")
    publish_date = models.DateTimeField("发布时间", auto_now_add=True, editable=True)
    update_date = models.DateTimeField("更新时间", auto_now=True, null=True)
    image = models.ImageField("图片", upload_to="upload", default="upload/logo2_03.png")

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-publish_date']


'''
评论的数据模型
'''


class Comment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, verbose_name="所属文章")
    commentator = models.ForeignKey(User_info, on_delete=models.CASCADE)
    content = models.TextField()
    comment_date = models.DateTimeField("评论时间", auto_now_add=True, editable=True)
    parent_id = models.IntegerField(default=-1)

'''
检测记录的数据模型
'''

class Recognition(models.Model):
    user_id = models.CharField("用户id", max_length=512)
    result = models.CharField("识别结果", max_length=512)
    recognition_date = models.DateTimeField("时间", auto_now_add=True, editable=True)
    image = models.ImageField("图片", upload_to="upload/recognition", default="upload/recognition/logo2_03.png")
