# Phase 4: 图片上传与分享

**目标：** 完成图片上传接口与编辑器接线，完成分享开关/密码接口、详情页分享设置面板与公开分享页。
**前置条件：** Phase 3 完成（编辑器与详情页已存在）。
**交付物：** `blueprints/upload.py`、`blueprints/share.py`；编辑器插图能力；详情页分享设置面板；`share.html` 公开分享页与密码校验流程。

**本阶段实现的界面决策：** 契约 10.1 旅程 3（分享）；契约 10.2 详情页「分享设置」卡（开关 + 链接 + 复制 + 密码 + 保存）与分享页布局；契约 10.4 分享面板的未开启/已开启/复制成功/密码保存成功状态、按钮「已复制」反馈；契约 10.5 分享链接换行显示。

---

## Task 1: 图片上传接口（TDD）

**目标：** 实现 `POST /api/upload`，完成扩展名白名单、大小限制、随机重命名与按年月分目录。

**文件：**
- 新建：`blueprints/upload.py`
- 修改：`app.py`（注册 upload 蓝图）
- 测试：`tests/test_upload.py`

**步骤：**
- [ ] 写失败测试 `tests/test_upload.py`（用 `io.BytesIO` 构造 `FileStorage`）：
  - `test_upload_png_ok`：上传合法 png → `code=OK`，`data.url` 以 `/static/uploads/` 开头且以 `.png` 结尾，磁盘存在该文件。
  - `test_upload_rejects_bad_extension`：上传 `evil.exe` → 400 `FILE_ERROR`。
  - `test_upload_rejects_oversize`：构造 5MB+1 字节文件 → 400 `FILE_ERROR`。
  - `test_upload_requires_login`：未登录 → 401 `UNAUTHORIZED`。
  - `test_upload_filename_is_randomized`：两次上传同名文件得到不同 url，且 url 不含原始文件名。
- [ ] Run: `pytest tests/test_upload.py -q`
  - Expected: FAIL。
- [ ] 实现 `blueprints/upload.py`：
  - `login_required`；仅接受 `multipart/form-data` 的 `file` 字段，缺失 → `PARAM_ERROR`。
  - 取 `secure_filename` 后的扩展名小写化，白名单 `{jpg, jpeg, png, gif, webp}`，否则 `FILE_ERROR`。
  - 读取内容长度校验 ≤ `config.UPLOAD_MAX_SIZE`（5MB），超限 `FILE_ERROR`。
  - 落盘路径 `static/uploads/<YYYY>/<MM>/<uuid4hex>.<ext>`（目录不存在则创建），返回 `ok({"url": "/static/uploads/YYYY/MM/xxxx.png"})`（使用正斜杠）。
- [ ] 在 `app.py` 注册 upload 蓝图。
- [ ] Run: `pytest tests/test_upload.py -q`
  - Expected: PASS。

**安全/边界说明：** 不信任前端文件名；随机重命名消除路径穿越与覆盖风险；上传目录不放任何可执行内容；测试使用临时 `UPLOAD_DIR`。

---

## Task 2: 编辑器接入图片上传

**目标：** 让工具栏「图片」按钮完成「选文件 → 上传 → 在光标处插入 `![](url)`」。

**文件：**
- 修改：`templates/editor.html`（加入隐藏 `<input type="file">`）
- 修改：`static/js/editor.js`
- 修改：`static/js/api.js`（若 `api.upload` 尚未落地则补充）

**步骤：**
- [ ] 在 `editor.html` 加隐藏文件输入：`accept="image/jpeg,image/png,image/gif,image/webp"`。
- [ ] 在 `editor.js` 为「图片」按钮绑定：点击 → 触发文件选择 → 选中后按钮进入禁用并显示「上传中…」→ 调 `api.upload(file)`（`POST /api/upload`，`FormData` 字段名 `file`）→ 成功后在光标处插入 `![文件名](url)` → 失败时 `toast` 显示接口 `message`（如「仅支持 jpg/png/gif/webp，且不超过 5MB」）→ 恢复按钮。
- [ ] Run: `python app.py` 手测：
  - 选一张 png → 正文出现 `![](/static/uploads/...png)`，预览能看到图片。
  - 选一个 `.txt`（前端 `accept` 可被绕过，用手动构造或改名测试）→ 显示中文错误提示。
  - 未登录时上传 → 提示后跳登录页。

**视觉验证：** 上传中按钮态可见；插入后预览区图片宽度不超过卡片宽度（1440px 与 375px 各验一次）。

---

## Task 3: 分享开关与密码接口（TDD）

**目标：** 实现 `PUT /api/notes/<id>/share`，支持开启/关闭分享、设置/移除密码，并生成/失效 token。

**文件：**
- 修改：`blueprints/notes.py`（新增 `set_share` 与 `set_comment` 两个路由）
- 测试：`tests/test_share.py`

**步骤：**
- [ ] 写失败测试 `tests/test_share.py`：
  - `test_enable_share_generates_token`：`{enabled:true}` → `is_shared=1`、`share_token` 非空、`has_password=false`。
  - `test_enable_share_with_password`：`{enabled:true,password:"pass123"}` → `has_password=true`，库中 `share_password_hash` 非明文。
  - `test_disable_share_clears_token`：关闭后 `is_shared=0`、`share_token` 为空。
  - `test_share_requires_owner`：他人操作 → 403 `FORBIDDEN`。
  - `test_short_password_rejected`：密码 <6 位 → `PARAM_ERROR`。
- [ ] Run: `pytest tests/test_share.py -q`
  - Expected: FAIL。
- [ ] 在 `blueprints/notes.py` 实现 `set_share(id)`（`login_required` + 归属校验，路由 `PUT /api/notes/<id>/share`）：
  - `enabled=true`：若已有 token 则复用，否则 `uuid4().hex`；`password` 传非空字符串则校验 ≥6 位后 `generate_password_hash` 存入，传 `null` 表示移除密码，字段缺省表示不改动密码。
  - `enabled=false`：`is_shared=0`、`share_token=NULL`、`share_password_hash=NULL`。
  - 返回 `ok({"is_shared":bool,"share_token":str|null,"share_url":"/share.html?token=...","has_password":bool})`。
- [ ] 在 `blueprints/notes.py` 实现 `set_comment(id)`（路由 `PUT /api/notes/<id>/comment-setting`，体 `{enabled}`），返回 `ok({"comments_enabled":bool})`。
- [ ] 在 `app.py` 注册 share 蓝图时只覆盖公开读取路由：`share_bp` 的 `url_prefix="/api/share"`（其路由在 Task 4 实现）；`set_share`/`set_comment` 随 `notes_bp`（`/api/notes`）一起注册，与设计文档 9.4 的路径一致。
- [ ] Run: `pytest tests/test_share.py -q`
  - Expected: PASS。

**安全/边界说明：** 分享密码必须哈希存储；关闭分享即令 token 失效，避免旧链接继续可读。

---

## Task 4: 公开分享读取接口（TDD）

**目标：** 实现 `GET /api/share/<token>`（元信息）与 `POST /api/share/<token>`（校验密码取正文）。

**文件：**
- 修改：`blueprints/share.py`
- 测试：`tests/test_share.py`（追加）

**步骤：**
- [ ] 追加失败测试：
  - `test_share_meta_no_password`：无密码分享 → `GET` 返回 `need_password=false`，且**不含** `content`。
  - `test_share_meta_with_password`：有密码分享 → `need_password=true`。
  - `test_share_meta_invalid_token`：随机 token → 404 `NOT_FOUND`。
  - `test_share_meta_disabled`：关闭分享后原 token → 404 `NOT_FOUND`。
  - `test_read_no_password_ok`：`POST` 空体 → 返回正文与 `{id,title,content,author,comments_enabled,favorited,is_owner}`。
  - `test_read_wrong_password`：`POST {password:"wrong"}` → 403 `WRONG_PASSWORD`。
  - `test_read_correct_password`：返回正文。
  - `test_share_read_logged_in_favorited_flag`：已登录且已收藏时 `favorited=true`；未登录时固定 `false`。
- [ ] Run: `pytest tests/test_share.py -q`
  - Expected: FAIL。
- [ ] 实现：
  - `GET /api/share/<token>`：按 token 且 `is_shared=1` 查笔记；不存在 → `NOT_FOUND`；返回 `{title, author, need_password, created_at, updated_at}`（**不含 content**）。
  - `POST /api/share/<token>`：同上查笔记；`has_password` 为真且 `check_password_hash` 失败 → `WRONG_PASSWORD`；成功返回设计文档 9.7 的完整结构；`favorited` 依据 `session` 中是否有登录用户计算；`is_owner` 同理。
  - 抽公共函数 `_find_shared_note(token)` 供两个接口复用。
- [ ] Run: `pytest tests/test_share.py -q`
  - Expected: PASS。

**安全/边界说明：** 元信息接口绝不返回正文与密码哈希；密码校验失败不提示具体原因。

---

## Task 5: 详情页分享设置面板 + 公开分享页

**目标：** 在详情页交付分享设置面板，并交付 `share.html` 完成密码校验与正文阅读。

**文件：**
- 修改：`templates/note.html`、`static/js/note.js`、`static/css/note.css`
- 新建：`templates/share.html`
- 新建：`static/js/share.js`
- 修改：`app.py`（新增 `/share.html` 路由，或直接由静态托管）

**步骤：**
- [ ] 在 `note.html` 的 `#share-panel` 内实现：标题「分享设置」+ 右侧「收起/展开」；开启开关（toggle）；开启后显示只读链接输入框（`share.html?token=...` 的完整地址）+「复制」按钮；下方密码输入框（占位「输入新密码（留空移除）」）+「保存密码」按钮。
- [ ] 在 `note.js` 实现：
  - `PUT /api/notes/<id>/share` 的开启/关闭、保存密码三种调用；开关切换后即时反映链接区显隐。
  - 「复制」用 `navigator.clipboard.writeText`，成功后按钮文案变「已复制」并在 1.5s 后复原；失败回退为选中文本提示手动复制。
  - 布局按契约 10.5：窄屏下链接换行显示且复制按钮仍可点。
- [ ] 新建 `templates/share.html`：顶部精简导航（仅 logo + 「个人笔记」+ 登录/注册或用户名）；中间正文卡片；底部需要密码时先显示密码表单（输入框 + 「查看」按钮 + 错误提示位）。
- [ ] 写 `static/js/share.js`：
  - 从 `location.search` 取 `token`，缺失则显示「链接无效」。
  - `GET /api/share/<token>` 拿元信息：404 → 显示「资源不存在或分享已关闭」；`need_password=false` → 直接 `POST` 取正文渲染；`true` → 显示密码表单。
  - `POST /api/share/<token>` 成功后渲染标题、作者、时间与正文（复用 `renderMarkdown`），并启用评论区占位（Phase 5 填充）与「收藏」按钮占位（Phase 5 填充）。
  - `WRONG_PASSWORD` → 表单保留输入并显示「分享密码错误」，允许重试；未登录点「收藏/评论」→ 跳 `/login?next=<当前地址>`。
- [ ] 新增 `/share.html` 页面路由（`send_from_directory("templates","share.html")`）。
- [ ] Run: `python app.py` 手测：
  - 开启无密码分享 → 无痕窗口打开链接可直接读到正文。
  - 设置密码后重新打开 → 先要求密码，输入错误提示「分享密码错误」，输入正确显示正文。
  - 详情页点「复制」→ 剪贴板得到完整链接。
  - 关闭分享 → 原链接显示「资源不存在或分享已关闭」。

**视觉验证：** 1440px 下分享卡片居中、正文排版与详情页一致；375px 下链接文本换行不溢出、密码表单整行可用。截图留档（分享设置面板展开态、分享页密码态、分享页正文态各一张）。

---

## 阶段完成检查清单

- [ ] 全部任务完成
- [ ] `pytest -q` 全绿（新增 upload 与 share 用例）
- [ ] 上传/分享/评论开关的接口契约与设计文档 9.4/9.7/9.8 一致
- [ ] 分享页在无密码、有密码、错误密码、失效 token 四种情况下表现正确
- [ ] 视觉验证截图已留档
- [ ] 准备好进入 Phase 5
