# hotel/models.py — 路线规划模块最小化 model
# 路线规划功能不直接依赖数据库模型，仅需 User 用于认证
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, phone=None, user_type='customer'):
        if not username:
            raise ValueError('用户必须设置用户名')
        user = self.model(username=username, phone=phone, user_type=user_type)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, phone=None):
        user = self.create_user(username=username, password=password, phone=phone, user_type='admin')
        return user


class User(AbstractBaseUser):
    USER_TYPE_CHOICES = (
        ('admin', '管理员'),
        ('staff', '员工'),
        ('customer', '客户'),
    )
    username = models.CharField(max_length=50, unique=True, verbose_name='用户名')
    phone = models.CharField(max_length=11, unique=True, verbose_name='手机号码')
    email = models.EmailField(max_length=255, blank=True, null=True, unique=True, verbose_name='邮箱地址')
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='customer', verbose_name='用户类型')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name='注册时间')
    last_login = models.DateTimeField(auto_now=True, verbose_name='最后登录')

    objects = UserManager()
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['phone']

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.username

    @property
    def is_staff(self):
        return self.user_type in ['admin', 'staff']

    @property
    def is_admin(self):
        return self.user_type == 'admin'

    def has_perm(self, perm, obj=None):
        return self.is_admin

    def has_module_perms(self, app_label):
        return self.is_admin
