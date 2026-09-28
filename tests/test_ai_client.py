"""DeepSeek 客户端测试：提示词、缺 Key 兜底与流式解析。

全部基于伪造的 ``requests.post`` 响应，不发起任何真实网络请求。
"""
import json

import pytest

from services import ai_client

TARGET_TEXT = "这是原始文本"


class FakeResponse:
    """伪造 requests 流式响应：只暴露 ``polish_stream`` 实际使用的接口。"""

    def __init__(self, lines, status_code=200):
        self.status_code = status_code
        self._lines = lines

    def iter_lines(self):
        for line in self._lines:
            yield line


def sse_line(payload):
    """一行 SSE 文本 → ``iter_lines()`` 产出的 bytes。"""
    return ("data: " + payload).encode("utf-8")


def delta_line(content):
    """构造一行 ``choices[0].delta.content`` 帧。"""
    body = {"choices": [{"delta": {"content": content}}]}
    return sse_line(json.dumps(body, ensure_ascii=False))


def test_missing_api_key_raises(app, monkeypatch):
    """未配置 Key 时抛 AIUnavailableError，且不发起网络请求。"""

    def explode(*args, **kwargs):
        raise AssertionError("缺少 Key 时不允许发起网络请求")

    monkeypatch.setattr(ai_client.requests, "post", explode)

    with app.app_context():
        app.config["DEEPSEEK_API_KEY"] = ""
        with pytest.raises(ai_client.AIUnavailableError):
            list(ai_client.polish_stream(TARGET_TEXT))


def test_polish_prompt_contains_text(app, monkeypatch):
    """请求体：system 固定润色提示词，user 为目标文本。"""
    captured = {}

    def fake_post(url, json=None, **kwargs):
        captured["url"] = url
        captured["payload"] = json
        return FakeResponse([delta_line("优化"), sse_line("[DONE]")])

    monkeypatch.setattr(ai_client.requests, "post", fake_post)

    with app.app_context():
        app.config.update(
            DEEPSEEK_API_KEY="test-key",
            DEEPSEEK_BASE_URL="https://api.example.com/v1",
            DEEPSEEK_MODEL="deepseek-chat",
        )
        list(ai_client.polish_stream(TARGET_TEXT))

    system = captured["payload"]["messages"][0]
    user = captured["payload"]["messages"][1]
    assert system["role"] == "system"
    assert "润色" in system["content"]
    assert "只返回润色后的文本" in system["content"]
    assert user == {"role": "user", "content": TARGET_TEXT}
    assert captured["payload"]["stream"] is True
    assert captured["url"] == "https://api.example.com/v1/chat/completions"


def test_stream_yields_deltas(app, monkeypatch):
    """逐块产出 content，跳过空行与空 content，遇到 [DONE] 立即结束。"""
    lines = [
        delta_line("优化后的"),
        b"",                       # 空行需跳过
        delta_line("文本"),
        delta_line(None),          # content 为空需跳过
        sse_line("[DONE]"),
        delta_line("不应出现"),
    ]
    monkeypatch.setattr(ai_client.requests, "post", lambda *a, **k: FakeResponse(lines))

    with app.app_context():
        app.config.update(DEEPSEEK_API_KEY="test-key")
        chunks = list(ai_client.polish_stream(TARGET_TEXT))

    assert chunks == ["优化后的", "文本"]


def test_upstream_http_error_raises_without_leaking_key(app, monkeypatch):
    """上游非 200 → AIUnavailableError，且异常文案不含密钥。"""
    monkeypatch.setattr(
        ai_client.requests, "post",
        lambda *a, **k: FakeResponse([b""], status_code=500))

    with app.app_context():
        app.config.update(DEEPSEEK_API_KEY="secret-key-should-not-leak")
        with pytest.raises(ai_client.AIUnavailableError) as excinfo:
            list(ai_client.polish_stream(TARGET_TEXT))

    assert "secret-key-should-not-leak" not in str(excinfo.value)
