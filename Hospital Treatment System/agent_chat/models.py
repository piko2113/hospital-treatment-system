from django.db import models


class ChatHistory(models.Model):
    """用户对话历史记录。"""
    username = models.CharField("用户名", max_length=64, db_index=True)
    question = models.TextField("提问内容")
    answer = models.TextField("AI回答", blank=True, null=True)
    created_at = models.DateTimeField("时间", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
