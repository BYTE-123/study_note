"""登录态工具：读取当前用户 id 与登录校验装饰器。

约定：
- 前端为 SPA 式请求，未登录时**不重定向**，一律返回统一 JSON 失败体。
- 已登录时把 ``user_id`` 以关键字参数注入被装饰函数，供业务层使用。
"""
from functools import wraps

from flask import session

from utils.responses import fail


def current_user_id():
    """返回当前登录用户 id，未登录返回 None。"""
    return session.get("user_id")


def login_required(fn):
    """登录校验装饰器：未登录返回 UNAUTHORIZED，已登录注入 user_id。"""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = current_user_id()
        if user_id is None:
            return fail("UNAUTHORIZED")
        kwargs["user_id"] = user_id
        return fn(*args, **kwargs)

    return wrapper
