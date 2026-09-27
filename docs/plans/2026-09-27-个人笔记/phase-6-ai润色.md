# Phase 6: AI 润色

**目标：** 完成 DeepSeek 客户端封装与 SSE 流式润色接口，交付编辑器自定义右键菜单与左右对比流式弹窗。
**前置条件：** Phase 3 完成（编辑器与选区可用）；Phase 2 完成（登录态）。真机联调需要可用的 `DEEPSEEK_API_KEY`。
**交付物：** `services/ai_client.py`、`blueprints/ai.py`、`static/js/ai-polish.js`、右键菜单与弹窗样式；接口单测用 mock，无需真实 Key。

**本阶段实现的界面决策：** 契约 10.2 的 AI 润色弹窗布局；契约 10.4 的右键菜单触发条件与 AI 模态全部状态（请求中/流式输出中/完成/出错可重试/空内容禁用确认）；契约 10.1 旅程 5。

---

## Task 1: DeepSeek 客户端与润色提示词

**目标：** 封装可被 mock 的 DeepSeek 流式调用，并固定润色提示词。

**文件：**
- 新建：`services/ai_client.py`
- 测试：`tests/test_ai_client.py`

**步骤：**
- [ ] 写测试 `tests/test_ai_client.py`：
  - `test_missing_api_key_raises`：未配置 `DEEPSEEK_API_KEY` 时调用抛出自定义 `AIUnavailableError`（不发起网络请求）。
  - `test_polish_prompt_contains_text`：断言发送的 `messages` 中 system 提示词包含「润色」与「只返回润色后的文本」，user 内容为目标文本。
  - `test_stream_yields_deltas`：monkeypatch `requests.post` 返回伪造的流式响应，断言 `polish_stream()` 逐块产出 `"优化后的"`、`"文本"` 等片段。
- [ ] Run: `pytest tests/test_ai_client.py -q` → Expected: FAIL。
- [ ] 实现 `services/ai_client.py`：
  - 常量 `SYSTEM_PROMPT = "你是一名中文写作助手。请对用户提供的文本进行润色优化，提升流畅度、清晰度与文采，保持原意与语言风格。只返回润色后的文本，不要解释，不要加引号或前后缀。"`
  - `AIUnavailableError(Exception)`。
  - `polish_stream(text)` 生成器：读取 `DEEPSEEK_BASE_URL`、`DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL`；无 Key 抛 `AIUnavailableError`；`requests.post(f"{base}/chat/completions", json={model, messages, stream:True, temperature:0.7}, stream=True, timeout=30)`；逐行解析以 `data: ` 开头的内容，遇到 `[DONE]` 结束，取出 `choices[0].delta.content` 并 `yield`；HTTP 非 200 抛 `AIUnavailableError`。
- [ ] Run: `pytest tests/test_ai_client.py -q` → Expected: PASS。

**安全/边界说明：** 密钥只从环境变量读取，不得出现在日志或异常消息中；`timeout=30` 防止请求挂死。

---

## Task 2: SSE 润色接口（TDD）

**目标：** 实现 `POST /api/ai/polish`，把 DeepSeek 的流式结果以 SSE 帧转发给前端，并处理长度、频率与异常。

**文件：**
- 新建：`blueprints/ai.py`
- 修改：`app.py`（注册 ai 蓝图，并注册成支持流式的路由）
- 测试：`tests/test_ai.py`

**步骤：**
- [ ] 写失败测试 `tests/test_ai.py`：
  - `test_polish_requires_login`：未登录 → 401 `UNAUTHORIZED`。
  - `test_polish_empty_text`：`{text:""}` → 400 `PARAM_ERROR`。
  - `test_polish_too_long`：`text` 长度 2001 → 400 `PARAM_ERROR`。
  - `test_polish_streams_deltas`：monkeypatch `services.ai_client.polish_stream` 依次产出「优」「化」→ 读取响应体，断言包含 `data: {"delta": "优"}`、`data: {"delta": "化"}`、`data: [DONE]`。
  - `test_polish_upstream_error_frame`：monkeypatch 使其抛 `AIUnavailableError` → 响应体包含 `data: {"error": "AI 服务暂时不可用，请稍后重试"}`。
  - `test_polish_rate_limit`：连续调用超过阈值（配置 `AI_RATE_LIMIT_PER_MINUTE`，测试设为 2）→ 第三次返回 429 `RATE_LIMIT`。
- [ ] Run: `pytest tests/test_ai.py -q` → Expected: FAIL。
- [ ] 实现 `blueprints/ai.py`：
  - 以「模块导入」方式引用服务（`from services import ai_client`，调用 `ai_client.polish_stream(...)`），使测试可通过 monkeypatch 替换 `services.ai_client.polish_stream` 生效。
  - `login_required`；校验 `text` 非空且长度 ≤2000，否则 `fail("PARAM_ERROR", ...)`。
  - 频率限制：进程内字典 `{user_id: [时间戳]}`，滑动窗口 60s，超过 `config.AI_RATE_LIMIT_PER_MINUTE`（默认 10）→ `RATE_LIMIT`。
  - 返回 `Response(stream_with_context(generate()), mimetype="text/event-stream")` 并设置响应头 `Cache-Control: no-cache`、`X-Accel-Buffering: no`（供 Nginx 关闭缓冲）。
  - `generate()` 生成器：逐块 `yield f"data: {json.dumps({'delta': chunk}, ensure_ascii=False)}\n\n"`；捕获 `AIUnavailableError` 与其他异常 → `yield 'data: {"error": "AI 服务暂时不可用，请稍后重试"}\n\n'`；finally 中 `yield "data: [DONE]\n\n"`。
  - 测试读取流式响应体用 `r.get_data(as_text=True)`；断言帧文本时注意 JSON 序列化后的引号与空格需与实际输出一致。
- [ ] 在 `app.py` 注册 ai 蓝图（`url_prefix="/api/ai"`）。
- [ ] Run: `pytest tests/test_ai.py -q` → Expected: PASS。

**安全/边界说明：** 流式响应不泄漏上游原始错误文本；仅登录用户可调用，配合频率限制控制成本。

---

## Task 3: 编辑器自定义右键菜单

**目标：** 在编辑器正文区实现「选中文本后右键出现 AI 润色菜单项」。

**文件：**
- 新建：`static/js/ai-polish.js`
- 修改：`templates/editor.html`（引入 `ai-polish.js` 与菜单容器）
- 修改：`static/css/editor.css`（菜单样式）

**步骤：**
- [ ] 在 `editor.html` 加入菜单容器 `<div id="editor-context-menu" class="context-menu" hidden><button data-action="polish">AI 润色</button></div>`。
- [ ] 在 `ai-polish.js` 实现 `initContextMenu(textarea)`：
  - 监听 `contextmenu`：读取 `selectionStart/selectionEnd`，`selectionEnd > selectionStart` 且选区文本 `trim()` 非空时，阻止浏览器默认菜单并显示自定义菜单（定位到鼠标坐标，超出视口时回收）；否则不拦截，走浏览器默认行为。
  - 点击菜单项：记录 `{start, end, text}` 到模块状态，隐藏菜单并调用 `openPolishModal(selection)`。
  - 点击页面其他位置、滚动、按 Esc 时隐藏菜单。
  - 键盘可达（契约 10.5）：菜单项获得焦点时按 Enter/Space 触发；`textarea` 上按 `Shift+F10` 或菜单键时，若存在选区则显示菜单。
- [ ] 在 `editor.js` 引入并调用 `initContextMenu(textareaEl)`。
- [ ] 写菜单样式：白底、`--radius-control`、`--shadow-modal`、内边距 8×12、悬停主色浅底、菜单项前置「✨」图标。
- [ ] Run: `python app.py` 手测：
  - 未选中文本时右键 → 出现浏览器默认菜单，无自定义菜单。
  - 选中文本后右键 → 出现自定义菜单且仅含「AI 润色」。
  - 点击页面空白处或按 Esc → 菜单消失。

**视觉验证：** 菜单在视口右下角附近右键时不越界；1440px 与 375px 下样式一致。

---

## Task 4: AI 润色弹窗（流式 + 确认替换）

**目标：** 交付左右分栏的润色弹窗，右侧流式显示结果，并实现「取消不改动 / 确认替换仅替换选区」。

**文件：**
- 修改：`static/js/ai-polish.js`
- 修改：`templates/editor.html`（弹窗结构）
- 修改：`static/css/editor.css`（弹窗样式）
- 修改：`static/js/api.js`（新增 `streamPolish(text, {onDelta, onError, onDone, signal})` 的流式请求封装）

**步骤：**
- [ ] 在 `api.js` 新增 `streamPolish(text, handlers)`：用 `fetch('/api/ai/polish', {method:'POST', credentials:'include', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text}), signal})`，读取 `response.body.getReader()`，按 `\n\n` 切分帧，解析 `data: ` 后：`{"delta":x}` → `handlers.onDelta(x)`；`{"error":m}` → `handlers.onError(m)`；`[DONE]` → `handlers.onDone()`。非 200 时按统一响应解析并交由 `onError`（含 401 跳登录、429 提示频率）。
- [ ] 在 `editor.html` 加弹窗结构（`role="dialog" aria-modal="true"`）：标题栏「✨ AI 文本润色」+ 关闭按钮「×」；主体 `.polish-grid` 左栏「原文」（只读展示选中文本）右栏「润色结果」（只读、可选中复制）；底部右下角「取消」「确认替换」。
- [ ] 在 `editor.css` 写弹窗样式：遮罩 `rgba(60,45,30,.35)`；面板最大宽 900px、`--radius-card`、`--shadow-modal`；左右两栏等宽、之间 1px `--color-border` 分隔；两栏各带小标题（13px `--color-muted`）；左上角标题衬线 18px；按钮遵循主/次样式。窄屏（<768px）改为上下堆叠、按钮整行铺满。
- [ ] 在 `ai-polish.js` 实现 `openPolishModal({start, end, text})`：
  - 打开弹窗，左栏填入原文，右栏清空并显示「润色中…」+ 加载动画（spinner）。
  - 调 `streamPolish(text, ...)`：`onDelta` 逐块追加到右栏并自动滚到底部；`onDone` 移除加载态；`onError` 在右栏显示中文错误文案与「重试」按钮。
  - `AbortController`：关闭弹窗或点「取消」时中断请求。
  - 「确认替换」：用右栏当前已生成文本替换 `textarea` 的 `[start, end)` 区间，`setSelectionRange` 定位到替换后文本末尾并触发 `input` 事件，随后关闭弹窗；右栏为空（无任何输出）时按钮禁用。
  - 「取消」/「×」/Esc/点击遮罩：关闭弹窗且**不修改**正文。
  - 焦点管理（契约 10.5）：打开时焦点移入弹窗，Esc 关闭，Tab 在弹窗内循环。
- [ ] Run: `python app.py` 手测（可用 mock 或真实 Key）：
  - 选中一段文字 → 右键「AI 润色」→ 弹窗打开，右栏逐字出现内容。
  - 点「取消」→ 正文完全不变。
  - 再选同一段 → 点「确认替换」→ 仅该段被替换，其余文字与光标位置正常。
  - 将 `DEEPSEEK_API_KEY` 置空后重试 → 右栏显示「AI 服务暂时不可用，请稍后重试」并可重试。
  - 未登录状态触发 → 提示后跳登录页。
- [ ] Run: `pytest -q` → Expected: 全绿。

**视觉验证：** 1440px 下弹窗居中、左右两栏等宽、按钮位于右下角；768px 下两栏变上下堆叠；375px 下按钮整行铺满、文本不溢出。截图留档（弹窗流式中、弹窗完成态各一张），与截图 `05ai润色.png` 对比核对。

---

## 阶段完成检查清单

- [ ] 全部任务完成
- [ ] `pytest -q` 全绿（新增 ai_client / ai 用例，全部基于 mock）
- [ ] 未配置 Key 时接口与前端均给出中文可重试提示，不崩溃
- [ ] 弹窗与截图 05 的布局一致（标题、左右栏标题、右下角两按钮）
- [ ] 「取消不改动、确认替换仅替换选区」经手测确认
- [ ] 视觉验证截图已留档
- [ ] 准备好进入 Phase 7
