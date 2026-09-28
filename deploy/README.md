# 部署说明（Linux + gunicorn + Nginx）

面向一台公网 Linux 服务器（Debian/Ubuntu 或 CentOS 均可）。假设项目放在 `/srv/notes`，
域名为 `your-domain.example`，按下文替换即可。

## 0. 前置

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip nginx
python3 --version          # 需 ≥ 3.10
```

## 1. 拉取代码并建虚拟环境

```bash
sudo mkdir -p /srv/notes && sudo chown "$USER":"$USER" /srv/notes
# 把项目文件放进 /srv/notes（git clone 或 rsync）
cd /srv/notes

python3 -m venv .venv
source .venv/bin/activate
# 依赖走清华镜像，requirements.txt 已锁定版本
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`（**不要提交到版本库**）：

| 变量 | 生产建议 |
|---|---|
| `SECRET_KEY` | 必须改为随机串：`python -c "import secrets;print(secrets.token_hex(32))"` |
| `DB_PATH` | 指向持久化目录，如 `/srv/notes/data/notes.db` |
| `UPLOAD_DIR` | 指向持久化目录，如 `/srv/notes/data/uploads` |
| `DEEPSEEK_API_KEY` | 真实 Key；留空则 AI 润色返回「AI 服务暂时不可用」 |
| `DEEPSEEK_BASE_URL` | 默认 `https://api.deepseek.com/v1` |
| `DEEPSEEK_MODEL` | 默认 `deepseek-chat`，可换官方推荐对话模型 |
| `UPLOAD_MAX_SIZE` | 默认 5242880（5MB） |
| `AI_RATE_LIMIT_PER_MINUTE` | 默认 10，用于控制 AI 成本 |
| `GUNICORN_BIND` | 默认 `127.0.0.1:8000` |
| `GUNICORN_WORKERS` / `GUNICORN_THREADS` | 默认 2 / 4，小站够用 |
| `GUNICORN_TIMEOUT` | 默认 120，SSE 需要较长超时 |

> 建议给 `.env` 收紧权限：`chmod 600 .env`。

## 3. 初始化数据库

首次启动会自动建表（`models.init_db()`），无需手工执行 SQL：

```bash
python -c "from app import create_app; create_app()"
```

## 4. 启动 gunicorn

```bash
gunicorn -c deploy/gunicorn.conf.py "app:create_app()"
curl -s http://127.0.0.1:8000/api/health
# {"code":"OK","message":"操作成功","data":{"status":"up"}}
```

日志写入项目根 `logs/`（`access.log` / `error.log`）。

### 用 systemd 常驻

新建 `/etc/systemd/system/notes.service`：

```ini
[Unit]
Description=个人笔记 (gunicorn)
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/srv/notes
EnvironmentFile=/srv/notes/.env
ExecStart=/srv/notes/.venv/bin/gunicorn -c /srv/notes/deploy/gunicorn.conf.py "app:create_app()"
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now notes
sudo systemctl status notes
```

## 5. 配置 Nginx

```bash
sudo cp /srv/notes/deploy/nginx.conf.example /etc/nginx/conf.d/notes.conf
sudoedit /etc/nginx/conf.d/notes.conf      # 改 server_name 与 alias 路径
sudo nginx -t && sudo systemctl reload nginx
```

务必保留 `/api/` 段的 `proxy_buffering off;`，否则 AI 润色的流式输出会被 Nginx 缓冲成
一次性返回。

### HTTPS

用 certbot 签发证书后，启用配置中注释的 443 段并把 80 段改为 301 跳转：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.example
```

配好 HTTPS 后，建议再给 Flask 打开安全 Cookie（在 `.env` 所在环境追加）：
会话 Cookie 的 `Secure` 属性可避免明文网络下泄漏。当前实现固定
`HttpOnly + SameSite=Lax`；如需 `Secure`，可在 `app.py` 的 `create_app()` 中按环境变量
开启 `SESSION_COOKIE_SECURE`。

## 6. 数据持久化与备份

需要持久化的只有两份数据：

- `notes.db`（或 `DB_PATH` 指向的文件）
- `static/uploads/`（或 `UPLOAD_DIR` 指向的目录）

建议放在 `/srv/notes/data/`，纳入定期备份：

```bash
# 备份（SQLite 用 .backup 保证一致性，勿直接 cp 正在写入的库）
sqlite3 /srv/notes/data/notes.db ".backup '/backup/notes-$(date +%F).db'"
tar -czf "/backup/uploads-$(date +%F).tar.gz" -C /srv/notes/data uploads

# 回滚：停服 → 还原两份数据 → 启服
```

## 7. 上线自检

- `curl https://your-domain.example/api/health` 返回 `code=OK`。
- 浏览器打开主页 → 注册 → 写笔记 → 发布 → 分享 → 无痕窗口打开分享链接。
- 打开分享链接输入密码可读正文。
- 编辑器划词右键 → AI 润色 → 结果**逐字出现**（证明 Nginx 未缓冲 SSE）。
- 检查 `logs/error.log` 无异常堆栈。
