"""认证蓝图：注册、登录、登出与当前用户（设计文档 9.3）。"""
import re
import sqlite3
from datetime import datetime

from flask import Blueprint, request, session
from werkzeug.security import check_password_hash, generate_password_hash

import models
from utils.auth_guard import login_required
from utils.errors import ApiError
from utils.responses import fail, ok

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# 邮箱格式：本地部分 @ 域名部分.顶级域，均不含空白
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

USERNAME_MIN = 2
USERNAME_MAX = 20
PASSWORD_MIN = 6


def _now():
    """统一时间格式：秒级 ISO 字符串。"""
    return datetime.now().isoformat(timespec="seconds")


def _conflict_from_integrity(error):
    """把唯一约束异常翻译成带具体中文文案的 CONFLICT。"""
    text = str(error)
    if "email" in text:
        return ApiError("CONFLICT", "邮箱已被注册")
    if "username" in text:
        return ApiError("CONFLICT", "昵称已被占用")
    return ApiError("CONFLICT")


@auth_bp.post("/register")
def register():
    """注册新用户：参数校验 → 唯一性检查 → 写入哈希密码。"""
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    confirm_password = body.get("confirm_password") or ""

    if not email or not username or not password or not confirm_password:
        return fail("PARAM_ERROR", "请完整填写注册信息")
    if not EMAIL_RE.match(email):
        return fail("PARAM_ERROR", "请输入正确的邮箱地址")
    if not (USERNAME_MIN <= len(username) <= USERNAME_MAX):
        return fail("PARAM_ERROR", "用户名长度需为 2-20 个字符")
    if len(password) < PASSWORD_MIN:
        return fail("PARAM_ERROR", "密码长度至少 6 位")
    if password != confirm_password:
        return fail("PARAM_ERROR", "两次输入的密码不一致")

    if models.query_one("SELECT id FROM users WHERE email = ?", (email,)):
        return fail("CONFLICT", "邮箱已被注册")
    if models.query_one("SELECT id FROM users WHERE username = ?", (username,)):
        return fail("CONFLICT", "昵称已被占用")

    try:
        uid = models.execute(
            "INSERT INTO users (email, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (email, username, generate_password_hash(password), _now()),
        )
    except sqlite3.IntegrityError as error:
        # 并发下唯一约束兜底，避免竞态写入重复账号
        raise _conflict_from_integrity(error)

    return ok({"id": uid, "email": email, "username": username})


@auth_bp.post("/login")
def login():
    """登录：按邮箱查用户，密码错误与账号不存在返回同一提示。"""
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""

    user = models.query_one(
        "SELECT id, email, username, password_hash FROM users WHERE email = ?",
        (email,),
    )
    if user is None or not check_password_hash(user["password_hash"], password):
        # 不区分「账号不存在」与「密码错误」，避免账号枚举
        return fail("PASSWORD_ERROR")

    session["user_id"] = user["id"]
    return ok({"id": user["id"], "email": user["email"], "username": user["username"]})


@auth_bp.post("/logout")
@login_required
def logout(user_id=None):
    """登出：清空整个 Session。"""
    session.clear()
    return ok(None, "已退出登录")


@auth_bp.get("/me")
@login_required
def me(user_id=None):
    """当前登录用户信息。"""
    user = models.query_one(
        "SELECT id, email, username, bio FROM users WHERE id = ?",
        (user_id,),
    )
    if user is None:
        # 账号已被删除：清理失效 Session
        session.clear()
        return fail("UNAUTHORIZED")
    return ok({
        "id": user["id"],
        "email": user["email"],
        "username": user["username"],
        "bio": user["bio"] or "",
    })
