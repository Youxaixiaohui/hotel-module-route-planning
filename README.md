# 路线规划模块

Django 路线规划模块，支持百度/高德地图展示、固定起终点的途经点优化、真实驾车路线查询和无地图密钥时的距离估算回退。

## 本地运行

1. 创建并激活 Python 虚拟环境。
2. 安装依赖：`pip install -r requirements.txt`
3. 将 `.env.example` 复制为 `.env`，至少设置一个随机的 `DJANGO_SECRET_KEY`。
4. 初始化数据库：`python manage.py migrate`
5. 启动：`python manage.py runserver`
6. 访问 `http://127.0.0.1:8000/register/` 注册后使用。

地图密钥可留空，此时页面会提示地图未配置，后端路线计算自动使用球面距离估算。运行测试：`python manage.py test`。

## 生产部署

设置 `DEBUG=False`、准确的 `ALLOWED_HOSTS`、足够长的随机密钥，并在 HTTPS 入口启用 `SECURE_SSL_REDIRECT=True`、`SESSION_COOKIE_SECURE=True`、`CSRF_COOKIE_SECURE=True`。生产环境应使用持久数据库和进程级共享缓存替代 SQLite 与本地内存缓存。
