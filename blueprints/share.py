"""公开分享读取蓝图（设计文档 9.7）。

约定：
- 免登录访问；按 ``token`` 且 ``is_shared = 1`` 定位笔记，否则 404。
- ``GET`` 只返回元信息，**绝不**返回正文与密码哈希。
- ``POST`` 校验密码后返回设计文档 9.7 的完整结构；密码错误统一返回
  ``WRONG_PASSWORD``，不提示具体原因。
- ``favorited`` / ``is_owner`` 依据当前 Session 计算，未登录时均为 ``false``。
"""
from flask import Blueprint, request
from werkzeug.security import check_password_hash

import models
from utils.auth_guard import current_user_id
from utils.errors import ApiError
from utils.responses import fail, ok

share_bp = Blueprint("share", __name__, url_prefix="/api/share")


def _find_shared_note(token):
    """按 token 定位已分享的笔记，不存在（含分享已关闭）一律 404。"""
    note = models.query_one(
        "SELECT * FROM notes WHERE share_token = ? AND is_shared = 1",
        (token,),
    )
    if note is None:
        raise ApiError("NOT_FOUND")
    return note


def _author(note):
    """取笔记作者用户名。"""
    user = models.query_one(
        "SELECT username FROM users WHERE id = ?", (note["user_id"],)
    )
    return user["username"] if user else ""


@share_bp.get("/<token>")
def meta(token):
    """分享元信息：标题、作者、是否需要密码、时间（不含正文）。"""
    note = _find_shared_note(token)
    return ok({
        "title": note["title"],
        "author": _author(note),
        "need_password": bool(note["share_password_hash"]),
        "created_at": note["created_at"],
        "updated_at": note["updated_at"],
    })


@share_bp.post("/<token>")
def read(token):
    """校验密码后返回正文与互动所需字段（设计文档 9.7）。"""
    note = _find_shared_note(token)

    if note["share_password_hash"]:
        body = request.get_json(silent=True) or {}
        if not check_password_hash(
            note["share_password_hash"], body.get("password") or ""
        ):
            return fail("WRONG_PASSWORD")

    user_id = current_user_id()
    favorited = False
    if user_id is not None:
        favorited = models.query_one(
            "SELECT id FROM favorites WHERE user_id = ? AND note_id = ?",
            (user_id, note["id"]),
        ) is not None

    return ok({
        "id": note["id"],
        "title": note["title"],
        "content": note["content"] or "",
        "author": _author(note),
        "created_at": note["created_at"],
        "updated_at": note["updated_at"],
        "comments_enabled": bool(note["comments_enabled"]),
        "favorited": favorited,
        "is_owner": user_id is not None and user_id == note["user_id"],
    })
