"""个人主页接口测试（设计文档 9.3 用户资料 + 统计）。

约定：
- ``GET /api/profile`` 需登录，返回用户资料与四类统计。
- ``PUT /api/profile`` 校验昵称 2–20 且唯一（重复 → CONFLICT）、简介 ≤200 字。
- 未登录一律 401。
"""
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


def test_get_profile_ok(client):
    register_and_login(client)
    create_note(client, title="草稿", status="draft")
    published = create_note(client, title="已发布", status="published")
    client.post("/api/notes/%d/favorite" % published)
    client.post("/api/notes/%d/comments" % published, json={"content": "自评"})

    r = client.get("/api/profile")
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert set(data.keys()) == {"id", "email", "username", "bio", "created_at", "stats"}
    assert data["email"] == "a@b.com"
    assert data["username"] == "阿明"
    assert data["stats"] == {"draft": 1, "published": 1, "favorite": 1, "comment": 1}


def test_profile_requires_login(client):
    r = client.get("/api/profile")
    assert r.status_code == 401
    assert r.get_json()["code"] == "UNAUTHORIZED"


def test_put_profile_updates_username_and_bio(client):
    register_and_login(client)
    r = client.put("/api/profile", json={"username": "新名字", "bio": "新的简介"})
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert data["username"] == "新名字"
    assert data["bio"] == "新的简介"

    # 刷新后仍生效
    again = client.get("/api/profile").get_json()["data"]
    assert again["username"] == "新名字"
    assert again["bio"] == "新的简介"


def test_put_profile_duplicate_username_conflict(app, client):
    register_and_login(client)
    other = app.test_client()
    register_and_login(other, email="b@b.com", username="阿波")

    r = client.put("/api/profile", json={"username": "阿波", "bio": ""})
    assert r.status_code == 409
    assert r.get_json()["code"] == "CONFLICT"
    assert r.get_json()["message"] == "昵称已被占用"


def test_put_profile_same_own_username_allowed(client):
    register_and_login(client)
    r = client.put("/api/profile", json={"username": "阿明", "bio": "简介"})
    assert r.status_code == 200
    assert r.get_json()["data"]["username"] == "阿明"


def test_put_profile_bio_too_long(client):
    register_and_login(client)
    r = client.put("/api/profile", json={"username": "阿明", "bio": "字" * 201})
    assert r.status_code == 400
    assert r.get_json()["code"] == "PARAM_ERROR"


def test_put_profile_username_length(client):
    register_and_login(client)
    too_short = client.put("/api/profile", json={"username": "甲", "bio": ""})
    assert too_short.status_code == 400
    assert too_short.get_json()["code"] == "PARAM_ERROR"

    too_long = client.put("/api/profile", json={"username": "字" * 21, "bio": ""})
    assert too_long.status_code == 400
    assert too_long.get_json()["code"] == "PARAM_ERROR"

    # 边界：2 与 20 字均允许
    assert client.put("/api/profile", json={"username": "甲乙", "bio": ""}).status_code == 200
    assert client.put("/api/profile", json={"username": "字" * 20, "bio": ""}).status_code == 200


def test_put_profile_requires_login(client):
    r = client.put("/api/profile", json={"username": "谁", "bio": ""})
    assert r.status_code == 401
    assert r.get_json()["code"] == "UNAUTHORIZED"
