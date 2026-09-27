"""笔记接口测试：CRUD、归属校验、筛选与摘要（设计文档 9.4）。

约定：所有接口都需要登录；归属校验放在按 id 操作的最前面，
错误顺序为「未登录 401 → 不存在 404 → 非本人 403」。
"""
import time

import models


def add_favorite(app, email, note_id):
    """直接写入 favorites 行（收藏接口属 Phase 5，本阶段用于构造统计）。"""
    with app.app_context():
        user = models.query_one("SELECT id FROM users WHERE email = ?", (email,))
        models.execute(
            "INSERT INTO favorites (user_id, note_id, created_at) VALUES (?, ?, ?)",
            (user["id"], note_id, "2026-01-01T00:00:00"),
        )


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


def test_create_note_ok(client):
    register_and_login(client)
    r = client.post("/api/notes", json={"title": "第一篇", "content": "正文"})
    assert r.status_code == 200
    assert r.get_json()["code"] == "OK"
    uid = r.get_json()["data"]["id"]
    detail = client.get("/api/notes/%d" % uid).get_json()["data"]
    assert detail["title"] == "第一篇"
    # 未传 status 时默认草稿
    assert detail["status"] == "draft"


def test_create_note_empty_title_defaults(client):
    register_and_login(client)
    uid = create_note(client, title="")
    detail = client.get("/api/notes/%d" % uid).get_json()["data"]
    assert detail["title"] == "无标题"


def test_list_own_notes_only(app, client):
    register_and_login(client)
    create_note(client, title="A1")
    create_note(client, title="A2")

    other = app.test_client()
    register_and_login(other, email="b@b.com", username="阿波")
    create_note(other, title="B1")

    data = client.get("/api/notes").get_json()["data"]
    assert data["total"] == 2
    assert {item["title"] for item in data["items"]} == {"A1", "A2"}


def test_list_filter_by_status_and_keyword(client):
    register_and_login(client)
    create_note(client, title="学习笔记", content="python 学习", status="published")
    create_note(client, title="生活随笔", content="今天天气不错", status="draft")

    published = client.get("/api/notes?status=published").get_json()["data"]
    assert published["total"] == 1
    assert published["items"][0]["title"] == "学习笔记"

    draft = client.get("/api/notes?status=draft").get_json()["data"]
    assert draft["total"] == 1
    assert draft["items"][0]["title"] == "生活随笔"

    matched = client.get("/api/notes?keyword=天气").get_json()["data"]
    assert matched["total"] == 1
    assert matched["items"][0]["title"] == "生活随笔"


def test_detail_returns_full_fields(client):
    register_and_login(client)
    uid = create_note(client, title="详情", content="# 正文")
    detail = client.get("/api/notes/%d" % uid).get_json()["data"]
    assert detail["content"] == "# 正文"
    assert detail["has_password"] is False
    assert detail["favorited"] is False
    assert detail["is_owner"] is True


def test_detail_not_found(client):
    register_and_login(client)
    # 路由确实存在：本人笔记可读
    assert client.get("/api/notes/%d" % create_note(client)).status_code == 200
    r = client.get("/api/notes/9999")
    assert r.status_code == 404
    assert r.get_json()["code"] == "NOT_FOUND"


def test_detail_others_note_forbidden(app, client):
    register_and_login(client)
    uid = create_note(client, title="A 的笔记")

    other = app.test_client()
    register_and_login(other, email="b@b.com", username="阿波")
    r = other.get("/api/notes/%d" % uid)
    assert r.status_code == 403
    assert r.get_json()["code"] == "FORBIDDEN"


def test_update_note(client):
    register_and_login(client)
    uid = create_note(client, title="旧标题", content="旧正文")
    before = client.get("/api/notes/%d" % uid).get_json()["data"]["updated_at"]

    # 时间戳为秒级，跨过一秒边界才能稳定观察到 updated_at 变大
    time.sleep(1.1)
    r = client.put("/api/notes/%d" % uid, json={
        "title": "新标题", "content": "新正文", "tags": "标签", "status": "published"})
    assert r.status_code == 200

    detail = client.get("/api/notes/%d" % uid).get_json()["data"]
    assert detail["title"] == "新标题"
    assert detail["content"] == "新正文"
    assert detail["tags"] == "标签"
    assert detail["status"] == "published"
    assert detail["updated_at"] > before


def test_update_others_note_forbidden(app, client):
    register_and_login(client)
    uid = create_note(client, title="A 的笔记")

    other = app.test_client()
    register_and_login(other, email="b@b.com", username="阿波")
    r = other.put("/api/notes/%d" % uid, json={"title": "篡改"})
    assert r.status_code == 403
    assert r.get_json()["code"] == "FORBIDDEN"


def test_delete_others_note_forbidden(app, client):
    register_and_login(client)
    uid = create_note(client, title="A 的笔记")

    other = app.test_client()
    register_and_login(other, email="b@b.com", username="阿波")
    r = other.delete("/api/notes/%d" % uid)
    assert r.status_code == 403
    assert r.get_json()["code"] == "FORBIDDEN"
    # 未被删除
    assert client.get("/api/notes/%d" % uid).status_code == 200


def test_delete_own_note_ok(client):
    register_and_login(client)
    uid = create_note(client)
    assert client.delete("/api/notes/%d" % uid).status_code == 200
    assert client.get("/api/notes/%d" % uid).status_code == 404


def test_notes_require_login(client):
    r = client.get("/api/notes")
    assert r.status_code == 401
    assert r.get_json()["code"] == "UNAUTHORIZED"


def test_list_summary_strips_markdown(client):
    register_and_login(client)
    create_note(client, title="带标记", content="# 标题\n正文内容")
    item = client.get("/api/notes").get_json()["data"]["items"][0]
    assert "#" not in item["summary"]
    assert len(item["summary"]) <= 80


def test_stats_counts(app, client):
    register_and_login(client)
    create_note(client, title="草稿", status="draft")
    published_id = create_note(client, title="已发布", status="published")
    add_favorite(app, "a@b.com", published_id)

    data = client.get("/api/notes/stats").get_json()["data"]
    assert data == {"draft": 1, "published": 1, "favorite": 1}


def test_recent_limit_and_order(client):
    register_and_login(client)
    ids = [create_note(client, title="N%d" % i) for i in range(3)]

    data = client.get("/api/notes/recent?limit=2").get_json()["data"]
    assert [item["id"] for item in data] == [ids[2], ids[1]]
    assert set(data[0].keys()) == {"id", "title", "status", "updated_at"}


def test_recent_default_limit(client):
    register_and_login(client)
    for i in range(6):
        create_note(client, title="N%d" % i)
    data = client.get("/api/notes/recent").get_json()["data"]
    assert len(data) == 5


def test_recent_limit_capped(client):
    register_and_login(client)
    for i in range(21):
        create_note(client, title="N%d" % i)
    data = client.get("/api/notes/recent?limit=100").get_json()["data"]
    assert len(data) == 20


def test_stats_require_login(client):
    r = client.get("/api/notes/stats")
    assert r.status_code == 401
    assert r.get_json()["code"] == "UNAUTHORIZED"
