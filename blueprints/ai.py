"""AI 润色蓝图：把 DeepSeek 的流式结果以 SSE 帧转发给前端（设计文档 9.x / 10.1）。

约定与边界：
- 仅登录用户可调用，且受进程内滑动窗口频率限制约束（控制成本）；
- ``text`` 非空且 ≤2000 字，否则 400 PARAM_ERROR；
- 频率限制在**打开流之前**判定，超限直接 429 RATE_LIMIT（JSON 响应，不是 SSE）；
- 流内任何异常都收敛为单帧中文错误帧，绝不把上游原始报文回显给前端；
- 服务层以「模块导入」方式引用（``from services import ai_client``），
  调用时取 ``ai_client.polish_stream``，便于测试用 monkeypatch 替换；
- 响应头 ``X-Accel-Buffering: no`` 供 Nginx 关闭缓冲，否则流式会被攒成一坨。
"""
import json
import time

from flask import Blueprint, Response, current_app, request, stream_with_context

from services import ai_client
from utils.auth_guard import login_required
from utils.responses import fail

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")

#: 单次润色的最大字符数
MAX_TEXT_LENGTH = 2000
#: 频率限制的滑动窗口长度（秒）
RATE_WINDOW_SECONDS = 60
#: 统一的失败帧（文案对应 ERROR_MESSAGES["AI_ERROR"]）
ERROR_FRAME = 'data: {"error": "AI 服务暂时不可用，请稍后重试"}\n\n'
DONE_FRAME = "data: [DONE]\n\n"


def _rate_buckets(app):
    """取当前应用实例的频率计数桶（per-app，避免测试或子进程间互相污染）。"""
    return app.extensions.setdefault("ai_rate_buckets", {})


def _is_rate_limited(app, user_id, now):
    """滑动窗口计数：先淘汰过期时间戳，超限返回 True，否则记一次调用。"""
    limit = app.config["AI_RATE_LIMIT_PER_MINUTE"]
    buckets = _rate_buckets(app)
    recent = [stamp for stamp in buckets.get(user_id, [])
              if now - stamp < RATE_WINDOW_SECONDS]

    if len(recent) >= limit:
        buckets[user_id] = recent
        return True

    recent.append(now)
    buckets[user_id] = recent
    return False


@ai_bp.post("/polish")
@login_required
def polish(user_id=None):
    """校验参数与频率后，以 SSE 流式转发润色结果。"""
    payload = request.get_json(silent=True) or {}
    text = payload.get("text")

    if not isinstance(text, str) or not text.strip():
        return fail("PARAM_ERROR", "请先选择需要润色的文本")
    if len(text) > MAX_TEXT_LENGTH:
        return fail("PARAM_ERROR", "选中文本过长，请控制在 2000 字以内")

    if _is_rate_limited(current_app, user_id, time.monotonic()):
        return fail("RATE_LIMIT")

    def generate():
        """逐块转发 delta；异常收敛为错误帧；正常收尾补 [DONE]。

        注意：[DONE] 不能放在 ``finally`` 里 —— 客户端中途断开时生成器会被
        ``close()``（触发 GeneratorExit），在 ``finally`` 中 yield 会抛
        ``RuntimeError: generator ignored GeneratorExit``。
        """
        try:
            for chunk in ai_client.polish_stream(text):
                yield "data: " + json.dumps({"delta": chunk}, ensure_ascii=False) + "\n\n"
        except ai_client.AIUnavailableError:
            yield ERROR_FRAME
        except Exception:
            # 明细只进服务端日志，响应里不出任何内部信息
            current_app.logger.exception("AI 润色流式转发失败")
            yield ERROR_FRAME
        yield DONE_FRAME

    response = Response(stream_with_context(generate()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response
