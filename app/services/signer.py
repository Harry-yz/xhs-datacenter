from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any


def generate_nonce(length: int = 16) -> str:
    # 文档要求唯一随机字符串 nonce
    return secrets.token_hex(length // 2)


def build_sign_params(
    *,
    client_id: str,
    secret_key: str,
    params: dict[str, Any] | None = None,
    with_timestamp: bool = True,
    with_nonce: bool = True,
) -> dict[str, Any]:
    data: dict[str, Any] = dict(params or {})

    data["clientId"] = client_id

    # 文档要求 timestamp=now(秒)
    if with_timestamp and not data.get("timestamp"):
        data["timestamp"] = int(time.time())

    if with_nonce and not data.get("nonce"):
        data["nonce"] = generate_nonce()

    data["sign"] = generate_sign(data, secret_key)
    return data


def generate_sign(params: dict[str, Any], secret_key: str) -> str:
    """
    文档规则：
    1. 按参数名升序排列非空参数（包含 clientId，不包含 secretKey）
    2. 拼成 key=value&key2=value2...
    3. 末尾追加 &secretKey=xxx
    4. MD5 后转大写
    """
    items: list[tuple[str, str]] = []

    for key in sorted(params.keys()):
        value = params[key]
        if key == "sign":
            continue
        if value is None or value == "":
            continue

        if isinstance(value, list):
            # 文档里 tagList / entId 这类 GET Query 参数用逗号拼接更稳
            value_str = ",".join(str(v) for v in value if v not in (None, ""))
        elif isinstance(value, bool):
            value_str = "true" if value else "false"
        else:
            value_str = str(value)

        if value_str == "":
            continue

        items.append((key, value_str))

    string_a = "&".join(f"{k}={v}" for k, v in items)
    string_sign_temp = f"{string_a}&secretKey={secret_key}"
    return hashlib.md5(string_sign_temp.encode("utf-8")).hexdigest().upper()