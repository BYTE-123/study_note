# Phase 2: 认证模块

**目标：** 完成注册、登录、登出、当前用户四个接口与登录校验装饰器，交付登录页与注册页。
**前置条件：** Phase 1 完成（骨架、统一响应、models、common.css、api.js）。
**交付物：** `blueprints/auth.py`、`utils/auth_guard.py`、`templates/login.html`、`templates/register.html`、`templates/index.html`（主页落地页）、`static/js/auth.js`、`static/js/nav.js`、`static/css/form.css`、`static/css/home.css`；pytest 覆盖认证全部分支。

**本阶段实现的界面决策：** 契约 10.2 主页「记录生活 · 书写成长」布局与四大特性块、全局骨架；契约 10.1 旅程 1（首次到访 → 开始记录 → 注册 → 自动登录 → 工作台）；契约 10.4 输入框的默认/聚焦/错误状态与中文提示、按钮加载中状态。

---

## Task 1: 注册接口（TDD）

**目标：** 实现 `POST /api/auth/register`，完成全部参数校验、唯一性冲突与密码哈希。

**文件：**
- 新建：`blueprints/auth.py`
- 修改：`app.py`（注册 auth 蓝图）
- 测试：`tests/test_auth.py`

**步骤：**
- [ ] 写失败测试 `tests/test_auth.py`：

```python
def test_register_ok(client):
    r = client.post("/api/auth/register", json={
        "email": "a@b.com", "username": "阿明",
        "password": "123456", "confirm_password": "123456"})
    assert r.status_code == 200
    assert r.get_json()["code"] == "OK"
    assert r.get_json()["data"]["username"] == "阿明"

def test_register_duplicate_email(client):
    payload = {"email":"a@b.com","username":"阿明","password":"123456","confirm_password":"123456"}
    client.post("/api/auth/register", json=payload)
    r = client.post("/api/auth/register", json={**payload, "username":"小明"})
    assert r.status_code == 409
    assert r.get_json()["code"] == "CONFLICT"
    assert r.get_json()["message"] == "邮箱已被注册"

def test_register_duplicate_username(client):
    payload = {"email":"a@b.com","username":"阿明","password":"123456","confirm_password":"123456"}
    client.post("/api/auth/register", json=payload)
    r = client.post("/api/auth/register", json={**payload, "email":"c@d.com"})
    assert r.get_json()["code"] == "CONFLICT"
    assert r.get_json()["message"] == "昵称已被占用"

def test_register_bad_email(client):
    r = client.post("/api/auth/register", json={
        "email":"not-an-email","username":"阿明","password":"123456","confirm_password":"123456"})
    assert r.get_json()["code"] == "PARAM_ERROR"

def test_register_password_mismatch(client):
    r = client.post("/api/auth/register", json={
        "email":"a@b.com","username":"阿明","password":"123456","confirm_password":"654321"})
    assert r.get_json()["code"] == "PARAM_ERROR"

def test_register_short_password(client):
    r = client.post("/api/auth/register", json={
        "email":"a@b.com","username":"阿明","password":"123","confirm_password":"123"})
    assert r.get_json()["code"] == "PARAM_ERROR"

def test_register_username_length(client):
    r = client.post("/api/auth/register", json={
        "email":"a@b.com","username":"x","password":"123456","confirm_password":"123456"})
    assert r.get_json()["code"] == "PARAM_ERROR"
```
- [ ] Run: `pytest tests/test_auth.py -q`
  - Expected: FAIL（404，蓝图未注册）。
- [ ] 实现 `blueprints/auth.py` 的 `register()`：
  - 校验：四字段非空；邮箱正则 `^[^@\s]+@[^@\s]+\.[^@\s]+$`；用户名 2–20 字符；密码 ≥6 位；两次密码一致。任一不满足 → `fail("PARAM_ERROR", <具体中文>)`。
  - 查重：邮箱已存在 → `CONFLICT / 邮箱已被注册`；用户名已存在 → `CONFLICT / 昵称已被占用`。
  - 写入：`password_hash = generate_password_hash(password)`，`created_at = datetime.now().isoformat(timespec="seconds")`；插入 `users`。
  - 返回 `ok({"id": uid, "email": email, "username": username})`。
- [ ] 在 `app.py` 注册蓝图：`app.register_blueprint(auth_bp, url_prefix="/api/auth")`。
- [ ] Run: `pytest tests/test_auth.py -q`
  - Expected: PASS（7 passed）。

**安全/边界说明：** 密码只存哈希；不得在响应或日志中回显密码；查重与插入之间依赖唯一约束兜底，捕获 `sqlite3.IntegrityError` 转 `CONFLICT`。

---

## Task 2: 登录、登出、当前用户与鉴权装饰器

**目标：** 完成 `POST /api/auth/login`、`POST /api/auth/logout`、`GET /api/auth/me`，并提供 `login_required` 装饰器供后续所有模块复用。

**文件：**
- 修改：`blueprints/auth.py`
- 新建：`utils/auth_guard.py`
- 测试：`tests/test_auth.py`（追加）

**步骤：**
- [ ] 追加失败测试：
```python
def test_login_ok_and_me(client):
    client.post("/api/auth/register", json={
        "email":"a@b.com","username":"阿明","password":"123456","confirm_password":"123456"})
    r = client.post("/api/auth/login", json={"email":"a@b.com","password":"123456"})
    assert r.get_json()["code"] == "OK"
    me = client.get("/api/auth/me")
    assert me.get_json()["data"]["username"] == "阿明"

def test_login_wrong_password(client):
    client.post("/api/auth/register", json={
        "email":"a@b.com","username":"阿明","password":"123456","confirm_password":"123456"})
    r = client.post("/api/auth/login", json={"email":"a@b.com","password":"000000"})
    assert r.status_code == 400
    assert r.get_json()["code"] == "PASSWORD_ERROR"

def test_login_unknown_email_same_message(client):
    r = client.post("/api/auth/login", json={"email":"no@b.com","password":"123456"})
    assert r.get_json()["code"] == "PASSWORD_ERROR"
    assert r.get_json()["message"] == "邮箱或密码错误"

def test_me_requires_login(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.get_json()["code"] == "UNAUTHORIZED"

def test_logout_clears_session(client):
    client.post("/api/auth/register", json={
        "email":"a@b.com","username":"阿明","password":"123456","confirm_password":"123456"})
    client.post("/api/auth/login", json={"email":"a@b.com","password":"123456"})
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").get_json()["code"] == "UNAUTHORIZED"
```
- [ ] Run: `pytest tests/test_auth.py -q`
  - Expected: FAIL（login/me/logout 未实现）。
- [ ] 写 `utils/auth_guard.py`：
  - `current_user_id()`：从 `session.get("user_id")` 读取，无则返回 `None`。
  - `login_required(fn)`：包装函数，未登录直接 `fail("UNAUTHORIZED")`，已登录把 `user_id` 以关键字参数传入原函数。
- [ ] 在 `auth.py` 实现：
  - `login()`：按邮箱查用户；不存在或 `check_password_hash` 失败一律 `fail("PASSWORD_ERROR")`；成功则 `session["user_id"]=uid`，返回 `ok({id,email,username})`。
  - `logout()`：`session.clear()`，返回 `ok(None, "已退出登录")`；用 `login_required` 保护。
  - `me()`：用 `login_required`，按 id 查用户返回 `{id,email,username,bio}`；查不到时清 Session 并 `UNAUTHORIZED`。
- [ ] Run: `pytest tests/test_auth.py -q`
  - Expected: PASS（12 passed）。

**安全/边界说明：** 登录失败不区分账号不存在与密码错误；Session 配置 `SESSION_COOKIE_HTTPONLY=True`、`SESSION_COOKIE_SAMESITE='Lax'`（在 `config.py` 设置）。

---

## Task 3: 登录页与注册页

**目标：** 交付 `login.html` 与 `register.html`，完成表单校验、错误提示与登录后跳转。

**文件：**
- 新建：`templates/login.html`、`templates/register.html`
- 新建：`static/css/form.css`
- 新建：`static/js/auth.js`
- 修改：`app.py`（新增 `/login`、`/register` 页面路由）

**步骤：**
- [ ] 在 `app.py` 增加页面路由 `/login`、`/register`，用 `send_from_directory("templates", ...)` 返回对应 HTML。
- [ ] 写 `static/css/form.css`：居中窄卡片（最大宽 420px）、输入框默认/聚焦（主色描边）/错误（`--color-danger` 描边 + 下方 13px 中文提示）、主按钮整行、次要文字链接；复用 `common.css` 令牌与 `.bg-parchment`。
- [ ] 写 `templates/login.html`：字段「邮箱」「密码」+ 主按钮「登录」+ 底部「还没有账号？去注册」链接；引用 `common.css`、`form.css`、`api.js`、`auth.js`。
- [ ] 写 `templates/register.html`：字段「邮箱」「用户名」「密码」「确认密码」+ 主按钮「注册」+ 底部「已有账号？去登录」链接。
- [ ] 写 `static/js/auth.js`：
  - 客户端预校验：注册页校验邮箱格式、用户名 2–20、密码 ≥6、两次一致，不通过则在对应输入框下显示中文提示且不发请求。
  - 提交时按钮进入禁用 + 「登录中…」/「注册中…」文案。
  - 成功后：注册页自动调用登录接口，再跳 `/workbench`；登录页直接跳 `/workbench`（`?next=` 存在且以 `/` 开头时优先）。
  - 失败：按钮恢复，错误提示显示在表单顶部（文案取接口 `message`）。
  - 页面加载时调用 `GET /api/auth/me`，已登录则直接跳 `/workbench`。
- [ ] Run: `python app.py`，在浏览器手测：
  - 空提交 → 输入框下出现中文提示，无网络请求。
  - 邮箱格式错误 → 提示「请输入正确的邮箱地址」。
  - 密码不一致 → 提示「两次输入的密码不一致」。
  - 用已注册邮箱提交 → 顶部显示「邮箱已被注册」。
  - 正确提交 → 跳转 `/workbench`（此阶段该页未实现，允许 404，但跳转动作发生）。
- [ ] Run: `python app.py` 并用错误密码登录
  - Expected: 顶部显示「邮箱或密码错误」。

**视觉验证：** 1440px 下表单卡片居中、输入框聚焦为主色描边；375px 下卡片占满宽度且不溢出；错误态输入框为红描边并带中文提示。截图留档（正常态 + 错误态各一张）。

---

## Task 4: 主页落地页

**目标：** 交付 `index.html`，实现「满幅背景 + 左文右景」的主页，并把「开始记录」接到注册/工作台。

**文件：**
- 修改：`templates/index.html`（替换 Phase 1 的占位内容）
- 新建：`static/css/home.css`
- 新建：`static/js/home.js`
- 修改：`static/js/nav.js`（如主页导航形态与内页不同，则在此处理）

**步骤：**
- [ ] 写 `templates/index.html`：顶部导航（未登录「登录 / 注册 / 关于」，已登录「我的文章 / 个人主页 / 关于」）；主区左侧为主标题「记录生活 · 书写成长 / 遇见美好」、主色短横线、副文案「个人笔记是一款简洁优雅的在线笔记应用，帮助你随时随地记录灵感、管理任务、沉淀思考，让每一个想法都被珍藏，让每一天都更有意义。」、两个按钮「✎ 开始记录」（主）与「▷ 了解更多」（次）；下方四个特性块（`简洁易用`、`云端同步`、`隐私保护`、`灵活分类`）各配线性图标与一行说明；页脚。
- [ ] 文案诚实性要求：四个特性**标题沿用截图 01**，但描述按真实能力撰写，避免宣称未实现的能力——`简洁易用`→「界面清新，专注记录」；`云端同步`→「账号登录，多端可读」（说明数据存于服务器，非实时同步）；`隐私保护`→「默认仅自己可见，分享需显式开启」（不写「数据加密」）；`灵活分类`→「标签管理，高效查找」。
- [ ] 写 `static/css/home.css`：首屏 `min-height:100vh`，`background: url("../img/个人笔记主页.jpg") center/right no-repeat` 且 `background-size:cover`；左侧文案区限宽约 520px、与背景右侧的咖啡/笔记本主体错开；主标题 44px/行高 1.25 衬线字，窄屏降到 30px；短横线为主色 3px×48px；两个按钮按契约按钮样式（主按钮填充 `--color-primary`，次按钮白底描边）；特性区四列等距，图标 32px 线性主色。
- [ ] 写 `static/js/home.js`：调 `GET /api/auth/me` 后渲染导航；「开始记录」按登录态跳 `/workbench` 或 `/register`；「了解更多」平滑滚动到特性区（若特性区在当前列表下方则滚动，否则跳 `/about`）。
- [ ] Run: `python app.py` 手测：
  - 未登录打开主页 → 导航为「登录 / 注册 / 关于」，「开始记录」跳 `/register`。
  - 登录后打开主页 → 导航为「我的文章 / 个人主页 / 关于」，「开始记录」跳 `/workbench`。
  - 点击「了解更多」滚动到特性区。

**视觉验证：** 1440px 下背景图右侧主体（咖啡杯与笔记本）完整可见、文案不与主体重叠；768px 下文案区与背景仍可读（必要时给文案区加半透明浅色底）；375px 下主标题不溢出、两个按钮换行或整行铺满、四个特性块单列堆叠。截图留档（主页 1440 与 375 各一张），与截图 `01个人笔记-主页截图.png` 对比核对。

---

## 阶段完成检查清单

- [ ] 全部任务完成
- [ ] `pytest tests/test_auth.py -q` 全部通过
- [ ] `pytest -q` 全绿（含 Phase 1 用例）
- [ ] 登录/注册页与契约 10.4 的输入框、按钮状态一致
- [ ] 主页与截图 01 的结构一致，四个特性文案不夸大未实现的能力
- [ ] 浏览器手测通过列表逐条核对完成
- [ ] 准备好进入 Phase 3
