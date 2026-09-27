"""认证接口测试：注册、登录、登出与当前用户。"""


def test_register_ok(client):
    r = client.post("/api/auth/register", json={
        "email": "a@b.com", "username": "阿明",
        "password": "123456", "confirm_password": "123456"})
    assert r.status_code == 200
    assert r.get_json()["code"] == "OK"
    assert r.get_json()["data"]["username"] == "阿明"


def test_register_duplicate_email(client):
    payload = {"email": "a@b.com", "username": "阿明", "password": "123456", "confirm_password": "123456"}
    client.post("/api/auth/register", json=payload)
    r = client.post("/api/auth/register", json={**payload, "username": "小明"})
    assert r.status_code == 409
    assert r.get_json()["code"] == "CONFLICT"
    assert r.get_json()["message"] == "邮箱已被注册"


def test_register_duplicate_username(client):
    payload = {"email": "a@b.com", "username": "阿明", "password": "123456", "confirm_password": "123456"}
    client.post("/api/auth/register", json=payload)
    r = client.post("/api/auth/register", json={**payload, "email": "c@d.com"})
    assert r.get_json()["code"] == "CONFLICT"
    assert r.get_json()["message"] == "昵称已被占用"


def test_register_bad_email(client):
    r = client.post("/api/auth/register", json={
        "email": "not-an-email", "username": "阿明", "password": "123456", "confirm_password": "123456"})
    assert r.get_json()["code"] == "PARAM_ERROR"


def test_register_password_mismatch(client):
    r = client.post("/api/auth/register", json={
        "email": "a@b.com", "username": "阿明", "password": "123456", "confirm_password": "654321"})
    assert r.get_json()["code"] == "PARAM_ERROR"


def test_register_short_password(client):
    r = client.post("/api/auth/register", json={
        "email": "a@b.com", "username": "阿明", "password": "123", "confirm_password": "123"})
    assert r.get_json()["code"] == "PARAM_ERROR"


def test_register_username_length(client):
    r = client.post("/api/auth/register", json={
        "email": "a@b.com", "username": "x", "password": "123456", "confirm_password": "123456"})
    assert r.get_json()["code"] == "PARAM_ERROR"


def test_login_ok_and_me(client):
    client.post("/api/auth/register", json={
        "email": "a@b.com", "username": "阿明", "password": "123456", "confirm_password": "123456"})
    r = client.post("/api/auth/login", json={"email": "a@b.com", "password": "123456"})
    assert r.get_json()["code"] == "OK"
    me = client.get("/api/auth/me")
    assert me.get_json()["data"]["username"] == "阿明"


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={
        "email": "a@b.com", "username": "阿明", "password": "123456", "confirm_password": "123456"})
    r = client.post("/api/auth/login", json={"email": "a@b.com", "password": "000000"})
    assert r.status_code == 400
    assert r.get_json()["code"] == "PASSWORD_ERROR"


def test_login_unknown_email_same_message(client):
    r = client.post("/api/auth/login", json={"email": "no@b.com", "password": "123456"})
    assert r.get_json()["code"] == "PASSWORD_ERROR"
    assert r.get_json()["message"] == "邮箱或密码错误"


def test_me_requires_login(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.get_json()["code"] == "UNAUTHORIZED"


def test_logout_clears_session(client):
    client.post("/api/auth/register", json={
        "email": "a@b.com", "username": "阿明", "password": "123456", "confirm_password": "123456"})
    client.post("/api/auth/login", json={"email": "a@b.com", "password": "123456"})
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").get_json()["code"] == "UNAUTHORIZED"
