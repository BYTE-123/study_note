"""评论蓝图：列表（免登录）、发表与删除（设计文档 9.6 / 9.8）。

约定：
- ``GET /api/notes/<id>/comments`` 免登录可读；笔记不存在 → 404。
- ``POST `` 需登录；评论开关关闭 → 403 ``FORBIDDEN``（文案「评论已关闭」）。
- 内容去首尾空格后为空或超过 500 字 → 400 ``PARAM_ERROR``。
- ``DELETE /api/comments/<id>`` 需登录且仅作者可删。
- 列表按 ``created_at ASC, id ASC``；``is_self`` 依据当前 Session 判断。
- 安全：后端存原文，XSS 防护交由前端渲染时 ``escapeHtml``。
"""
from datetime import datetime

from flask import Blueprint, request

import models
from utils.auth_guard import current_user_id, login_required
from utils.errors import ApiError
from utils.responses import fail, ok

comments_bp = Blueprint("comments", __name__, url_prefix="/api")

MAX_CONTENT = 500


def _now():
    """统一时间格式：秒级 ISO 字符串（与笔记模块一致）。"""
    return datetime.now().isoformat(timespec="seconds")


def _load_note(note_id):
    """取笔记，不存在 → 404。"""
    note = models.query_one("SELECT * FROM notes WHERE id = ?", (note_id,))
    if note is None:
        raise ApiError("NOT_FOUND")
    return note


def _serialize(comment, viewer_id):
    """把评论行转成接口结构；``is_self`` 依据访问者身份计算。"""
    return {
        "id": comment["id"],
        "user": {"id": comment["user_id"], "username": comment["username"]},
        "content": comment["content"],
        "created_at": comment["created_at"],
        "is_self": viewer_id is not None and comment["user_id"] == viewer_id,
    }


def _comment_query(where, params):
    """联结作者名读取评论行。"""
    return models.query_all(
        "SELECT c.id, c.user_id, c.content, c.created_at, u.username"
        " FROM comments c JOIN users u ON u.id = c.user_id"
        " WHERE " + where + " ORDER BY c.created_at ASC, c.id ASC",
        params,
    )


@comments_bp.get("/notes/<int:note_id>/comments")
def list_comments(note_id):
    """评论列表：免登录，返回评论开关状态与按时间升序的评论。"""
    note = _load_note(note_id)
    rows = _comment_query("c.note_id = ?", (note_id,))
    viewer_id = current_user_id()
    return ok({
        "comments_enabled": bool(note["comments_enabled"]),
        "items": [_serialize(row, viewer_id) for row in rows],
    })


@comments_bp.post("/notes/<int:note_id>/comments")
@login_required
def create(note_id, user_id=None):
    """发表评论：评论关闭 → 403；内容校验后落库并返回新评论。"""
    note = _load_note(note_id)
    if not note["comments_enabled"]:
        return fail("FORBIDDEN", "评论已关闭")

    body = request.get_json(silent=True) or {}
    content = (body.get("content") or "").strip()
    if not content:
        return fail("PARAM_ERROR", "评论内容不能为空")
    if len(content) > MAX_CONTENT:
        return fail("PARAM_ERROR", "评论最多 500 字")

    comment_id = models.execute(
        "INSERT INTO comments (note_id, user_id, content, created_at)"
        " VALUES (?, ?, ?, ?)",
        (note_id, user_id, content, _now()),
    )
    row = _comment_query("c.id = ?", (comment_id,))[0]
    return ok(_serialize(row, user_id))


@comments_bp.delete("/comments/<int:comment_id>")
@login_required
def delete(comment_id, user_id=None):
    """删除评论：不存在 → 404，非作者 → 403。"""
    comment = models.query_one(
        "SELECT * FROM comments WHERE id = ?", (comment_id,))
    if comment is None:
        raise ApiError("NOT_FOUND")
    if comment["user_id"] != user_id:
        raise ApiError("FORBIDDEN")
    models.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    return ok(None, "已删除")
