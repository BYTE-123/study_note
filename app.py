"""应用入口：应用工厂、蓝图注册、页面路由与全局错误处理。"""
import logging
import os

from flask import Flask, send_from_directory
from werkzeug.exceptions import HTTPException

import models
from blueprints.auth import auth_bp
from config import Config
from utils.errors import ApiError
from utils.responses import fail

# 蓝图登记表：各阶段逐步把领域蓝图追加进来（前缀声明在蓝图自身）。
BLUEPRINTS = [auth_bp]

# 常见 HTTP 异常 → 错误码映射（其余按 5xx/4xx 兜底）
_HTTP_EXCEPTION_CODE = {
    400: "PARAM_ERROR",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "NOT_FOUND",
    409: "CONFLICT",
    429: "RATE_LIMIT",
}


def register_error_handlers(app):
    """注册全局错误处理器，确保任何失败都返回统一 JSON 结构。"""

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return fail(error.code, error.message)

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        code = _HTTP_EXCEPTION_CODE.get(error.code)
        if code is None:
            code = "SERVER_ERROR" if (error.code or 500) >= 500 else "PARAM_ERROR"
        return fail(code)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        # 只记日志，绝不把堆栈或数据库原文返回前端
        app.logger.exception("Unhandled exception: %s", error)
        return fail("SERVER_ERROR")


def create_app(config_object=Config):
    """创建并配置 Flask 应用。"""
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config.from_object(config_object)
    app.secret_key = app.config["SECRET_KEY"]

    # 登录态安全：HttpOnly + SameSite=Lax
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # 中文不被转义为 \uXXXX
    app.json.ensure_ascii = False

    # 上传目录必须先存在
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)

    with app.app_context():
        models.init_db()

    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)

    register_error_handlers(app)

    @app.get("/api/health")
    def health():
        return {"code": "OK", "message": "操作成功", "data": {"status": "up"}}

    @app.get("/")
    def index():
        return send_from_directory("templates", "index.html")

    @app.get("/login")
    def login_page():
        return send_from_directory("templates", "login.html")

    @app.get("/register")
    def register_page():
        return send_from_directory("templates", "register.html")

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app().run(
        host="127.0.0.1",
        port=5000,
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
