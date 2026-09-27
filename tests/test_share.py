"""分享接口测试（设计文档 9.4 分享开关 / 9.7 公开读取 / 9.8 评论开关）。

约定：
- ``PUT /api/notes/<id>/share`` 需登录且仅作者可操作，密码哈希存储。
- ``GET/POST /api/share/<token>`` 免登录；token 无效或分享关闭时 404。
- 元信息接口绝不返回正文与密码哈希。
"""
import models


def register_and_login(client, email="a@b.com", username="阿明"):
    """注册并登录一个用户，返回同一个 client（已带 Session）。"""
    client.post("/api/auth/register", json={
        "email": email, "username": username,
        "password": "123456", "confirm_password": "123456"})
    client.post("/api/auth/login", json={"email": email, "password": "123456"})
    return client


def create_note(client, **overrides):
    """创建一篇笔记并返回其 id。"""
    body = {"title": "标题", "content": "正文"}
    body.update(overrides)
    r = client.post("/api/notes", json=body)
    assert r.status_code == 200, r.get_json()
    return r.get_json()["data"]["id"]


def note_row(app, note_id):
    """直接读取 notes 表某行，用于断言落库字段。"""
    with app.app_context():
        return models.query_one("SELECT * FROM notes WHERE id = ?", (note_id,))


def set_share(client, note_id, payload):
    return client.put("/api/notes/%d/share" % note_id, json=payload)


def enable_share(client, note_id, **extra):
    """开启分享并返回 data（默认无密码）。"""
    payload = {"enabled": True}
    payload.update(extra)
    r = set_share(client, note_id, payload)
    assert r.status_code == 200, r.get_json()
    return r.get_json()["data"]


# ---------------------------------------------------------------- Task 3

def test_enable_share_generates_token(app, client):
    register_and_login(client)
    uid = create_note(client, status="published")
    data = enable_share(client, uid)
    assert data["is_shared"] is True
    assert data["share_token"]
    assert data["has_password"] is False
    assert data["share_url"] == "/share.html?token=" + data["share_token"]

    row = note_row(app, uid)
    assert row["is_shared"] == 1
    assert row["share_token"] == data["share_token"]


def test_enable_share_with_password(app, client):
    register_and_login(client)
    uid = create_note(client, status="published")
    data = enable_share(client, uid, password="pass123")
    assert data["has_password"] is True

    row = note_row(app, uid)
    assert row["share_password_hash"]
    # 绝不落库明文
    assert row["share_password_hash"] != "pass123"


def test_disable_share_clears_token(app, client):
    register_and_login(client)
    uid = create_note(client, status="published")
    enable_share(client, uid)

    data = set_share(client, uid, {"enabled": False}).get_json()["data"]
    assert data["is_shared"] is False
    assert data["share_token"] is None

    row = note_row(app, uid)
    assert row["is_shared"] == 0
    assert row["share_token"] is None


def test_share_requires_owner(app, client):
    register_and_login(client)
    uid = create_note(client, status="published")

    other = app.test_client()
    register_and_login(other, email="b@b.com", username="阿波")
    r = set_share(other, uid, {"enabled": True})
    assert r.status_code == 403
    assert r.get_json()["code"] == "FORBIDDEN"


def test_short_password_rejected(client):
    register_and_login(client)
    uid = create_note(client, status="published")
    r = set_share(client, uid, {"enabled": True, "password": "123"})
    assert r.status_code == 400
    assert r.get_json()["code"] == "PARAM_ERROR"


def test_enable_share_reuses_existing_token(client):
    register_and_login(client)
    uid = create_note(client, status="published")
    first = enable_share(client, uid)["share_token"]
    second = enable_share(client, uid)["share_token"]
    assert first == second


def test_password_null_removes(app, client):
    register_and_login(client)
    uid = create_note(client, status="published")
    enable_share(client, uid, password="pass123")
    data = enable_share(client, uid, password=None)
    assert data["has_password"] is False
    assert note_row(app, uid)["share_password_hash"] is None


def test_comment_setting_toggle(app, client):
    register_and_login(client)
    uid = create_note(client, status="published")
    off = client.put("/api/notes/%d/comment-setting" % uid, json={"enabled": False})
    assert off.status_code == 200
    assert off.get_json()["data"]["comments_enabled"] is False
    assert note_row(app, uid)["comments_enabled"] == 0

    on = client.put("/api/notes/%d/comment-setting" % uid, json={"enabled": True})
    assert on.get_json()["data"]["comments_enabled"] is True


def test_comment_setting_requires_owner(app, client):
    register_and_login(client)
    uid = create_note(client, status="published")
    other = app.test_client()
    register_and_login(other, email="b@b.com", username="阿波")
    r = other.put("/api/notes/%d/comment-setting" % uid, json={"enabled": False})
    assert r.status_code == 403


# ---------------------------------------------------------------- Task 4

def share_token(client, note_id, **extra):
    """开启分享并返回 token。"""
    return enable_share(client, note_id, **extra)["share_token"]


def test_share_meta_no_password(client):
    register_and_login(client)
    uid = create_note(client, title="公开文", content="正文内容", status="published")
    token = share_token(client, uid)

    r = client.get("/api/share/%s" % token)
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert data["title"] == "公开文"
    assert data["author"] == "阿明"
    assert data["need_password"] is False
    assert "content" not in data
    assert "share_password_hash" not in data


def test_share_meta_with_password(client):
    register_and_login(client)
    uid = create_note(client, status="published")
    token = share_token(client, uid, password="pass123")
    data = client.get("/api/share/%s" % token).get_json()["data"]
    assert data["need_password"] is True


def test_share_meta_invalid_token(client):
    r = client.get("/api/share/deadbeef")
    assert r.status_code == 404
    assert r.get_json()["code"] == "NOT_FOUND"


def test_share_meta_disabled(client):
    register_and_login(client)
    uid = create_note(client, status="published")
    token = share_token(client, uid)
    set_share(client, uid, {"enabled": False})
    r = client.get("/api/share/%s" % token)
    assert r.status_code == 404
    assert r.get_json()["code"] == "NOT_FOUND"


def test_read_no_password_ok(app, client):
    register_and_login(client)
    uid = create_note(client, title="公开文", content="# 正文", status="published")
    token = share_token(client, uid)

    # 以未登录访客身份读取，确保公开可读且 is_owner=false
    guest = app.test_client()
    r = guest.post("/api/share/%s" % token, json={})
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert data["id"] == uid
    assert data["title"] == "公开文"
    assert data["content"] == "# 正文"
    assert data["author"] == "阿明"
    assert data["comments_enabled"] is True
    assert data["is_owner"] is False
    assert data["favorited"] is False


def test_read_wrong_password(client):
    register_and_login(client)
    uid = create_note(client, content="秘密正文", status="published")
    token = share_token(client, uid, password="pass123")

    r = client.post("/api/share/%s" % token, json={"password": "wrong"})
    assert r.status_code == 403
    assert r.get_json()["code"] == "WRONG_PASSWORD"


def test_read_correct_password(client):
    register_and_login(client)
    uid = create_note(client, content="秘密正文", status="published")
    token = share_token(client, uid, password="pass123")

    r = client.post("/api/share/%s" % token, json={"password": "pass123"})
    assert r.status_code == 200
    assert r.get_json()["data"]["content"] == "秘密正文"


def test_share_read_logged_in_favorited_flag(app, client):
    register_and_login(client)
    uid = create_note(client, content="正文", status="published")
    token = share_token(client, uid)

    # 未登录访客固定 favorited=false / is_owner=false
    guest = app.test_client()
    guest_data = guest.post("/api/share/%s" % token, json={}).get_json()["data"]
    assert guest_data["favorited"] is False
    assert guest_data["is_owner"] is False

    # 另一个登录用户收藏后 favorited=true，且非作者
    other = app.test_client()
    register_and_login(other, email="b@b.com", username="阿波")
    with app.app_context():
        user = models.query_one("SELECT id FROM users WHERE email = ?", ("b@b.com",))
        models.execute(
            "INSERT INTO favorites (user_id, note_id, created_at) VALUES (?, ?, ?)",
            (user["id"], uid, "2026-01-01T00:00:00"),
        )
    other_data = other.post("/api/share/%s" % token, json={}).get_json()["data"]
    assert other_data["favorited"] is True
    assert other_data["is_owner"] is False
