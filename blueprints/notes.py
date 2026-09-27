"""笔记蓝图：增删改查、归属校验与摘要（设计文档 9.4）。

约定：
- 全部接口需要登录（``@login_required`` 注入 ``user_id``）。
- 归属校验按 id 操作时最先执行，错误顺序：未登录 401 → 不存在 404 → 非本人 403。
- 非本人且不存在时统一返回 ``NOT_FOUND``，不泄漏笔记是否存在。
"""
import re
from datetime import datetime

from flask import Blueprint, current_app, request

import models
from utils.auth_guard import login_required
from utils.errors import ApiError
from utils.responses import fail, ok

notes_bp = Blueprint("notes", __name__, url_prefix="/api/notes")

# 上限与默认值
MAX_TITLE = 100
MAX_TAGS = 100
SUMMARY_LEN = 80
STATUSES = ("draft", "published")
RECENT_DEFAULT = 5
RECENT_MAX = 20

# Markdown 标记清理：图片/链接语法先去，再去除行内标记，最后压缩空白
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MD_MARK_RE = re.compile(r"[#*>`~]+")
_WS_RE = re.compile(r"\s+")


def _now():
    """统一时间格式：秒级 ISO 字符串（与认证模块一致）。"""
    return datetime.now().isoformat(timespec="seconds")


def strip_markdown(text):
    """去掉常见 Markdown 标记，取前 80 字作为列表摘要。"""
    text = text or ""
    text = _MD_IMAGE_RE.sub("", text)
    text = _MD_LINK_RE.sub(r"\1", text)
    text = _MD_MARK_RE.sub("", text)
    return _WS_RE.sub(" ", text).strip()[:SUMMARY_LEN]


def _positive_int(value, default):
    """把 query 参数解析为正整数，非法或缺省时返回默认值。"""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _load_owned_note(note_id, user_id):
    """按 id 取笔记并校验归属：不存在 404，非本人 403。"""
    note = models.query_one("SELECT * FROM notes WHERE id = ?", (note_id,))
    if note is None:
        raise ApiError("NOT_FOUND")
    if note["user_id"] != user_id:
        raise ApiError("FORBIDDEN")
    return note


def _validate_title(raw):
    """标题校验：超长报错，空串回落为「无标题」。"""
    title = (raw or "").strip()
    if len(title) > MAX_TITLE:
        raise ApiError("PARAM_ERROR", "标题最多 100 个字符")
    return title or "无标题"


def _validate_tags(raw):
    """标签校验：超长报错。"""
    tags = (raw or "").strip()
    if len(tags) > MAX_TAGS:
        raise ApiError("PARAM_ERROR", "标签最多 100 个字符")
    return tags


def _validate_status(raw, default="draft"):
    """状态校验：仅允许 draft / published。"""
    status = (raw or default).strip()
    if status not in STATUSES:
        raise ApiError("PARAM_ERROR", "状态只能为草稿或已发布")
    return status


@notes_bp.get("")
@login_required
def list_notes(user_id=None):
    """我的笔记列表：支持状态、关键词、标签筛选与分页。"""
    status = (request.args.get("status") or "all").strip()
    keyword = (request.args.get("keyword") or "").strip()
    tag = (request.args.get("tag") or "").strip()
    page = _positive_int(request.args.get("page"), 1)
    page_size = _positive_int(request.args.get("page_size"), current_app.config["PAGE_SIZE"])

    where = ["user_id = ?"]
    params = [user_id]
    if status in STATUSES:
        where.append("status = ?")
        params.append(status)
    if keyword:
        where.append("(title LIKE ? OR content LIKE ?)")
        like = "%" + keyword + "%"
        params.extend([like, like])
    if tag:
        where.append("tags LIKE ?")
        params.append("%" + tag + "%")
    clause = " AND ".join(where)

    total = models.query_one(
        "SELECT COUNT(*) AS total FROM notes WHERE " + clause, params
    )["total"]

    rows = models.query_all(
        "SELECT * FROM notes WHERE " + clause
        + " ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
        params + [page_size, (page - 1) * page_size],
    )
    items = [{
        "id": row["id"],
        "title": row["title"],
        "summary": strip_markdown(row["content"]),
        "tags": row["tags"] or "",
        "status": row["status"],
        "is_shared": bool(row["is_shared"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    } for row in rows]

    return ok({"total": total, "page": page, "page_size": page_size, "items": items})


@notes_bp.post("")
@login_required
def create(user_id=None):
    """新建笔记：校验参数后落库，返回 ``{id}``。"""
    body = request.get_json(silent=True) or {}
    title = _validate_title(body.get("title"))
    tags = _validate_tags(body.get("tags"))
    status = _validate_status(body.get("status"))
    content = body.get("content") or ""

    now = _now()
    note_id = models.execute(
        "INSERT INTO notes (user_id, title, content, tags, status, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, title, content, tags, status, now, now),
    )
    return ok({"id": note_id})


@notes_bp.get("/stats")
@login_required
def stats(user_id=None):
    """工作台统计：草稿数、已发布数与本人收藏数。"""
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
    return ok({"draft": draft, "published": published, "favorite": favorite})


@notes_bp.get("/recent")
@login_required
def recent(user_id=None):
    """最近文章：按 updated_at 倒序，limit 默认 5、上限 20。"""
    limit = min(_positive_int(request.args.get("limit"), RECENT_DEFAULT), RECENT_MAX)
    rows = models.query_all(
        "SELECT id, title, status, updated_at FROM notes WHERE user_id = ?"
        " ORDER BY updated_at DESC, id DESC LIMIT ?",
        (user_id, limit),
    )
    return ok([{
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "updated_at": row["updated_at"],
    } for row in rows])


@notes_bp.get("/<int:note_id>")
@login_required
def detail(note_id, user_id=None):
    """笔记详情：仅本人可读，返回设计文档 9.4 的完整结构。"""
    note = _load_owned_note(note_id, user_id)
    favorite = models.query_one(
        "SELECT id FROM favorites WHERE user_id = ? AND note_id = ?",
        (user_id, note_id),
    )
    return ok({
        "id": note["id"],
        "title": note["title"],
        "content": note["content"] or "",
        "tags": note["tags"] or "",
        "status": note["status"],
        "is_shared": bool(note["is_shared"]),
        "share_token": note["share_token"],
        "has_password": bool(note["share_password_hash"]),
        "comments_enabled": bool(note["comments_enabled"]),
        "created_at": note["created_at"],
        "updated_at": note["updated_at"],
        "favorited": favorite is not None,
        "is_owner": True,
    })


@notes_bp.put("/<int:note_id>")
@login_required
def update(note_id, user_id=None):
    """更新笔记：归属校验后只更新传入的字段，并刷新 updated_at。"""
    _load_owned_note(note_id, user_id)
    body = request.get_json(silent=True) or {}

    fields = {}
    if "title" in body:
        fields["title"] = _validate_title(body.get("title"))
    if "content" in body:
        fields["content"] = body.get("content") or ""
    if "tags" in body:
        fields["tags"] = _validate_tags(body.get("tags"))
    if "status" in body:
        fields["status"] = _validate_status(body.get("status"))

    if fields:
        fields["updated_at"] = _now()
        assignments = ", ".join("%s = ?" % column for column in fields)
        models.execute(
            "UPDATE notes SET " + assignments + " WHERE id = ?",
            list(fields.values()) + [note_id],
        )
    return ok({"id": note_id})


@notes_bp.delete("/<int:note_id>")
@login_required
def delete(note_id, user_id=None):
    """删除笔记：归属校验后删除，评论与收藏由外键级联清理。"""
    _load_owned_note(note_id, user_id)
    models.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    return ok(None, "已删除")
