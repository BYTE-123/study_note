"""图片上传蓝图（设计文档 9.8）。

约定：
- 仅登录用户可上传，``multipart/form-data`` 字段名固定为 ``file``。
- 扩展名白名单 jpg/jpeg/png/gif/webp，大小 ≤ ``UPLOAD_MAX_SIZE``（默认 5MB）。
- 额外校验文件头（magic bytes）确属图片，防止把非图片内容改名成图片后缀上传。
- 文件名一律随机重命名（保留扩展名），不信任前端文件名，消除路径穿越与覆盖。
- 落盘 ``<UPLOAD_DIR>/<YYYY>/<MM>/<uuid4hex>.<ext>``，返回以 ``/static/uploads/``
  开头的正斜杠 URL。
"""
import os
from datetime import datetime
from uuid import uuid4

from flask import Blueprint, current_app, request

from utils.auth_guard import login_required
from utils.responses import fail, ok

upload_bp = Blueprint("upload", __name__, url_prefix="/api/upload")

# 允许的图片扩展名（小写，不含点）
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
# URL 前缀：与生产环境 UPLOAD_DIR = static/uploads 对应
URL_PREFIX = "/static/uploads"

# 允许的图片文件头（只需与「是图片」这一事实相符，不必与后缀一一对应）
_IMAGE_SIGNATURES = (
    b"\x89PNG\r\n\x1a\n",   # PNG
    b"\xff\xd8\xff",        # JPEG
    b"GIF87a",              # GIF
    b"GIF89a",              # GIF
)


def _extension(filename):
    """取白名单可比对的扩展名：基于原始文件名，小写化，不含点。

    不能用 ``secure_filename``：它会剥离所有非 ASCII 字符，导致基名为中文的
    合法图片（如 ``图片.png``）丢失扩展名而被误拒。扩展名只用于白名单校验，
    落盘文件名始终为 ``uuid4().hex``，不信任前端基名。
    """
    return os.path.splitext(filename or "")[1].lstrip(".").lower()


def _looks_like_image(content):
    """按文件头判断内容是否为允许的图片类型（不依赖扩展名）。"""
    if any(content.startswith(sig) for sig in _IMAGE_SIGNATURES):
        return True
    # WEBP：RIFF....WEBP
    return (content[:4] == b"RIFF" and content[8:12] == b"WEBP")


@upload_bp.post("")
@login_required
def upload(user_id=None):
    """接收上传文件：校验参数、扩展名、文件头与大小 → 随机重命名落盘。"""
    file = request.files.get("file")
    if file is None or not file.filename:
        return fail("PARAM_ERROR")

    ext = _extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        return fail("FILE_ERROR")

    content = file.read()
    if len(content) > current_app.config["UPLOAD_MAX_SIZE"]:
        return fail("FILE_ERROR")
    if not _looks_like_image(content):
        # 例如把 .txt 改名成 .png：后缀合法但内容不是图片
        return fail("FILE_ERROR")

    now = datetime.now()
    year, month = now.strftime("%Y"), now.strftime("%m")
    name = uuid4().hex + "." + ext

    directory = os.path.join(current_app.config["UPLOAD_DIR"], year, month)
    os.makedirs(directory, exist_ok=True)
    file.stream.seek(0)
    file.save(os.path.join(directory, name))

    return ok({"url": "/".join([URL_PREFIX, year, month, name])})
