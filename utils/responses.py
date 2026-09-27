"""统一响应封装：所有接口（含错误分支）的唯一出口。

成功：``ok(data, message)`` → ``({code, message, data}, 200)``
失败：``fail(code, message)`` → ``({code, message, data: null}, http_status)``
返回的是 ``(body_dict, http_status)`` 二元组，由 Flask 自动序列化为 JSON。
"""
from utils.errors import ERROR_HTTP_STATUS, ERROR_MESSAGES


def ok(data=None, message="操作成功"):
    """成功响应。"""
    return {"code": "OK", "message": message, "data": data}, 200


def fail(code, message=None):
    """失败响应：message 缺省时取错误码表默认中文文案。"""
    if message is None:
        message = ERROR_MESSAGES.get(code, ERROR_MESSAGES["SERVER_ERROR"])
    status = ERROR_HTTP_STATUS.get(code, ERROR_HTTP_STATUS["SERVER_ERROR"])
    return {"code": code, "message": message, "data": None}, status
