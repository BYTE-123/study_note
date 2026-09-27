"""收藏蓝图：切换收藏与收藏列表（设计文档 9.5）。

约定：
- 两条路由均需登录；声明在 ``/api`` 前缀下：``/notes/<id>/favorite``、``/favorites``。
- 切换语义：无记录插入、有记录删除，返回最新 ``{"favorited": bool}``。
- 安全：**非本人且未分享**的笔记既不可读也不可收藏 → 403，避免通过收藏探测隐私。
- 列表 ``is_available`` = 自有 或 笔记 ``is_shared=1``；按 ``favorites.created_at DESC``。
- 返回与 ``GET /api/notes`` 一致的分页信封，便于前端复用分页逻辑。
"""
from datetime import datetime

from flask import Blueprint, current_app, request

import models
from utils.auth_guard import login_required
from utils.errors import ApiError
from utils.responses import ok

favorites_bp = Blueprint("favorites", __name__, url_prefix="/api")


def _now():
    """统一时间格式：秒级 ISO 字符串（与笔记模块一致）。"""
    return datetime.now().isoformat(timespec="seconds")


def _positive_int(value, default):
    """把 query 参数解析为正整数，非法或缺省时返回默认值。"""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _load_note(note_id):
    """取笔记，不存在 → 404。"""
    note = models.query_one("SELECT * FROM notes WHERE id = ?", (note_id,))
    if note is None:
        raise ApiError("NOT_FOUND")
    return note


@favorites_bp.post("/notes/<int:note_id>/favorite")
@login_required
def toggle(note_id, user_id=None):
    """切换收藏：非本人且未分享 → 403；否则插入或删除收藏记录。"""
    note = _load_note(note_id)
    if note["user_id"] != user_id and not note["is_shared"]:
        raise ApiError("FORBIDDEN")

    existing = models.query_one(
        "SELECT id FROM favorites WHERE user_id = ? AND note_id = ?",
        (user_id, note_id),
    )
    if existing is not None:
        models.execute("DELETE FROM favorites WHERE id = ?", (existing["id"],))
        return ok({"favorited": False})

    models.execute(
        "INSERT INTO favorites (user_id, note_id, created_at) VALUES (?, ?, ?)",
        (user_id, note_id, _now()),
    )
    return ok({"favorited": True})


@favorites_bp.get("/favorites")
@login_required
def list_favorites(user_id=None):
    """收藏列表：分页返回标题、作者、可用性与收藏时间。"""
    page = _positive_int(request.args.get("page"), 1)
    page_size = _positive_int(
        request.args.get("page_size"), current_app.config["PAGE_SIZE"])

    total = models.query_one(
        "SELECT COUNT(*) AS total FROM favorites WHERE user_id = ?",
        (user_id,),
    )["total"]

    rows = models.query_all(
        "SELECT f.note_id, f.created_at AS favorited_at, n.title,"
        " n.user_id AS owner_id, n.is_shared, u.username AS owner_name"
        " FROM favorites f"
        " JOIN notes n ON n.id = f.note_id"
        " JOIN users u ON u.id = n.user_id"
        " WHERE f.user_id = ?"
        " ORDER BY f.created_at DESC, f.id DESC LIMIT ? OFFSET ?",
        (user_id, page_size, (page - 1) * page_size),
    )

    items = []
    for row in rows:
        is_self = row["owner_id"] == user_id
        items.append({
            "note_id": row["note_id"],
            "title": row["title"],
            "owner": row["owner_name"],
            "is_self": is_self,
            "is_available": is_self or bool(row["is_shared"]),
            "created_at": row["favorited_at"],
        })

    return ok({"total": total, "page": page, "page_size": page_size, "items": items})
