from django.contrib import admin
from .models import User_info, Article, Topic, Comment,Recognition


class UsersAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "nickname", "password", "email", "phone", "is_admin")


class ArticlesAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "publish_date", "topic", "image")
    search_fields = ("title",)


class CommentsAdmin(admin.ModelAdmin):
    list_display = ("id", "article", "commentator", "comment_date", "parent_id")


class TopicsAdmin(admin.ModelAdmin):
    list_display = ("id", "tname", "parent_id")

class RecognitionAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "result", "recognition_date")

admin.site.register(Article, ArticlesAdmin)
admin.site.register(Comment, CommentsAdmin)
admin.site.register(Topic, TopicsAdmin)
admin.site.register(User_info, UsersAdmin)
admin.site.register(Recognition, RecognitionAdmin)
