from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import http.client
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class LLMError(RuntimeError):
    pass


@dataclass
class LLMResponse:
    provider: str
    model: str
    text: str
    raw: Dict[str, Any]


class ClaudeClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 120,
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model or os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
        self.base_url = (base_url or os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")).rstrip("/")
        self.timeout = timeout

    def complete(self, prompt: str, system: Optional[str] = None, max_tokens: int = 1200) -> LLMResponse:
        if not self.api_key:
            raise LLMError("Missing ANTHROPIC_API_KEY")
        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        raw = _post_json(
            url=f"{self.base_url}/v1/messages",
            payload=payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=self.timeout,
        )
        return LLMResponse(provider="claude", model=self.model, text=_extract_claude_text(raw), raw=raw)


class MiroMindClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 300,
    ):
        self.api_key = api_key or os.environ.get("MIROMIND_API_KEY")
        self.model = model or os.environ.get("MIROMIND_MODEL", "mirothinker-1-7-deepresearch-mini")
        self.base_url = (base_url or os.environ.get("MIROMIND_BASE_URL", "https://api.miromind.ai")).rstrip("/")
        self.timeout = timeout

    def chat(self, messages: List[Dict[str, str]], max_tokens: int = 1600) -> LLMResponse:
        if not self.api_key:
            raise LLMError("Missing MIROMIND_API_KEY")
        raw = _post_json(
            url=f"{self.base_url}/v1/chat/completions",
            payload={
                "model": self.model,
                "messages": messages,
                "stream": False,
                "max_tokens": max_tokens,
            },
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )
        return LLMResponse(provider="miromind", model=self.model, text=_extract_openai_chat_text(raw), raw=raw)

    def deep_research(self, prompt: str, max_output_tokens: int = 2400, background: bool = False) -> LLMResponse:
        if not self.api_key:
            raise LLMError("Missing MIROMIND_API_KEY")
        payload: Dict[str, Any] = {
            "model": self.model,
            "input": prompt,
            "max_output_tokens": max_output_tokens,
        }
        if background:
            payload["background"] = True
        else:
            payload["stream"] = False
        raw = _post_json(
            url=f"{self.base_url}/v1/responses",
            payload=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )
        return LLMResponse(provider="miromind", model=self.model, text=_extract_miromind_response_text(raw), raw=raw)

    def get_response(self, response_id: str) -> Dict[str, Any]:
        if not self.api_key:
            raise LLMError("Missing MIROMIND_API_KEY")
        return _request_json(
            request=urllib.request.Request(
                f"{self.base_url}/v1/responses/{response_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                method="GET",
            ),
            timeout=self.timeout,
        )


def _post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: int) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    return _request_json(request, timeout)


def _request_json(request: urllib.request.Request, timeout: int) -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise LLMError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"Network error: {exc}") from exc
    except http.client.IncompleteRead as exc:
        raise LLMError(f"Incomplete response from provider: {exc}") from exc
    except TimeoutError as exc:
        raise LLMError(f"Request timed out: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LLMError(f"Invalid JSON response: {exc}") from exc


def _extract_claude_text(raw: Dict[str, Any]) -> str:
    parts: List[str] = []
    for item in raw.get("content", []):
        if item.get("type") == "text":
            parts.append(item.get("text", ""))
    return "\n".join(part for part in parts if part).strip()


def _extract_openai_chat_text(raw: Dict[str, Any]) -> str:
    choices = raw.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    return str(message.get("content", "")).strip()


def _extract_miromind_response_text(raw: Dict[str, Any]) -> str:
    if raw.get("status") == "in_progress" and raw.get("id"):
        return f"Background research started: {raw['id']}"

    parts: List[str] = []
    for item in raw.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                parts.append(content.get("text", ""))
    if parts:
        return "\n".join(part for part in parts if part).strip()
    if "output_text" in raw:
        return str(raw["output_text"]).strip()
    return ""
