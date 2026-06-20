"""
自定义模板标签：相对时间 + ISO 时间格式化
"""
from django import template
from django.utils import timezone
from datetime import timedelta

register = template.Library()


@register.filter(name='iso_time')
def iso_time(value):
    """将 datetime 对象转为 ISO 格式字符串，供 JS 解析。"""
    if not value:
        return ''
    # 确保有时区信息
    if timezone.is_naive(value):
        value = timezone.make_aware(value)
    return value.isoformat()
