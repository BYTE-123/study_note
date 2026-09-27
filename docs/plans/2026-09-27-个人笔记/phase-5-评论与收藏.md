# Phase 5: 评论与收藏

**目标：** 完成评论与收藏接口及界面，交付个人主页（个人信息 / 收藏 / 笔记历史）。
**前置条件：** Phase 4 完成（详情页与分享页已留出评论与收藏容器）。
**交付物：** `blueprints/comments.py`、`blueprints/favorites.py`；详情页与分享页的评论区；个人主页三块内容；`GET/PUT /api/profile`。

**本阶段实现的界面决策：** 契约 10.2 详情页评论区与个人主页布局、底部导航「个人主页」；契约 10.4 评论区全部状态（加载中/无评论/有评论/提交中/提交成功/超长提示）与空状态文案、收藏状态标签；契约 10.1 旅程 4（互动）与旅程 6（回看）。

---

## Task 1: 评论接口（TDD）

**目标：** 实现评论的查询、发表与删除，并遵守评论开关与作者归属规则。

**文件：**
- 新建：`blueprints/comments.py`
- 修改：`app.py`（注册 comments 蓝图）
- 测试：`tests/test_comments.py`

**步骤：**
- [x] 写失败测试 `tests/test_comments.py`：
  - `test_list_comments_empty`：`GET /api/notes/<id>/comments` → `{comments_enabled:true, items:[]}`，免登录可读。
  - `test_post_comment_ok`：登录后发表 → `code=OK`，再次 `GET` 列表长度为 1。
  - `test_post_comment_requires_login`：未登录 → 401 `UNAUTHORIZED`。
  - `test_post_comment_when_disabled`：作者关闭评论后 → 403 `FORBIDDEN`。
  - `test_post_comment_empty_or_too_long`：空内容或 >500 字 → `PARAM_ERROR`。
  - `test_delete_own_comment_ok`：删除自己评论 → `OK`，列表长度减 1。
  - `test_delete_others_comment_forbidden`：删他人评论 → 403 `FORBIDDEN`。
  - `test_comments_of_missing_note`：不存在笔记 → `NOT_FOUND`。
  - `test_comment_is_self_flag`：本人评论 `is_self=true`，他人评论 `false`。
- [x] Run: `pytest tests/test_comments.py -q`
  - Expected: FAIL。
- [x] 实现 `blueprints/comments.py`：
  - `list(note_id)`：免登录；笔记不存在 → `NOT_FOUND`；返回 `{comments_enabled, items:[{id, user:{id,username}, content, created_at, is_self}]}`，按 `created_at ASC`。
  - `create(note_id)`：`login_required`；评论开关关闭 → `FORBIDDEN / 评论已关闭`；内容去首尾空格后为空或 >500 字 → `PARAM_ERROR`；插入后返回 `ok({...新评论结构...})`。
  - `delete(comment_id)`：`login_required`；评论不存在 → `NOT_FOUND`；非本人 → `FORBIDDEN`；删除返回 `ok(None,"已删除")`。
- [x] 在 `app.py` 注册评论蓝图 `comments_bp`，`url_prefix="/api"`，蓝图内声明两条路由 `/notes/<int:note_id>/comments`（GET/POST）与 `/comments/<int:comment_id>`（DELETE），与设计文档 9.6 的路径一致。
- [x] Run: `pytest tests/test_comments.py -q`
  - Expected: PASS。

**安全/边界说明：** 评论内容渲染时在**前端**转义（后端存原文，渲染时用 `escapeHtml` 后再插入 DOM），不依赖后端裁剪 HTML。

---

## Task 2: 详情页与分享页评论区

**目标：** 在详情页与分享页交付可用的评论区。

**文件：**
- 修改：`templates/note.html`、`static/js/note.js`
- 修改：`templates/share.html`、`static/js/share.js`
- 修改：`static/css/note.css`（评论区样式，两页共用）

**步骤：**
- [x] 在 `note.html` 的 `#comment-panel` 内实现：标题「评论（N）」+ 右侧「评论已开启」toggle（仅作者可见可操作）；评论列表项显示昵称、时间、内容、本人评论带删除图标；底部输入框（占位「写下你的评论…」）+「发布」按钮。
- [x] 抽取公共评论渲染函数 `renderComments(container, data, {canDelete, onDelete})` 与 `bindCommentBox(...)` 放入新文件 `static/js/comments-ui.js`，供 `note.js` 与 `share.js` 复用（DRY）。
- [x] `note.js`：加载评论并渲染；toggle 调 `PUT /api/notes/<id>/comment-setting`；发布调 `POST /api/notes/<id>/comments`；删除调 `DELETE /api/comments/<id>`。
- [x] `share.js`：加载评论；有 `comments_enabled` 决定显示输入框还是「评论已关闭」；未登录时输入框替换为「登录后可评论」按钮，点击跳 `/login?next=<当前地址>`；本人评论可删除。
- [x] 状态覆盖（契约 10.4）：加载中显示骨架；无评论显示「还没有评论，来说两句吧」；提交时按钮禁用显示「发布中…」；超过 500 字在输入框下方提示「评论最多 500 字」并禁用发布。
- [x] Run: `python app.py` 手测：
  - 详情页发评论后列表即时插入且计数 +1。
  - 关闭评论开关后，详情页与分享页均显示「评论已关闭」且无法提交。
  - 分享页未登录状态下看到「登录后可评论」。

**视觉验证：** 1440px 下评论区与正文卡片同宽、间距 24px；375px 下昵称/时间换行不挤压内容、输入框与按钮整行排布。

---

## Task 3: 收藏接口（TDD）

**目标：** 实现收藏切换与收藏列表，并正确计算 `is_available`。

**文件：**
- 新建：`blueprints/favorites.py`
- 修改：`app.py`（注册 favorites 蓝图）
- 修改：`blueprints/share.py`、`blueprints/notes.py`（详情返回 `favorited`，见下）
- 测试：`tests/test_favorites.py`

**步骤：**
- [x] 写失败测试 `tests/test_favorites.py`：
  - `test_toggle_favorite_on_then_off`：首次 → `{favorited:true}`；再次 → `{favorited:false}`。
  - `test_favorite_requires_login`：未登录 → 401。
  - `test_favorite_missing_note`：不存在笔记 → `NOT_FOUND`。
  - `test_favorite_own_note_allowed`：收藏自己的笔记成功。
  - `test_favorite_shared_note_allowed`：收藏他人已分享的笔记成功。
  - `test_favorite_private_note_of_other_forbidden`：收藏他人未分享的笔记 → 403 `FORBIDDEN`。
  - `test_list_favorites_with_availability`：A 收藏 B 的分享笔记后，B 关闭分享 → A 的收藏列表中该项 `is_available=false`。
  - `test_list_favorites_self_flag`：`is_self` 对自有笔记为 `true`。
- [x] Run: `pytest tests/test_favorites.py -q`
  - Expected: FAIL。
- [x] 实现 `blueprints/favorites.py`：
  - `toggle(note_id)`：`login_required`；笔记不存在 → `NOT_FOUND`；若笔记非本人且未开启分享 → `FORBIDDEN`；存在收藏记录则删除，否则插入；返回 `ok({"favorited": bool})`。
  - `list()`：`login_required`；分页；每项 `{note_id, title, owner, is_self, is_available, created_at}`；`is_available` = （`is_self` 为真）或（笔记 `is_shared=1`）；按 `favorites.created_at DESC`。
- [x] 让详情页与分享页能拿到 `favorited`：`GET /api/notes/<id>` 与 `POST /api/share/<token>` 已按设计文档返回该字段，本任务补齐其计算逻辑（依据当前登录用户是否在 `favorites` 中）。
- [x] 在 `app.py` 注册收藏蓝图 `favorites_bp`，`url_prefix="/api"`，蓝图内声明两条路由 `/notes/<int:note_id>/favorite`（POST）与 `/favorites`（GET），与设计文档 9.5 的路径一致。
- [x] Run: `pytest tests/test_favorites.py -q`
  - Expected: PASS。

**安全/边界说明：** 未分享的他人笔记既不可读也不可收藏，避免通过收藏列表探测他人隐私内容。

---

## Task 4: 收藏按钮接入 + 个人主页

**目标：** 在详情页与分享页接入收藏按钮，并交付 `profile.html`（个人信息 / 收藏 / 笔记历史）与 `GET/PUT /api/profile`。

**文件：**
- 新建：`blueprints/profile.py`
- 修改：`app.py`（注册 profile 蓝图与新增 `/profile` 路由）
- 修改：`templates/note.html`、`static/js/note.js`、`templates/share.html`、`static/js/share.js`
- 新建：`templates/profile.html`、`static/css/profile.css`、`static/js/profile.js`
- 测试：`tests/test_profile.py`

**步骤：**
- [x] 写失败测试 `tests/test_profile.py`：`GET /api/profile` 返回 `{id,email,username,bio,created_at,stats:{draft,published,favorite,comment}}`；`PUT` 更新昵称与简介；昵称重复 → `CONFLICT`；简介 >200 字 → `PARAM_ERROR`；未登录 → 401。
- [x] Run: `pytest tests/test_profile.py -q` → Expected: FAIL。
- [x] 新建 `blueprints/profile.py`（`url_prefix="/api/profile"`）：`GET` 汇总四类统计（草稿数、已发布数、收藏数、评论数）；`PUT` 校验昵称 2–20 且唯一、简介 ≤200 字；返回更新后的用户信息。
- [x] 在 `app.py` 注册 profile 蓝图。
- [x] Run: `pytest tests/test_profile.py -q` → Expected: PASS。
- [x] 在详情页与分享页加「收藏」按钮（心形图标）：未收藏为线性、已收藏填充主色；点击调 `POST /api/notes/<id>/favorite`，成功后切换图标态并 `toast('已加入收藏'/'已取消收藏')`；未登录 → 跳登录。
- [x] 新建 `templates/profile.html`：
  - 「个人信息」卡：昵称、邮箱、注册时间、简介 +「编辑资料」按钮（弹窗或行内编辑，保存调 `PUT /api/profile`）。
  - 「我的收藏」卡：收藏列表项显示标题、作者（自有显示「我」）、时间；`is_available=false` 显示「内容已失效」标记且点击提示「该笔记已取消分享」。
  - 「笔记历史」卡：本人笔记按时间倒序，显示标题、状态标签、时间，点击进详情。
- [x] 写 `static/css/profile.css`（三卡纵向排列，宽屏下「个人信息」卡可与右侧内容分栏）与 `static/js/profile.js`（并发拉取 `profile`、`favorites`、`notes` 并渲染；各卡独立处理加载/空/失败态）。
- [x] Run: `python app.py` 手测：
  - 收藏自己的笔记与他人分享的笔记，均出现在个人主页收藏列表。
  - 他人取消分享后，个人主页该项显示「内容已失效」。
  - 修改昵称与简介后刷新仍生效；改成已存在昵称 → 提示「昵称已被占用」。
- [x] Run: `pytest -q` → Expected: 全绿。

**视觉验证：** 1440px 下三卡纵向排列、卡片间 24px；375px 下单列堆叠；收藏失效项有视觉区分（灰色 + 标记）。截图留档（个人主页一张、收藏失效态一张）。

---

## 阶段完成检查清单

- [x] 全部任务完成
- [x] `pytest -q` 全绿（新增 comments / favorites / profile 用例）
- [x] 评论在详情页与分享页行为一致，权限规则与设计文档 9.6 一致
- [x] 收藏的 `is_available` 与 `is_self` 语义验证通过
- [x] 个人主页三块内容均可达且有空/失败态
- [x] 视觉验证截图已留档
- [x] 准备好进入 Phase 6
