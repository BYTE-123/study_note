"""图片上传接口测试（设计文档 9.8）。

约定：扩展名白名单 jpg/jpeg/png/gif/webp；大小 ≤ 5MB；
文件名随机生成（保留扩展名），不信任前端文件名与路径。
"""
import io
import os

# 5MB 上限（与 config.UPLOAD_MAX_SIZE 默认值一致）
MAX_SIZE = 5 * 1024 * 1024
# 1x1 透明 PNG 的最小合法字节
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def register_and_login(client, email="a@b.com", username="阿明"):
    """注册并登录一个用户，返回同一个 client（已带 Session）。"""
    client.post("/api/auth/register", json={
        "email": email, "username": username,
        "password": "123456", "confirm_password": "123456"})
    client.post("/api/auth/login", json={"email": email, "password": "123456"})
    return client


def upload(client, filename="pic.png", content=PNG_BYTES):
    """以 multipart/form-data 上传一个文件，字段名固定为 ``file``。"""
    return client.post(
        "/api/upload",
        data={"file": (io.BytesIO(content), filename)},
        content_type="multipart/form-data",
    )


def disk_path(app, url):
    """把返回的 /static/uploads/... URL 映射到测试用的 UPLOAD_DIR 磁盘路径。"""
    rel = url[len("/static/uploads/"):]
    return os.path.join(app.config["UPLOAD_DIR"], *rel.split("/"))


def test_upload_png_ok(app, client):
    register_and_login(client)
    r = upload(client, "photo.png")
    assert r.status_code == 200
    body = r.get_json()
    assert body["code"] == "OK"
    url = body["data"]["url"]
    assert url.startswith("/static/uploads/")
    assert url.endswith(".png")
    # 返回的是正斜杠 URL，且磁盘上确实落盘
    assert "\\" not in url
    assert os.path.exists(disk_path(app, url))


def test_upload_rejects_bad_extension(client):
    register_and_login(client)
    r = upload(client, "evil.exe", b"MZ\x90\x00binary")
    assert r.status_code == 400
    assert r.get_json()["code"] == "FILE_ERROR"


def test_upload_rejects_oversize(client):
    register_and_login(client)
    r = upload(client, "big.png", b"a" * (MAX_SIZE + 1))
    assert r.status_code == 400
    assert r.get_json()["code"] == "FILE_ERROR"


def test_upload_requires_login(client):
    r = upload(client, "pic.png")
    assert r.status_code == 401
    assert r.get_json()["code"] == "UNAUTHORIZED"


def test_upload_filename_is_randomized(client):
    register_and_login(client)
    first = upload(client, "original.png").get_json()["data"]["url"]
    second = upload(client, "original.png").get_json()["data"]["url"]
    assert first != second
    assert "original" not in first
    assert "original" not in second


def test_upload_accepts_non_ascii_filename(app, client):
    """纯中文基名不应丢失扩展名：secure_filename 会把基名清空。"""
    register_and_login(client)
    r = upload(client, "图片.png")
    assert r.status_code == 200
    body = r.get_json()
    assert body["code"] == "OK"
    url = body["data"]["url"]
    assert url.startswith("/static/uploads/")
    assert url.endswith(".png")
    assert os.path.exists(disk_path(app, url))


def test_upload_accepts_non_ascii_jpeg(client):
    register_and_login(client)
    r = upload(client, "我的照片.jpeg")
    assert r.status_code == 200
    assert r.get_json()["data"]["url"].endswith(".jpeg")


def test_upload_rejects_missing_extension(client):
    register_and_login(client)
    r = upload(client, "noext", PNG_BYTES)
    assert r.status_code == 400
    assert r.get_json()["code"] == "FILE_ERROR"


def test_upload_rejects_double_extension(client):
    register_and_login(client)
    r = upload(client, "x.png.exe", b"MZ\x90\x00binary")
    assert r.status_code == 400
    assert r.get_json()["code"] == "FILE_ERROR"


def test_upload_rejects_non_ascii_executable(client):
    """白名单校验不应被非 ASCII 基名绕过。"""
    register_and_login(client)
    r = upload(client, "恶意.exe", b"MZ\x90\x00binary")
    assert r.status_code == 400
    assert r.get_json()["code"] == "FILE_ERROR"
