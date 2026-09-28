# 个人笔记

一个简洁优雅的在线个人笔记应用：Markdown 写作、图片插入、AI 润色、分享、评论与收藏。

- **后端**：Python + Flask（JSON API）+ SQLite
- **前端**：原生 HTML + CSS + JavaScript（多页静态页面，无构建步骤）

## 环境准备

```bash
python -m venv .venv
source .venv/Scripts/activate            # Windows Git Bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 配置

复制样例文件后按需修改：

```bash
cp .env.example .env
```

| 变量 | 说明 |
|---|---|
| `SECRET_KEY` | Session 签名密钥，务必改为随机字符串，绝不提交到仓库 |
| `DB_PATH` | SQLite 数据库文件路径，默认 `notes.db` |
| `UPLOAD_DIR` | 图片上传目录，默认 `static/uploads` |
| `UPLOAD_MAX_SIZE` | 单张图片大小上限（字节），默认 5242880（5MB） |
| `PAGE_SIZE` | 列表分页大小，默认 10 |
| `AI_RATE_LIMIT_PER_MINUTE` | AI 润色每分钟调用上限，默认 10 |
| `DEEPSEEK_API_KEY` | DeepSeek API Key，仅存于服务器环境变量 |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址，默认 `https://api.deepseek.com/v1` |
| `DEEPSEEK_MODEL` | 润色所用模型名，默认 `deepseek-chat` |

`.env` 与 `notes.db` 已在 `.gitignore` 中排除，不会进入版本控制。

## 运行

```bash
python app.py
```

默认监听 `http://127.0.0.1:5000`：

- 健康检查：`GET /api/health` → `{"code":"OK","message":"操作成功","data":{"status":"up"}}`
- 主页：`GET /`

## 生产部署

线上用 gunicorn 托管 Flask、Nginx 反向代理并关闭 SSE 缓冲（否则 AI 润色不会流式返回）：

```bash
gunicorn -c deploy/gunicorn.conf.py "app:create_app()"
```

配置样例与完整步骤见 [`deploy/README.md`](deploy/README.md)、[`deploy/nginx.conf.example`](deploy/nginx.conf.example)。
注意：gunicorn 仅支持 Linux，Windows 上请用 `python app.py` 做本地开发。

## 测试

```bash
.venv/Scripts/python.exe -m pytest -q
```

## 目录结构

```
app.py            应用工厂、路由与全局错误处理
config.py         配置（环境变量读取）
models.py         SQLite 连接、建表与 CRUD
blueprints/       按领域拆分的接口蓝图
services/         外部服务封装（AI 等）
utils/            统一响应与鉴权等横切能力
templates/        静态 HTML 页面
static/css        common.css 等样式
static/js         api.js 等脚本
static/img        背景素材与图标
static/uploads/   用户上传图片
deploy/           gunicorn 与 Nginx 部署配置
docs/specs/       需求与设计文档
```
