#!/usr/bin/env bash
# 个人笔记 · 一键部署脚本（Linux）
#
# 用法（在服务器上，以 root 运行）：
#     sudo bash deploy/install.sh
#
# 可选环境变量：
#     APP_DIR=/srv/notes            安装目录（默认 /srv/notes）
#     SERVER_NAME=1.2.3.4           Nginx server_name（默认取公网 IP，没有域名就用 IP）
#     DEEPSEEK_API_KEY=sk-xxx       填了 AI 润色才能用；也可以之后手改 .env
#
# 这个脚本做六件事：
#   1. 识别 apt / dnf / yum 并安装 python3、venv、nginx、git
#   2. 拉取（或更新）代码
#   3. 建虚拟环境并用清华镜像装依赖
#   4. 生成 .env（自动生成随机 SECRET_KEY，权限 600）
#   5. 建库、装 systemd 服务
#   6. 写 Nginx 反代（/api/ 关闭缓冲以支持 SSE）并启动、自检
#
# 幂等：重复执行会更新代码并重启服务，不会重复创建配置。
# 注意：脚本不配置 HTTPS（需要域名）；有域名后见 deploy/README.md 用 certbot 补。

set -euo pipefail

APP_NAME="notes"
PKG_APP_NAME="个人笔记"
DEFAULT_APP_DIR="/srv/notes"
REPO_URL="https://github.com/BYTE-123/study_note.git"
PIP_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"

log()  { printf '\033[32m[+]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "请用 root 运行：sudo bash deploy/install.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(dirname "$SCRIPT_DIR")"
APP_DIR="${APP_DIR:-$DEFAULT_APP_DIR}"

# ---------------------------------------------------------------- 1. 依赖
log "识别包管理器并安装系统依赖"
if   command -v apt-get >/dev/null 2>&1; then PKG=apt
elif command -v dnf     >/dev/null 2>&1; then PKG=dnf
elif command -v yum     >/dev/null 2>&1; then PKG=yum
else die "未识别的包管理器（只支持 apt / dnf / yum）"
fi
log "包管理器：$PKG"

case "$PKG" in
  apt)
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq python3 python3-venv python3-pip nginx git curl ca-certificates
    ;;
  dnf)
    dnf install -y -q python3 python3-pip nginx git curl ca-certificates
    ;;
  yum)
    yum install -y -q python3 python3-pip nginx git curl ca-certificates
    ;;
esac

command -v python3 >/dev/null || die "python3 安装失败"
PYV="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
log "python3 版本：$PYV"
python3 -c 'import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)' \
  || die "需要 Python 3.10+，当前 $PYV"

# ---------------------------------------------------------------- 2. 代码
if [ -f "$SRC_DIR/app.py" ] && [ "$SRC_DIR" = "$APP_DIR" ]; then
  log "使用当前目录代码：$APP_DIR"
elif [ -d "$APP_DIR/.git" ]; then
  log "更新已有代码：$APP_DIR"
  git -C "$APP_DIR" pull --ff-only
elif [ -e "$APP_DIR" ] && [ -n "$(ls -A "$APP_DIR" 2>/dev/null)" ]; then
  die "$APP_DIR 已存在且非空、又不是 git 仓库。请换个 APP_DIR 或先清空它。"
else
  log "克隆代码到 $APP_DIR"
  git clone --depth 1 "$REPO_URL" "$APP_DIR"
fi
[ -f "$APP_DIR/app.py" ] || die "$APP_DIR 里没有 app.py，代码不完整"

# ---------------------------------------------------------------- 3. 虚拟环境
log "创建虚拟环境并安装依赖（清华镜像）"
[ -d "$APP_DIR/.venv" ] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip -q -i "$PIP_INDEX"
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt" -q -i "$PIP_INDEX"

# ---------------------------------------------------------------- 4. .env
ENV_FILE="$APP_DIR/.env"
if [ -f "$ENV_FILE" ]; then
  warn ".env 已存在，保留不动（要改请编辑 $ENV_FILE）"
else
  log "生成 .env（随机 SECRET_KEY）"
  SK="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
  cat > "$ENV_FILE" <<EOF
# 由 deploy/install.sh 生成
SECRET_KEY=$SK
# 留空则 AI 润色不可用，填上真实 Key 即可启用
DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY:-}
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
UPLOAD_MAX_SIZE=5242880
PAGE_SIZE=10
AI_RATE_LIMIT_PER_MINUTE=10
GUNICORN_BIND=127.0.0.1:8000
GUNICORN_WORKERS=2
GUNICORN_THREADS=4
GUNICORN_TIMEOUT=120
EOF
fi
# 说明：DB_PATH 与 UPLOAD_DIR 刻意不写，走项目默认（app.py 同级的 notes.db 与
# static/uploads/）。上传 URL 前缀在 blueprints/upload.py 里固定为 /static/uploads，
# 因此 UPLOAD_DIR 必须落在 static/uploads，否则图片会 404。
mkdir -p "$APP_DIR/static/uploads"

# ---------------------------------------------------------------- 5. 服务账号
if   id www-data >/dev/null 2>&1; then RUN_USER=www-data
elif id nginx    >/dev/null 2>&1; then RUN_USER=nginx
else RUN_USER=root; fi
log "服务运行账号：$RUN_USER"

log "初始化数据库（首次启动自动建表）"
( cd "$APP_DIR" && "$APP_DIR/.venv/bin/python" -c "from app import create_app; create_app()" )

chown -R "$RUN_USER:$RUN_USER" "$APP_DIR"
chmod 600 "$ENV_FILE"

# ---------------------------------------------------------------- 6. systemd
log "写入 systemd 服务 /etc/systemd/system/${APP_NAME}.service"
cat > "/etc/systemd/system/${APP_NAME}.service" <<EOF
[Unit]
Description=${PKG_APP_NAME} (gunicorn)
After=network.target

[Service]
User=$RUN_USER
Group=$RUN_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$APP_DIR/.venv/bin/gunicorn -c $APP_DIR/deploy/gunicorn.conf.py "app:create_app()"
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# ---------------------------------------------------------------- 7. Nginx
SERVER_NAME="${SERVER_NAME:-_}"
log "写入 Nginx 配置 /etc/nginx/conf.d/${APP_NAME}.conf（server_name=$SERVER_NAME）"
if [ -e /etc/nginx/sites-enabled/default ]; then
  log "移除 Debian/Ubuntu 默认站点（否则抢 80 端口）"
  rm -f /etc/nginx/sites-enabled/default
fi
cat > "/etc/nginx/conf.d/${APP_NAME}.conf" <<EOF
server {
    listen 80;
    server_name $SERVER_NAME;

    client_max_body_size 6m;

    # 静态资源与上传图片由 Nginx 直接读盘
    location /static/ {
        alias $APP_DIR/static/;
        expires 7d;
        access_log off;
    }

    # 接口：转发给 gunicorn。SSE（AI 润色）必须关闭缓冲
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
        chunked_transfer_encoding on;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# ---------------------------------------------------------------- 8. 放行端口
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -qi active; then
  log "ufw 已启用，放行 80/tcp"
  ufw allow 80/tcp >/dev/null || true
fi
if command -v firewall-cmd >/dev/null 2>&1 && systemctl is-active firewalld >/dev/null 2>&1; then
  log "firewalld 已启用，放行 http"
  firewall-cmd --permanent --add-service=http >/dev/null || true
  firewall-cmd --reload >/dev/null || true
fi

# ---------------------------------------------------------------- 9. 启动
log "启动服务"
systemctl daemon-reload
systemctl enable --now "$APP_NAME" >/dev/null
nginx -t
systemctl enable --now nginx >/dev/null
systemctl reload nginx

# ---------------------------------------------------------------- 10. 自检
log "自检：等待 gunicorn 就绪"
ok=0
for _ in $(seq 1 30); do
  if curl -fsS -m 3 http://127.0.0.1:8000/api/health >/dev/null 2>&1; then ok=1; break; fi
  sleep 1
done
[ "$ok" -eq 1 ] || die "gunicorn 未就绪，请看：journalctl -u ${APP_NAME} -n 50 --no-pager"

curl -fsS -m 5 http://127.0.0.1:8000/api/health && echo
IP="$(curl -s -m 5 https://api.ipify.org 2>/dev/null || true)"
[ -n "$IP" ] || IP="<你的公网IP>"

echo
log "部署完成"
echo "    访问地址： http://$IP/"
echo "    服务状态： systemctl status $APP_NAME"
echo "    服务日志： journalctl -u $APP_NAME -f"
echo "    改配置后： systemctl restart $APP_NAME"
echo "    配置文件： $ENV_FILE"
echo
if grep -q '^DEEPSEEK_API_KEY=$' "$ENV_FILE" 2>/dev/null; then
  warn "DEEPSEEK_API_KEY 为空 → AI 润色会提示「AI 服务暂时不可用」。"
  warn "填法： 编辑 $ENV_FILE 补上 Key，然后 systemctl restart $APP_NAME"
fi
warn "如果你用的是云服务器（阿里云 / 腾讯云 / 华为云等），还要在控制台的【安全组】里放行 80 端口，"
warn "否则从外网打不开 —— 这一步在服务器内部看不到，是最常见的「部署好了但访问不了」原因。"
