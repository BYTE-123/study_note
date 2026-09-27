# Phase 1: 骨架与基础设施

**目标：** 搭起可运行的 Flask 骨架、统一响应与错误规范、SQLite 建表与测试夹具、前端设计令牌与请求封装，为后续所有阶段提供地基。
**前置条件：** 无。
**交付物：** 可 `python app.py` 启动的应用；`GET /api/health` 与任意非法接口均返回统一 JSON；数据库四张表建好；`common.css` 设计令牌与 `api.js` 请求封装可用；pytest 夹具可跑。

**本阶段实现的界面决策：** 契约 10.3 的视觉令牌（10 个颜色角色、字体、圆角、阴影变量）在 `common.css` 落地；契约 10.2 的全局骨架（导航 / 内容区 max-width 1100px / 页脚）在占位主页与 `common.css` 中定下结构。

---

## Task 1: 项目骨架与依赖锁定

**目标：** 建立目录结构、配置模块与应用工厂，使应用可启动并托管静态资源与页面。

**文件：**
- 新建：`requirements.txt`
- 新建：`.env.example`
- 新建：`config.py`
- 新建：`app.py`
- 新建：`blueprints/__init__.py`、`utils/__init__.py`、`services/__init__.py`
- 新建：`static/uploads/.gitkeep`
- 新建：`README.md`

**步骤：**
- [x] 创建虚拟环境并安装依赖（走国内镜像）：
  ```bash
  python -m venv .venv
  source .venv/Scripts/activate      # Windows Git Bash
  pip install Flask python-dotenv requests pytest -i https://pypi.tuna.tsinghua.edu.cn/simple
  ```
- [x] 安装完成后把解析出的确切版本写回 `requirements.txt`（格式 `Flask==x.y.z`，每行一个包），完成版本锁定。
- [x] 写 `.env.example`，包含：
  ```
  SECRET_KEY=replace-with-random-string
  DB_PATH=notes.db
  UPLOAD_DIR=static/uploads
  UPLOAD_MAX_SIZE=5242880
  PAGE_SIZE=10
  AI_RATE_LIMIT_PER_MINUTE=10
  DEEPSEEK_API_KEY=
  DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
  DEEPSEEK_MODEL=deepseek-chat
  ```
- [x] 写 `config.py`：定义 `Config` 类从环境变量读取上述字段（`UPLOAD_MAX_SIZE`/`PAGE_SIZE`/`AI_RATE_LIMIT_PER_MINUTE` 转 `int`），并提供 `TestingConfig`（`DB_PATH`、`UPLOAD_DIR` 会被测试夹具覆盖、`SECRET_KEY='test'`、`TESTING=True`）。
- [x] 写 `app.py`：实现 `create_app(config_object=Config)`，设置 `app.secret_key`、`app.config.from_object(...)`、`SESSION_COOKIE_HTTPONLY=True`、`SESSION_COOKIE_SAMESITE='Lax'`、`app.json.ensure_ascii = False`（保证中文不被转义为 `\uXXXX`），静态目录 `static/`，注册所有蓝图（本阶段先留空占位 `Blueprint` 列表），注册 `GET /api/health` 返回 `{"code":"OK","message":"操作成功","data":{"status":"up"}}`，注册页面路由 `/` → `templates/index.html`（其余页面路由在各阶段补充），启动时调用 `models.init_db()`。
- [x] 写一份最小 `templates/index.html` 占位页（含全局骨架结构），供本阶段验证；页面 `<head>` 写明 `<meta charset="utf-8">`，且所有 HTML 与 JS/CSS 文件以 UTF-8 无 BOM 保存。
- [x] Run: `python app.py`
  - Expected: 控制台输出监听地址，无异常。
- [x] Run: `curl -s http://127.0.0.1:5000/api/health`
  - Expected: 返回 `{"code":"OK","message":"操作成功","data":{"status":"up"}}`。
- [x] Run: `curl -s http://127.0.0.1:5000/`
  - Expected: 返回占位主页 HTML（HTTP 200）。
- [x] 写 `README.md`，记录本机运行命令与 `.env` 配置说明。

**安全/边界说明：** `SECRET_KEY` 必须来自环境变量；`.env.example` 不得包含真实密钥；若使用版本控制，需排除 `.env` 与 `notes.db`（可创建 `.gitignore`）。

---

## Task 2: 统一响应、错误码与全局错误处理

**目标：** 让所有成功与失败响应都符合 `{code,message,data}` 规范，且失败时机均映射到错误码表。

**文件：**
- 新建：`utils/responses.py`
- 新建：`utils/errors.py`
- 修改：`app.py`（注册全局错误处理器）
- 测试：`tests/test_responses.py`

**步骤：**
- [x] 写失败测试 `tests/test_responses.py`：

```python
def test_ok_shape():
    from utils.responses import ok
    body, status = ok({"n": 1})
    assert status == 200
    assert body["code"] == "OK"
    assert body["message"] == "操作成功"
    assert body["data"] == {"n": 1}

def test_fail_maps_http_status():
    from utils.responses import fail
    body, status = fail("NOT_FOUND")
    assert status == 404
    assert body["code"] == "NOT_FOUND"
    assert body["message"] == "资源不存在"

def test_unknown_route_returns_json_404(client):
    r = client.get("/api/no-such-endpoint")
    assert r.status_code == 404
    assert r.get_json()["code"] == "NOT_FOUND"

def test_uncaught_exception_returns_server_error(app):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    client = app.test_client()

    @app.route("/api/boom")
    def boom():
        raise RuntimeError("kaboom")

    r = client.get("/api/boom")
    assert r.status_code == 500
    assert r.get_json()["code"] == "SERVER_ERROR"
```
- [x] Run: `pytest tests/test_responses.py -q`
  - Expected: FAIL（`ModuleNotFoundError: utils.responses`）。
- [x] 写 `utils/errors.py`：定义 `ApiError(Exception)`（携带 `code`），以及常量字典 `ERROR_MESSAGES` 与 `ERROR_HTTP_STATUS`，覆盖错误码表全部 12 个 code（`OK`、`PARAM_ERROR`、`PASSWORD_ERROR`、`WRONG_PASSWORD`、`UNAUTHORIZED`、`FORBIDDEN`、`NOT_FOUND`、`CONFLICT`、`FILE_ERROR`、`AI_ERROR`、`RATE_LIMIT`、`SERVER_ERROR`），message 使用设计文档 9.2 的中文文案。
- [x] 写 `utils/responses.py`（返回 `(body_dict, http_status)` 二元组，由 Flask 自动序列化）：
  - `ok(data=None, message="操作成功")` → `({"code":"OK","message":message,"data":data}, 200)`
  - `fail(code, message=None)` → 取 `ERROR_MESSAGES[code]` 兜底 message，返回 `(body, ERROR_HTTP_STATUS[code])`
- [x] 在 `app.py` 注册错误处理器：
  - `ApiError` → `fail(e.code)`
  - `werkzeug.exceptions.HTTPException`（404/405）→ `fail("NOT_FOUND")`
  - 兜底 `Exception` → 记录日志后 `fail("SERVER_ERROR")`，且不把异常细节返回前端。
- [x] Run: `pytest tests/test_responses.py -q`
  - Expected: PASS（4 passed）。

**安全/边界说明：** 兜底处理器不得回显堆栈或数据库错误原文，只返回中文通用提示。

---

## Task 3: 数据层与建表 + 测试夹具

**目标：** 落地四张表、外键与级联，提供可复用的测试夹具。

**文件：**
- 新建：`models.py`
- 新建：`tests/conftest.py`
- 测试：`tests/test_models.py`

**步骤：**
- [x] 写 `tests/conftest.py`（用 `monkeypatch` 覆盖配置，避免测试间污染）：

```python
import pytest
from config import TestingConfig
from app import create_app

@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(TestingConfig, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(TestingConfig, "UPLOAD_DIR", str(tmp_path / "uploads"))
    return create_app(TestingConfig)

@pytest.fixture
def client(app):
    return app.test_client()
```
- [x] 写失败测试 `tests/test_models.py`，至少覆盖：`init_db()` 后四张表存在；`users.email` 与 `users.username` 唯一约束生效；`favorites(user_id,note_id)` 唯一约束生效；删除笔记后其 `comments` 与 `favorites` 被级联清除；`on delete` 依赖 `PRAGMA foreign_keys=ON` 生效。
- [x] Run: `pytest tests/test_models.py -q`
  - Expected: FAIL（`models.init_db` 未实现）。
- [x] 写 `models.py`：
  - `get_conn()`：`sqlite3.connect(config.DB_PATH)`，`conn.row_factory = sqlite3.Row`，执行 `PRAGMA foreign_keys = ON`。
  - `init_db()`：按设计文档 8.1–8.4 建 `users`/`notes`/`comments`/`favorites`（字段、类型、默认值、唯一约束、外键 `ON DELETE CASCADE` 完全一致），并建索引 `idx_notes_user_status`、`idx_notes_share_token`、`idx_comments_note`；使用 `CREATE TABLE IF NOT EXISTS`。
  - 提供小工具函数：`query_one(sql, params)`、`query_all(sql, params)`、`execute(sql, params)`（返回 `lastrowid`），全部使用 `?` 占位参数化。
- [x] Run: `pytest tests/test_models.py -q`
  - Expected: PASS。

**安全/边界说明：** 所有 SQL 必须参数化，禁止 f-string/`%` 拼接；`models` 不得包含业务规则（如"只能改自己的笔记"由蓝图负责）。

---

## Task 4: 前端公共资产（设计令牌、请求封装、静态素材）

**目标：** 落地设计契约的视觉令牌，提供带统一错误提示的请求封装，就位背景素材与图标。

**文件：**
- 新建：`static/css/common.css`
- 新建：`static/js/api.js`
- 复制：`static/img/个人笔记主页.jpg`、`static/img/个人笔记-笔记背景.jpg`（从 `图片素材/`）
- 新建：`static/img/logo.svg`
- 修改：`templates/index.html`（引用 `common.css`，验证令牌生效）

**步骤：**
- [x] 复制两张背景素材到 `static/img/`（文件名保持中文，与 HTML 引用一致）。
- [x] 写 `static/css/common.css`：
  - `:root` 定义契约 10.3 的 10 个颜色角色变量：`--color-primary:#A8894F`、`--color-primary-hover:#937743`、`--color-heading:#3D3028`、`--color-text:#5C4B3A`、`--color-muted:#8C7B66`、`--color-bg:#FDFCF9`、`--color-surface:#FFFFFF`、`--color-border:#E8E2D6`、`--color-success-bg:#E8F0E4`、`--color-success-text:#5B7A52`、`--color-danger:#C0504D`。
  - 字体栈：标题 `--font-heading: "Noto Serif SC","Source Han Serif SC",Georgia,serif`；正文 `--font-body: "Microsoft YaHei","PingFang SC",system-ui,sans-serif`。
  - 间距基数 `--space-1..--space-6`（4/8/12/16/24/32/48）；圆角 `--radius-card:8px`、`--radius-control:6px`、`--radius-pill:12px`；阴影 `--shadow-card:0 2px 12px rgba(160,140,110,.12)`、`--shadow-modal:0 12px 40px rgba(90,70,40,.22)`。
  - 全局骨架样式：`.app-nav`（固定顶栏）、`.app-main`（`max-width:1100px;margin:0 auto`）、`.app-footer`（文案「用心记录，让知识更有价值。© 个人笔记」）、`.btn`/`.btn-primary`/`.btn-ghost`、`.card`、`.tag`/`.tag-published`、`.toast`、`.empty-state`、`.skeleton`。
  - `:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }`；`@media (prefers-reduced-motion: reduce)` 关闭过渡动画。
  - 页面背景类：`.bg-parchment { background: url("../img/个人笔记-笔记背景.jpg") center/cover fixed; }`。
- [x] 写 `static/js/api.js`：
  - `request(method, url, {json, formData})`：`fetch` 带 `credentials:'include'`；`json` 时设 `Content-Type: application/json`；解析 `{code,message,data}`；`code!=='OK'` 时调用 `toast(message,'error')` 并 `throw new Error(message)`；网络异常时 `toast('网络异常，请检查连接','error')`。
  - 导出 `toast(message, type)`：右下角提示，2.5s 自动消失。
  - 导出便捷方法 `api.get/post/put/del` 与 `api.upload(file)`。
  - 导出 `escapeHtml(s)`，供页面渲染用户文本时转义。
- [x] 修改 `templates/index.html` 引用 `common.css` 与 `logo.svg`，搭出骨架（导航 + 内容区 + 页脚）。
- [x] Run: `python app.py` 后浏览器打开 `http://127.0.0.1:5000/`
  - Expected: 页面使用暖米色底、主色按钮、衬线标题；导航与页脚结构可见。

**视觉验证：** 在 1440px 与 375px 两档宽度打开占位主页，确认：主色按钮为 `#A8894F`、页面底色 `#FDFCF9`、标题为衬线体、内容区宽度不超过 1100px 且居中、窄屏下无横向滚动条。截图留档。

---

## 阶段完成检查清单

- [x] 全部任务完成
- [x] `pytest -q` 全部通过
- [x] `python app.py` 可启动，`/api/health` 与页面均可访问
- [x] `common.css` 令牌与契约 10.3 数值逐项一致
- [x] `notes.db`、`.env` 已加入 `.gitignore`
- [x] 准备好进入 Phase 2
