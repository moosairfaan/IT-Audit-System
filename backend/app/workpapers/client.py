"""Anthropic Messages API client for workpaper drafts."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_MODEL = "claude-sonnet-4-5"
_URL = "https://api.anthropic.com/v1/messages"


class WorkpaperUnavailable(RuntimeError):
    """The model could not be called."""


class AnthropicClient:
    def complete(self, instructions: str, source_json: str) -> str:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise WorkpaperUnavailable("ANTHROPIC_API_KEY is not set")
        model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        body = json.dumps(
            {
                "model": model,
                "max_tokens": 4000,
                "system": instructions,
                "messages": [{"role": "user", "content": source_json}],
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            _URL,
            data=body,
            headers={
                "content-type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except TimeoutError as exc:
            raise WorkpaperUnavailable("The model did not respond in time. Try generating the workpaper again.") from exc
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise WorkpaperUnavailable(f"Anthropic request failed ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise WorkpaperUnavailable(f"Anthropic request failed: {exc.reason}") from exc
        blocks = payload.get("content", [])
        texts = [block.get("text", "") for block in blocks if block.get("type") == "text"]
        if not texts:
            raise WorkpaperUnavailable("Anthropic returned no text")
        return "\n".join(texts)
