"""个人主页蓝图：用户资料与统计（设计文档 9.3）。

约定：
- ``GET /api/profile`` 需登录，返回资料 + 四类统计。
- ``PUT /api/profile`` 只更新传入的字段；昵称 2–20 字且唯一（重复 → CONFLICT），
  简介 ≤200 字。
- 统计口径：draft/published 为本人笔记状态数；favorite 为本人收藏数；
  comment 为本人发表的评论数。
"""
from flask import Blueprint, request

import models
from utils.auth_guard import login_required
from utils.errors import ApiError
from utils.responses import fail, ok

profile_bp = Blueprint("profile", __name__, url_prefix="/api/profile")

USERNAME_MIN = 2
USERNAME_MAX = 20
BIO_MAX = 200


def _load_user(user_id):
    """取用户行，不存在 → 404。"""
    user = models.query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if user is None:
        raise ApiError("NOT_FOUND")
    return user


def _stats(user_id):
    """汇总个人主页四类统计。"""
    draft = models.query_one(
        "SELECT COUNT(*) AS total FROM notes WHERE user_id = ? AND status = 'draft'",
        (user_id,),
    )["total"]
    published = models.query_one(
        "SELECT COUNT(*) AS total FROM notes WHERE user_id = ? AND status = 'published'",
        (user_id,),
    )["total"]
    favorite = models.query_one(
        "SELECT COUNT(*) AS total FROM favorites WHERE user_id = ?",
        (user_id,),
    )["total"]
    comment = models.query_one(
        "SELECT COUNT(*) AS total FROM comments WHERE user_id = ?",
        (user_id,),
    )["total"]
    return {
        "draft": draft,
        "published": published,
        "favorite": favorite,
        "comment": comment,
    }


def _user_payload(user):
    """用户资料 + 统计（个人主页 GET / PUT 共用同一结构）。"""
    return {
        "id": user["id"],
        "email": user["email"],
        "username": user["username"],
        "bio": user["bio"] or "",
        "created_at": user["created_at"],
        "stats": _stats(user["id"]),
    }


@profile_bp.get("")
@login_required
def get_profile(user_id=None):
    """读取当前用户资料与统计。"""
    return ok(_user_payload(_load_user(user_id)))


@profile_bp.put("")
@login_required
def update_profile(user_id=None):
    """更新昵称与简介：昵称 2–20 且唯一，简介 ≤200 字。"""
    _load_user(user_id)
    body = request.get_json(silent=True) or {}
    fields = {}

    if "username" in body:
        username = (body.get("username") or "").strip()
        if not (USERNAME_MIN <= len(username) <= USERNAME_MAX):
            return fail("PARAM_ERROR", "昵称需 2-20 个字符")
        taken = models.query_one(
            "SELECT id FROM users WHERE username = ? AND id <> ?",
            (username, user_id),
        )
        if taken is not None:
            return fail("CONFLICT", "昵称已被占用")
        fields["username"] = username

    if "bio" in body:
        bio = body.get("bio") or ""
        if len(bio) > BIO_MAX:
            return fail("PARAM_ERROR", "简介最多 200 字")
        fields["bio"] = bio

    if fields:
        assignments = ", ".join("%s = ?" % column for column in fields)
        models.execute(
            "UPDATE users SET " + assignments + " WHERE id = ?",
            list(fields.values()) + [user_id],
        )
    return ok(_user_payload(_load_user(user_id)))
