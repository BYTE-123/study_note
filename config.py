"""应用配置：从环境变量读取运行参数。

约定：所有可调参数都走环境变量，密钥绝不硬编码。
"""
import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _abs(path):
    """相对路径统一解析为相对项目根目录的绝对路径。"""
    if not path:
        return path
    return path if os.path.isabs(path) else os.path.join(BASE_DIR, path)


class Config:
    """开发/生产默认配置。"""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    DB_PATH = _abs(os.environ.get("DB_PATH", "notes.db"))
    UPLOAD_DIR = _abs(os.environ.get("UPLOAD_DIR", os.path.join("static", "uploads")))

    UPLOAD_MAX_SIZE = int(os.environ.get("UPLOAD_MAX_SIZE", 5242880))
    PAGE_SIZE = int(os.environ.get("PAGE_SIZE", 10))
    AI_RATE_LIMIT_PER_MINUTE = int(os.environ.get("AI_RATE_LIMIT_PER_MINUTE", 10))

    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")


class TestingConfig(Config):
    """测试配置：DB_PATH 与 UPLOAD_DIR 由 tests/conftest.py 的夹具覆盖。"""

    TESTING = True
    SECRET_KEY = "test"
    DB_PATH = os.path.join(BASE_DIR, "test.db")
    UPLOAD_DIR = os.path.join(BASE_DIR, "test_uploads")
