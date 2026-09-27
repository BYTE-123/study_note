# Phase 3: 笔记核心

**目标：** 完成笔记增删改查、统计与最近文章接口，交付工作台、我的文章、编辑器、笔记详情四个页面与 Markdown 渲染。
**前置条件：** Phase 2 完成（登录态与鉴权装饰器可用）。
**交付物：** `blueprints/notes.py`；`workbench.html`、`notes.html`、`editor.html`、`note.html` 及其 CSS/JS；`marked` 本地引入与安全的 Markdown 渲染。

**本阶段实现的界面决策：** 契约 10.2 的工作台三统计卡、我的文章列表、编辑器「标题 + 标签 + 工具栏 + 正文 + 预览」、详情页「标题 + 状态标签 + 编辑/删除 + 正文卡片」；契约 10.3 羊皮纸背景在内页铺底；契约 10.4 列表加载/空/失败态、编辑器占位文案、Markdown 工具栏插入语法与预览；契约 10.1 旅程 2（写作发布）。

---

## Task 1: 笔记 CRUD 与归属校验（TDD）

**目标：** 实现笔记的新增、查询列表、详情、更新、删除，并保证只能操作自己的笔记。

**文件：**
- 新建：`blueprints/notes.py`
- 修改：`app.py`（注册 notes 蓝图）
- 测试：`tests/test_notes.py`

**步骤：**
- [x] 写失败测试 `tests/test_notes.py`（需要一个已登录用户夹具，在文件中定义 `login(client)` 辅助函数完成注册+登录）：
  - `test_create_note_ok`：创建返回 `data.id`，状态默认 `draft`（未传 status 时）。
  - `test_create_note_empty_title_defaults`：`title` 为空字符串 → 存为「无标题」。
  - `test_list_own_notes_only`：用户 A 建 2 篇、用户 B 建 1 篇，A 列表只返回 2 篇。
  - `test_list_filter_by_status_and_keyword`：按 `status=published` 与 `keyword` 过滤结果正确。
  - `test_detail_returns_full_fields`：返回含 `content`、`has_password`、`favorited`、`is_owner`。
  - `test_update_note`：标题与正文被更新，`updated_at` 变大。
  - `test_update_others_note_forbidden`：B 改 A 的笔记 → 403 `FORBIDDEN`。
  - `test_delete_others_note_forbidden` / `test_delete_own_note_ok`。
  - `test_notes_require_login`：未登录访问 `GET /api/notes` → 401 `UNAUTHORIZED`。
  - `test_list_summary_strips_markdown`：正文 `# 标题\n正文内容` 的 `summary` 不含 `#`，长度 ≤ 80。
- [x] Run: `pytest tests/test_notes.py -q`
  - Expected: FAIL（蓝图未实现）。
- [x] 实现 `blueprints/notes.py`：
  - 所有接口用 `login_required`。
  - `create()`：校验 `title` 长度 ≤100（空则存「无标题」）、`content` 任意、`tags` 长度 ≤100、`status ∈ {draft, published}`（默认 `draft`）；插入后返回 `ok({"id": uid})`。发布时写 `published_at`（若无此列则用 `status` 判断即可，不额外加列）。
  - `list()`：参数 `status`(draft/published/all，默认 all)、`keyword`（匹配标题或正文）、`tag`、`page`(默认 1)、`page_size`(默认 `config.PAGE_SIZE`)；仅 `user_id = 当前用户`；返回 `{total, page, page_size, items:[{id,title,summary,tags,status,is_shared,created_at,updated_at}]}`。
  - `detail(id)`：仅作者本人（非作者返回 `FORBIDDEN`）；不存在返回 `NOT_FOUND`；返回设计文档 9.4 的完整结构（`has_password` 由 `share_password_hash` 是否为空推导）。
  - `update(id)`：归属校验后更新 `title/content/tags/status` 与 `updated_at`。
  - `delete(id)`：归属校验后删除（依赖 `ON DELETE CASCADE` 清理评论与收藏）。
  - 工具函数 `strip_markdown(text)`：去掉 `#`、`*`、`>`、反引号、图片/链接语法后取前 80 字作为 `summary`。
- [x] 在 `app.py` 注册 `notes_bp`（`url_prefix="/api/notes"`）。
- [x] Run: `pytest tests/test_notes.py -q`
  - Expected: PASS。

**安全/边界说明：** 归属校验放在每个按 id 操作的接口最前面；错误顺序为「未登录 401 → 不存在 404 → 非本人 403」；`FORBIDDEN` 不泄漏笔记是否存在（非本人且不存在时统一返回 `NOT_FOUND`）。

---

## Task 2: 统计与最近文章接口

**目标：** 为工作台提供 `GET /api/notes/stats` 与 `GET /api/notes/recent`。

**文件：**
- 修改：`blueprints/notes.py`
- 测试：`tests/test_notes.py`（追加）

**步骤：**
- [x] 追加失败测试：
  - `test_stats_counts`：构造 1 草稿、1 已发布、1 收藏 → `{draft:1, published:1, favorite:1}`。
  - `test_recent_limit_and_order`：创建 3 篇，`limit=2` 返回 2 篇且按 `updated_at` 倒序。
- [x] Run: `pytest tests/test_notes.py -q`
  - Expected: FAIL。
- [x] 实现：
  - `stats()`：三条 `COUNT` 查询（`favorite` 统计 `favorites` 表中 `user_id=当前用户` 的记录数）。
  - `recent()`：读取 `limit`（默认 5，上限 20），按 `updated_at DESC` 返回 `[{id,title,status,updated_at}]`。
- [x] Run: `pytest tests/test_notes.py -q`
  - Expected: PASS。

---

## Task 3: 工作台页与我的文章列表页

**目标：** 交付 `workbench.html` 与 `notes.html`，完成统计展示、最近文章、列表筛选与分页。

**文件：**
- 新建：`templates/workbench.html`、`templates/notes.html`
- 新建：`static/css/workbench.css`
- 新建：`static/js/workbench.js`、`static/js/notes.js`
- 修改：`app.py`（新增 `/workbench`、`/notes` 路由）
- 修改：`static/css/common.css`（补充 `.app-nav` 的登录态两种形态）

**步骤：**
- [x] 新增页面路由 `/workbench` 与 `/notes`。
- [x] 写 `static/css/workbench.css`：内页统一用 `.bg-parchment`；统计区 `.stat-grid` 三列（`gap:24px`），`.stat-card` 白底圆角 8px + `--shadow-card`，数字为衬线大字 32px、下方 13px `--color-muted` 标签；`.panel` 白底卡片承载「最近文章」。
- [x] 写 `templates/workbench.html`：`<h1>工作台</h1>` + 右侧「新建文章」（主按钮，跳 `/editor`）与「我的文章」（次按钮，跳 `/notes`）；统计三卡（草稿/已发布/收藏）；「最近文章」卡片，空时显示 `还没有笔记，点击「新建文章」开始记录吧`。
- [x] 写 `templates/notes.html`：顶部状态筛选（全部/草稿/已发布）+ 关键词输入 + 提交；下方文章列表，每项显示标题、`summary`、标签、状态标签、`updated_at`；底部分页（上一页/下一页 + 当前页）。空态同上文案。
- [x] 写 `static/js/workbench.js`：并发调 `stats` 与 `recent`；`is_shared` 为真时在最近文章项上追加「已分享」小标记；失败时在卡片内显示中文错误与「重试」按钮。
- [x] 写 `static/js/notes.js`：从 URL query 读筛选条件并写入表单；调用 `GET /api/notes`；列表渲染前用 `escapeHtml` 转义标题与摘要；状态标签用 `.tag-published`（已发布，绿底）或 `.tag`（草稿）；分页控件按 `total`/`page_size` 计算可用状态。
- [x] 所有页面顶部导航按登录态渲染：已登录显示「我的文章 / 个人主页 / 关于 / 退出」，未登录显示「登录 / 注册 / 关于」；新建 `static/js/nav.js`，导出 `renderNav(user)` 与 `initNav()`（内部调 `GET /api/auth/me` 后再渲染），供后续所有页面统一引用，避免每页重复实现。
- [x] Run: `python app.py` 手测：
  - 工作台显示真实统计数字，与 `/api/notes/stats` 返回一致。
  - 无笔记时显示空状态文案。
  - 列表页切换「草稿/已发布」筛选，结果随之变化。
  - URL 带 `?status=published` 直接打开时筛选器回填正确。

**视觉验证：** 1440px 下三统计卡同一行、间距 24px、阴影可见；375px 下统计卡单列堆叠且无横向滚动；工作台与列表页背景为羊皮纸素材。截图留档（工作台、列表空态、列表有数据各一张）。

---

## Task 4: 编辑器页（Markdown 工具栏、预览、保存草稿/发布）

**目标：** 交付 `editor.html`，支持新建与编辑、10 个工具栏按钮、预览切换、保存草稿与发布。

**文件：**
- 新建：`templates/editor.html`
- 新建：`static/css/editor.css`
- 新建：`static/js/editor.js`
- 新建：`static/js/vendor/marked.min.js`（本地引入）
- 修改：`app.py`（新增 `/editor` 路由）

**步骤：**
- [x] 下载 `marked` 的发行版放入 `static/js/vendor/marked.min.js`，并在 `editor.js` 顶部注释记录来源与版本。
- [x] 新增页面路由 `/editor`（编辑模式通过 `?id=` 区分）。
- [x] 写 `templates/editor.html`：顶部「← 返回」与右侧「保存草稿」「发布文章」；标题输入（占位「文章标题…」）；标签输入（占位「用逗号分隔，例如：生活,工作,随笔」）；工具栏 10 个按钮（H1、H2、加粗、斜体、行内代码、引用、无序列表、有序列表、链接、图片）与右侧「预览」按钮；正文 `textarea`（占位「开始书写你的笔记…」并附 Markdown 语法提示）；预览区默认隐藏。
- [x] 写 `static/css/editor.css`：白色编辑卡片、工具栏为浅色条（按钮悬停主色描边）、`textarea` 等宽友好字体且 `line-height:1.75`、预览区排版（标题衬线、引用左边框主色、行内代码浅底）。
- [x] 写 `static/js/editor.js`：
  - `insertSyntax(type)`：按当前 `selectionStart/selectionEnd` 在光标处包裹或加前缀，插入后光标定位到内容中间（各类型的模板：`# `、`## `、`**选中**`、`*选中*`、`` `选中` ``、`> `、`- `、`1. `、`[文字](url)`、`![描述](url)`）。
  - 预览切换：用 `marked.parse(md)` 渲染到预览区；渲染前对源文本先做 HTML 转义处理，渲染后再次清理 `script`/`on*` 属性，确保注入的原始 HTML 不执行。
  - 保存：收集标题/标签/正文；新建时 `POST`、编辑时 `PUT`；按钮进入禁用 + 「保存中…」；成功保存草稿提示「已保存」并保留在当前页，发布则跳 `/note?id=<id>`。
  - 编辑模式加载：`?id=` 存在时 `GET /api/notes/<id>` 回填三字段，并把按钮文案保持为「保存」语义（保存草稿 = `status:draft`，发布文章 = `status:published`）。
  - 未登录访问：`/api/notes/<id>` 或保存时收到 401，则 `toast` 提示后跳 `/login?next=/editor...`。
- [x] Run: `python app.py` 手测：
  - 10 个按钮逐个点击，正文插入语法正确、光标位置合理。
  - 输入 `# 标题`、`**加粗**`、`> 引用` 后点预览，渲染结果正确。
  - 在正文粘贴 `<script>alert(1)</script>` 后预览，**不弹窗**，脚本以文本呈现。
  - 「保存草稿」→ 工作台草稿数 +1；「发布文章」→ 跳详情页且状态为「已发布」。

**视觉验证：** 1440px 下编辑卡片居中、工具栏一行放得下；768px 下工具栏横向可滚动不换行错位；375px 下标题输入与正文占满宽度。截图留档（编辑态、预览态各一张）。

**安全/边界说明：** 预览渲染必须防 XSS；不得把用户正文直接拼进 `innerHTML`。

---

## Task 5: 笔记详情页

**目标：** 交付 `note.html`，展示渲染后的正文，提供编辑与删除入口；分享与评论区先留出占位容器供 Phase 4/5 填充。

**文件：**
- 新建：`templates/note.html`
- 新建：`static/css/note.css`
- 新建：`static/js/note.js`
- 修改：`app.py`（新增 `/note` 路由）

**步骤：**
- [x] 新增页面路由 `/note`。
- [x] 写 `templates/note.html`：「← 返回列表」；标题 + 状态标签（草稿/已发布，已发布用 `.tag-published`）+ 创建/更新时间（居中 `·` 分隔）；右侧「编辑」「删除」；正文卡片（渲染区）；`<section id="share-panel">` 与 `<section id="comment-panel">` 占位容器（本阶段只渲染空容器，不请求）。
- [x] 写 `static/css/note.css`：正文卡片白底圆角、`line-height:1.75`；正文内标题衬线、链接主色、引用左边框主色、代码块浅底等宽、图片最大宽 100%。
- [x] 写 `static/js/note.js`：
  - 从 `?id=` 读取并 `GET /api/notes/<id>`；渲染标题、状态、时间（格式 `YYYY-MM-DD HH:mm`）、正文（`marked` + 同一套 XSS 防护，抽为公共函数 `renderMarkdown(md)` 放入 `api.js` 以便复用）。
  - 「编辑」跳 `/editor?id=<id>`；「删除」弹出二次确认「删除后不可恢复，确定删除这篇笔记吗？」，确认后 `DELETE`，成功跳 `/notes` 并 `toast('已删除')`。
  - 401 时跳登录页；404 时显示「资源不存在」并提供返回列表按钮。
- [x] 复用并抽取 `renderMarkdown`（Task 4 与 Task 5 共用），避免重复实现。
- [x] Run: `python app.py` 手测：
  - 打开一篇含标题/列表/引用/代码/图片的笔记，渲染正确。
  - 删除后列表与工作台统计同步变化。
  - 直接打开 `/note?id=9999` → 显示「资源不存在」。

**视觉验证：** 1440px 下详情卡片居中、正文排版舒适（段间距与行高符合契约 10.3）；375px 下正文不溢出、图片自适应宽度。截图留档（详情页一张）。

---

## 阶段完成检查清单

- [x] 全部任务完成
- [x] `pytest -q` 全绿（认证 + 笔记）
- [x] 四个页面与截图 02/03/04 的结构一致
- [x] Markdown 预览经 XSS 用例验证不执行脚本
- [x] 列表空/加载/失败三态可达
- [x] 视觉验证截图已留档
- [x] 准备好进入 Phase 4
