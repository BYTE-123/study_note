"""错误码表：错误码 → 中文文案 / HTTP 状态（对应设计文档 9.2）。"""


class ApiError(Exception):
    """业务异常：携带错误码，由全局错误处理器统一转成响应。"""

    def __init__(self, code, message=None):
        self.code = code
        self.message = (
            message if message is not None else ERROR_MESSAGES.get(code, ERROR_MESSAGES["SERVER_ERROR"])
        )
        super().__init__(self.message)


# 全部 12 个错误码的默认中文文案
ERROR_MESSAGES = {
    "OK": "操作成功",
    "PARAM_ERROR": "参数不完整或格式错误",
    "PASSWORD_ERROR": "邮箱或密码错误",
    "WRONG_PASSWORD": "分享密码错误",
    "UNAUTHORIZED": "请先登录",
    "FORBIDDEN": "无权操作该资源",
    "NOT_FOUND": "资源不存在",
    "CONFLICT": "资源冲突，请稍后重试",
    "FILE_ERROR": "仅支持 jpg/png/gif/webp，且不超过 5MB",
    "AI_ERROR": "AI 服务暂时不可用，请稍后重试",
    "RATE_LIMIT": "操作过于频繁，请稍后再试",
    "SERVER_ERROR": "服务器开小差了，请稍后重试",
}

# 错误码 → HTTP 状态码
ERROR_HTTP_STATUS = {
    "OK": 200,
    "PARAM_ERROR": 400,
    "PASSWORD_ERROR": 400,
    "WRONG_PASSWORD": 403,
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "CONFLICT": 409,
    "FILE_ERROR": 400,
    "AI_ERROR": 502,
    "RATE_LIMIT": 429,
    "SERVER_ERROR": 500,
}
