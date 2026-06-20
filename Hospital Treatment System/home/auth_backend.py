"""
自定义认证后端：让 User_info 模型配合 Django 的 authenticate() / login() 体系。
"""
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password, make_password
from .models import User_info


class UserInfoBackend(BaseBackend):
    """使用 User_info 模型的认证后端，密码用 Django make_password / check_password。"""

    def authenticate(self, request, username=None, password=None):
        # 使用 filter().first() 避免重复用户名抛异常
        user = User_info.objects.filter(username=username).first()
        if user is None:
            return None
        # 兼容旧 MD5 哈希：如果密码仍是 MD5 格式（32位hex），自动升级为 Django 哈希
        if len(user.password) == 32 and user.password.isalnum():
            import hashlib
            if hashlib.md5(password.encode('utf-8')).hexdigest() == user.password:
                user.password = make_password(password)
                user.save(update_fields=['password'])
                return user
            return None
        # 标准 Django 哈希校验
        if check_password(password, user.password):
            return user
        return None

    def user_can_authenticate(self, user):
        # User_info 使用 status 字段（0=正常，1=已注销）而非 is_active
        return user.status == 0

    def get_user(self, user_id):
        try:
            return User_info.objects.get(pk=user_id)
        except Exception:
            return None
