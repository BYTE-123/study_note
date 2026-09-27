"""评论接口测试（设计文档 9.6 / 9.8）。

约定：
- ``GET /api/notes/<id>/comments`` 免登录可读，笔记不存在 → 404。
- ``POST /api/notes/<id>/comments`` 需登录；评论开关关闭 → 403 FORBIDDEN。
- ``DELETE /api/comments/<id>`` 需登录且仅作者可删。
- 内容去首尾空格后为空或 >500 字 → 400 PARAM_ERROR。
- 列表按 created_at ASC, id ASC；``is_self`` 依据当前 Session 判断。
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


def comments_url(note_id):
    return "/api/notes/%d/comments" % note_id


def list_comments(client, note_id):
    r = client.get(comments_url(note_id))
    assert r.status_code == 200, r.get_json()
    return r.get_json()["data"]


def post_comment(client, note_id, content):
    return client.post(comments_url(note_id), json={"content": content})


def test_list_comments_empty(app, client):
    register_and_login(client)
    note_id = create_note(client)

    # 免登录访客也能读列表，默认评论开启且为空
    guest = app.test_client()
    data = list_comments(guest, note_id)
    assert data["comments_enabled"] is True
    assert data["items"] == []


def test_post_comment_ok(client):
    register_and_login(client)
    note_id = create_note(client)

    r = post_comment(client, note_id, "第一条评论")
    assert r.status_code == 200
    assert r.get_json()["code"] == "OK"
    assert r.get_json()["data"]["content"] == "第一条评论"

    assert len(list_comments(client, note_id)["items"]) == 1


def test_post_comment_requires_login(client):
    register_and_login(client)
    note_id = create_note(client)

    other = client.application.test_client()
    r = post_comment(other, note_id, "匿名评论")
    assert r.status_code == 401
    assert r.get_json()["code"] == "UNAUTHORIZED"


def test_post_comment_when_disabled(client):
    register_and_login(client)
    note_id = create_note(client)
    client.put("/api/notes/%d/comment-setting" % note_id, json={"enabled": False})

    r = post_comment(client, note_id, "应该被拒绝")
    assert r.status_code == 403
    assert r.get_json()["code"] == "FORBIDDEN"
    assert r.get_json()["message"] == "评论已关闭"


def test_post_comment_empty_or_too_long(client):
    register_and_login(client)
    note_id = create_note(client)

    empty = post_comment(client, note_id, "   ")
    assert empty.status_code == 400
    assert empty.get_json()["code"] == "PARAM_ERROR"

    too_long = post_comment(client, note_id, "字" * 501)
    assert too_long.status_code == 400
    assert too_long.get_json()["code"] == "PARAM_ERROR"

    # 边界：恰好 500 字允许
    ok_500 = post_comment(client, note_id, "字" * 500)
    assert ok_500.status_code == 200


def test_delete_own_comment_ok(client):
    register_and_login(client)
    note_id = create_note(client)
    comment_id = post_comment(client, note_id, "待删除").get_json()["data"]["id"]

    r = client.delete("/api/comments/%d" % comment_id)
    assert r.status_code == 200
    assert r.get_json()["code"] == "OK"
    assert len(list_comments(client, note_id)["items"]) == 0


def test_delete_others_comment_forbidden(app, client):
    register_and_login(client)
    note_id = create_note(client)
    comment_id = post_comment(client, note_id, "A 的评论").get_json()["data"]["id"]

    other = app.test_client()
    register_and_login(other, email="b@b.com", username="阿波")
    r = other.delete("/api/comments/%d" % comment_id)
    assert r.status_code == 403
    assert r.get_json()["code"] == "FORBIDDEN"
    # 未被删除
    assert len(list_comments(client, note_id)["items"]) == 1


def test_comments_of_missing_note(client):
    register_and_login(client)

    r = client.get("/api/notes/9999/comments")
    assert r.status_code == 404
    assert r.get_json()["code"] == "NOT_FOUND"

    r = client.post("/api/notes/9999/comments", json={"content": "内容"})
    assert r.status_code == 404
    assert r.get_json()["code"] == "NOT_FOUND"


def test_delete_missing_comment(client):
    register_and_login(client)
    r = client.delete("/api/comments/9999")
    assert r.status_code == 404
    assert r.get_json()["code"] == "NOT_FOUND"


def test_comment_is_self_flag(app, client):
    register_and_login(client)
    note_id = create_note(client)
    mine = post_comment(client, note_id, "我自己的").get_json()["data"]["id"]

    other = app.test_client()
    register_and_login(other, email="b@b.com", username="阿波")
    theirs = post_comment(other, note_id, "别人的").get_json()["data"]["id"]

    # 以 A 的身份读取：自己的 true，他人的 false
    by_id = {item["id"]: item for item in list_comments(client, note_id)["items"]}
    assert by_id[mine]["is_self"] is True
    assert by_id[theirs]["is_self"] is False
    assert by_id[theirs]["user"] == {"id": by_id[theirs]["user"]["id"], "username": "阿波"}

    # 未登录访客一律 false
    guest = app.test_client()
    guest_by_id = {item["id"]: item for item in list_comments(guest, note_id)["items"]}
    assert guest_by_id[mine]["is_self"] is False


def test_comment_order_is_oldest_first(client):
    register_and_login(client)
    note_id = create_note(client)
    first = post_comment(client, note_id, "第一条").get_json()["data"]["id"]
    second = post_comment(client, note_id, "第二条").get_json()["data"]["id"]
    # 直接改库中时间，确保 created_at 有差异时排序仍为升序
    with client.application.app_context():
        models.execute("UPDATE comments SET created_at = ? WHERE id = ?",
                       ("2026-01-01T00:00:01", first))
        models.execute("UPDATE comments SET created_at = ? WHERE id = ?",
                       ("2026-01-01T00:00:02", second))

    ids = [item["id"] for item in list_comments(client, note_id)["items"]]
    assert ids == [first, second]
