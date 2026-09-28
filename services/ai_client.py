"""DeepSeek 流式客户端：把上游 SSE 逐块产出的内容交给调用方。

约定（设计文档 10.1 旅程 5）：
- 配置只从 ``current_app.config`` 读取（与 models.py 一致），便于测试用夹具覆盖；
- **未配置 Key 时在发起网络请求之前** 抛 ``AIUnavailableError``，避免无谓请求；
- 上游非 200 同样抛 ``AIUnavailableError``，且异常文案不含密钥；
- ``timeout=30`` 防止上游挂死拖垮工作进程。
"""
import json

import requests
from flask import current_app

# 润色提示词：固定话术，要求只返回润色后的文本本身
SYSTEM_PROMPT = (
    "你是一名中文写作助手。请对用户提供的文本进行润色优化，"
    "提升流畅度、清晰度与文采，保持原意与语言风格。"
    "只返回润色后的文本，不要解释，不要加引号或前后缀。"
)


class AIUnavailableError(Exception):
    """DeepSeek 不可用：缺 Key、上游报错或连接失败。异常文案不含密钥。"""


def polish_stream(text):
    """调用 DeepSeek 润色 ``text``，逐块 yield 生成的文本片段（生成器）。

    仅在迭代时才会真正发起请求，因此「缺 Key 直接抛错」也发生在迭代阶段。
    """
    config = current_app.config
    base_url = config["DEEPSEEK_BASE_URL"].rstrip("/")
    api_key = config["DEEPSEEK_API_KEY"]
    model = config["DEEPSEEK_MODEL"]

    if not api_key:
        # 无 Key 时绝不出网；文案不回显任何配置细节
        raise AIUnavailableError("未配置 DEEPSEEK_API_KEY")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "stream": True,
        "temperature": 0.7,
    }

    response = requests.post(
        base_url + "/chat/completions",
        json=payload,
        headers={"Authorization": "Bearer " + api_key},
        stream=True,
        timeout=30,
    )

    if response.status_code != 200:
        raise AIUnavailableError("AI 服务返回状态码 %s" % response.status_code)

    for raw_line in response.iter_lines():
        if not raw_line:
            continue
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        if not line.startswith("data: "):
            continue
        data = line[len("data: "):].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except ValueError:
            # 单帧脏数据不应中断整条流
            continue
        choices = chunk.get("choices") or []
        if not choices:
            continue
        content = (choices[0].get("delta") or {}).get("content")
        if content:
            yield content
