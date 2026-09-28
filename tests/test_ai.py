"""AI 润色接口测试：登录校验、参数边界、SSE 帧、异常帧与频率限制。

全部 monkeypatch ``services.ai_client.polish_stream``，不发起真实网络请求。
"""
from services import ai_client


def register_and_login(client, email="ai@b.com", username="小艾"):
    """注册并登录一个用户，返回同一个 client（已带 Session）。"""
    client.post("/api/auth/register", json={
        "email": email, "username": username,
        "password": "123456", "confirm_password": "123456"})
    client.post("/api/auth/login", json={"email": email, "password": "123456"})
    return client


def fake_stream(chunks):
    """构造一个逐块产出 ``chunks`` 的伪 polish_stream。"""

    def _stream(text):
        for chunk in chunks:
            yield chunk

    return _stream


def sse_frames(response):
    """把响应体切成 ``data: `` 后的帧负载列表。"""
    body = response.get_data(as_text=True)
    return [line[len("data: "):] for line in body.split("\n\n")
            if line.startswith("data: ")]


def test_polish_requires_login(client):
    r = client.post("/api/ai/polish", json={"text": "你好"})
    assert r.status_code == 401
    assert r.get_json()["code"] == "UNAUTHORIZED"


def test_polish_empty_text(client):
    register_and_login(client)
    r = client.post("/api/ai/polish", json={"text": ""})
    assert r.status_code == 400
    assert r.get_json()["code"] == "PARAM_ERROR"


def test_polish_too_long(client):
    register_and_login(client)
    r = client.post("/api/ai/polish", json={"text": "字" * 2001})
    assert r.status_code == 400
    assert r.get_json()["code"] == "PARAM_ERROR"


def test_polish_streams_deltas(client, monkeypatch):
    """正常流：逐块转发 delta 帧，结尾补 [DONE]，并带关闭缓冲的响应头。"""
    register_and_login(client)
    monkeypatch.setattr(ai_client, "polish_stream", fake_stream(["优", "化"]))

    r = client.post("/api/ai/polish", json={"text": "原始文本"})

    assert r.status_code == 200
    assert r.mimetype == "text/event-stream"
    assert r.headers["Cache-Control"] == "no-cache"
    assert r.headers["X-Accel-Buffering"] == "no"
    assert sse_frames(r) == [
        '{"delta": "优"}',
        '{"delta": "化"}',
        "[DONE]",
    ]


def test_polish_upstream_error_frame(client, monkeypatch):
    """上游不可用 → 单帧中文错误 + [DONE]，不泄漏原始异常文本。"""
    register_and_login(client)

    def boom(text):
        raise ai_client.AIUnavailableError("connect timeout to https://api.deepseek.com")

    monkeypatch.setattr(ai_client, "polish_stream", boom)

    r = client.post("/api/ai/polish", json={"text": "原始文本"})

    assert r.status_code == 200
    assert sse_frames(r) == [
        '{"error": "AI 服务暂时不可用，请稍后重试"}',
        "[DONE]",
    ]
    assert "api.deepseek.com" not in r.get_data(as_text=True)


def test_polish_unexpected_error_frame(client, monkeypatch):
    """未预期异常同样收敛为中文错误帧，不冒泡成 500。"""
    register_and_login(client)

    def boom(text):
        raise RuntimeError("internal detail")

    monkeypatch.setattr(ai_client, "polish_stream", boom)

    r = client.post("/api/ai/polish", json={"text": "原始文本"})

    assert r.status_code == 200
    assert sse_frames(r) == [
        '{"error": "AI 服务暂时不可用，请稍后重试"}',
        "[DONE]",
    ]
    assert "internal detail" not in r.get_data(as_text=True)


def test_closing_stream_early_is_clean(client, monkeypatch):
    """客户端中途断开（前端 AbortController）时关闭生成器不得抛错。"""
    register_and_login(client)
    monkeypatch.setattr(ai_client, "polish_stream", fake_stream(["优", "化"]))

    response = client.post("/api/ai/polish", json={"text": "原始文本"}, buffered=False)
    iterator = iter(response.response)
    assert next(iterator)
    iterator.close()  # 模拟客户端中断；生成器不得在关闭时继续 yield


def test_polish_rate_limit(client, app, monkeypatch):
    """超过 AI_RATE_LIMIT_PER_MINUTE 后返回 429 RATE_LIMIT，且不再打开流。"""
    register_and_login(client)
    app.config["AI_RATE_LIMIT_PER_MINUTE"] = 2
    monkeypatch.setattr(ai_client, "polish_stream", fake_stream(["优"]))

    for _ in range(2):
        r = client.post("/api/ai/polish", json={"text": "原始文本"})
        assert r.status_code == 200
        assert r.mimetype == "text/event-stream"
        r.get_data()  # 消费响应体，模拟真实客户端读完这条流

    third = client.post("/api/ai/polish", json={"text": "原始文本"})
    assert third.status_code == 429
    assert third.get_json()["code"] == "RATE_LIMIT"


def test_rate_limit_is_per_user(client, app, monkeypatch):
    """频率限制按用户计数：一个用户被限流不影响另一个用户。"""
    app.config["AI_RATE_LIMIT_PER_MINUTE"] = 1
    monkeypatch.setattr(ai_client, "polish_stream", fake_stream(["优"]))

    first = register_and_login(client)
    assert first.post("/api/ai/polish", json={"text": "原始文本"}).status_code == 200
    first.post("/api/ai/polish", json={"text": "原始文本"}).get_data()
    assert first.post("/api/ai/polish", json={"text": "原始文本"}).status_code == 429

    other = app.test_client()
    register_and_login(other, email="ai2@b.com", username="小艾二号")
    assert other.post("/api/ai/polish", json={"text": "原始文本"}).status_code == 200
    other.post("/api/ai/polish", json={"text": "原始文本"}).get_data()
