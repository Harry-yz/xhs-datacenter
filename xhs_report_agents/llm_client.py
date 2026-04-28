from __future__ import annotations

import json
import time
from typing import Any

import requests

from .config import Settings


class LLMError(RuntimeError):
    pass


class DeepSeekClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def complete_json(self, *, system: str, user: str, temperature: float = 0.2, model: str | None = None) -> dict[str, Any]:
        url = f"{self.settings.deepseek_base_url}/chat/completions"
        payload = {
            "model": model or self.settings.deepseek_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(self.settings.llm_max_retries + 1):
            try:
                resp = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.settings.request_timeout_seconds,
                )
                if resp.status_code >= 400:
                    raise LLMError(f"DeepSeek API error {resp.status_code}: {resp.text[:500]}")
                content = resp.json()["choices"][0]["message"]["content"]
                return _loads_json_object(content)
            except Exception as exc:
                last_error = exc
                if attempt < self.settings.llm_max_retries:
                    time.sleep(1.5 * (attempt + 1))
        raise LLMError(str(last_error))


def _loads_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM did not return valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMError("LLM JSON response must be an object")
    return data
