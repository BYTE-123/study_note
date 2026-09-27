"""收藏接口测试（设计文档 9.5）。

约定：
- ``POST /api/notes/<id>/favorite`` 需登录；未分享的他人笔记既不可读也不可收藏 → 403。
- 切换语义：无记录则插入，有记录则删除，返回最新 ``{favorited}``。
- ``GET /api/favorites`` 需登录、分页；``is_available`` = 自有 或 笔记 ``is_shared=1``。
- 详情页与分享页的 ``favorited`` 依据当前登录用户计算。
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


def toggle_favorite(client, note_id):
    return client.post("/api/notes/%d/favorite" % note_id)


def share_token(client, note_id):
    r = client.put("/api/notes/%d/share" % note_id, json={"enabled": True})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["data"]["share_token"]


def test_toggle_favorite_on_then_off(client):
    register_and_login(client)
    note_id = create_note(client)

    first = toggle_favorite(client, note_id)
    assert first.status_code == 200
    assert first.get_json()["data"]["favorited"] is True

    second = toggle_favorite(client, note_id)
    assert second.status_code == 200
    assert second.get_json()["data"]["favorited"] is False


def test_favorite_requires_login(client):
    register_and_login(client)
    note_id = create_note(client)

    guest = client.application.test_client()
    r = toggle_favorite(guest, note_id)
    assert r.status_code == 401
    assert r.get_json()["code"] == "UNAUTHORIZED"


def test_favorite_missing_note(client):
    register_and_login(client)
    r = toggle_favorite(client, 9999)
    assert r.status_code == 404
    assert r.get_json()["code"] == "NOT_FOUND"


def test_favorite_own_note_allowed(client):
    register_and_login(client)
    note_id = create_note(client)
    r = toggle_favorite(client, note_id)
    assert r.status_code == 200
    assert r.get_json()["data"]["favorited"] is True


def test_favorite_shared_note_allowed(app, client):
    register_and_login(client)
    owner = app.test_client()
    register_and_login(owner, email="b@b.com", username="阿波")
    note_id = create_note(owner, status="published")
    share_token(owner, note_id)

    r = toggle_favorite(client, note_id)
    assert r.status_code == 200
    assert r.get_json()["data"]["favorited"] is True


def test_favorite_private_note_of_other_forbidden(app, client):
    register_and_login(client)
    owner = app.test_client()
    register_and_login(owner, email="b@b.com", username="阿波")
    note_id = create_note(owner, status="published")

    r = toggle_favorite(client, note_id)
    assert r.status_code == 403
    assert r.get_json()["code"] == "FORBIDDEN"


def test_list_favorites_with_availability(app, client):
    register_and_login(client)
    owner = app.test_client()
    register_and_login(owner, email="b@b.com", username="阿波")
    note_id = create_note(owner, title="B 的分享文", status="published")
    share_token(owner, note_id)

    assert toggle_favorite(client, note_id).status_code == 200
    data = client.get("/api/favorites").get_json()["data"]
    assert set(data.keys()) == {"total", "page", "page_size", "items"}
    assert data["total"] == 1
    item = data["items"][0]
    assert item["note_id"] == note_id
    assert item["title"] == "B 的分享文"
    assert item["owner"] == "阿波"
    assert item["is_self"] is False
    assert item["is_available"] is True

    # B 关闭分享后，该项内容失效但仍在列表中
    owner.put("/api/notes/%d/share" % note_id, json={"enabled": False})
    data = client.get("/api/favorites").get_json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["is_available"] is False


def test_list_favorites_self_flag(client):
    register_and_login(client)
    note_id = create_note(client, title="我的笔记")
    toggle_favorite(client, note_id)

    item = client.get("/api/favorites").get_json()["data"]["items"][0]
    assert item["is_self"] is True
    assert item["owner"] == "阿明"
    assert item["is_available"] is True


def test_list_favorites_requires_login(client):
    r = client.get("/api/favorites")
    assert r.status_code == 401
    assert r.get_json()["code"] == "UNAUTHORIZED"


def test_list_favorites_order_newest_first(app, client):
    register_and_login(client)
    first = create_note(client, title="先收藏")
    second = create_note(client, title="后收藏")
    toggle_favorite(client, first)
    toggle_favorite(client, second)
    with app.app_context():
        models.execute("UPDATE favorites SET created_at = ? WHERE note_id = ?",
                       ("2026-01-01T00:00:01", first))
        models.execute("UPDATE favorites SET created_at = ? WHERE note_id = ?",
                       ("2026-01-01T00:00:02", second))

    titles = [item["title"] for item in client.get("/api/favorites").get_json()["data"]["items"]]
    assert titles == ["后收藏", "先收藏"]


def test_favorited_reflected_in_detail_and_share(app, client):
    register_and_login(client)
    # 自有笔记：详情 favorited 反映收藏状态
    uid = create_note(client, status="published")
    toggle_favorite(client, uid)
    detail = client.get("/api/notes/%d" % uid).get_json()["data"]
    assert detail["favorited"] is True
    assert detail["is_owner"] is True

    # 他人分享笔记：分享读取 favorited=true（A 已收藏）
    owner = app.test_client()
    register_and_login(owner, email="b@b.com", username="阿波")
    bid = create_note(owner, status="published")
    token = share_token(owner, bid)

    shared = client.post("/api/share/%s" % token, json={}).get_json()["data"]
    assert shared["favorited"] is False

    toggle_favorite(client, bid)
    shared = client.post("/api/share/%s" % token, json={}).get_json()["data"]
    assert shared["favorited"] is True
    assert shared["is_owner"] is False
