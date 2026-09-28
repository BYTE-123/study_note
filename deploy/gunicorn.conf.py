"""gunicorn 生产配置：仅监听本机回环，公网入口交给 Nginx。

用法（在项目根目录）::

    gunicorn -c deploy/gunicorn.conf.py "app:create_app()"

要点：
- ``worker_class="gthread"``：AI 润色是 SSE 长连接，同步 worker 会被长连接占满；
  多线程 worker 才能在少量 worker 下同时服务多个流式请求。
- ``timeout=120``：SSE 单次润色可能持续数十秒，超时必须放宽，否则会被 worker 杀掉。
- 日志写到项目根的 ``logs/``（已在 .gitignore 中排除），便于 systemd 之外就地排查。
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 只监听本机，公网流量由 Nginx 反向代理进来
bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:8000")

# 多线程 worker：兼顾低成本与 SSE 并发
worker_class = "gthread"
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))

# SSE 长连接：放宽超时
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5

accesslog = os.path.join(LOG_DIR, "access.log")
errorlog = os.path.join(LOG_DIR, "error.log")
loglevel = os.environ.get("GUNICORN_LOGLEVEL", "info")
