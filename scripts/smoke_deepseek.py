"""Production smoke check for the DeepSeek-compatible text route.

Usage: set DEEPSEEK_API_KEY, then run ``python scripts/smoke_deepseek.py``.
The key is read only from the environment and is never printed.
"""
from __future__ import annotations

import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request(url: str, key: str, payload: dict | None = None, timeout: float = 15.0) -> dict:
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    with urlopen(Request(url, data=data, headers=headers), timeout=timeout) as response:
        return json.load(response)


def main() -> int:
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        print("SKIP: DEEPSEEK_API_KEY is not configured")
        return 2
    base = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    started = time.monotonic()
    try:
        models = request(f"{base}/models", key)
        available = {item.get("id") for item in models.get("data", []) if isinstance(item, dict)}
        print(f"PASS: /models ({len(available)} models)")
        result = request(f"{base}/chat/completions", key, {"model": model, "messages": [{"role": "user", "content": "Reply with exactly: smoke-ok"}], "stream": False})
        text = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not text:
            print("FAIL: generation returned empty content")
            return 1
        print(f"PASS: generation model={model} chars={len(text)} latency_ms={int((time.monotonic() - started) * 1000)}")
        stream_request = Request(f"{base}/chat/completions", data=json.dumps({"model": model, "messages": [{"role": "user", "content": "Count from one to three."}], "stream": True}).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "text/event-stream"})
        chunks = 0
        with urlopen(stream_request, timeout=20) as response:
            for line in response:
                if line.startswith(b"data:") and b"[DONE]" not in line:
                    chunks += 1
        if chunks == 0:
            print("FAIL: streaming returned no delta events")
            return 1
        print(f"PASS: streaming delta_events={chunks}")
        return 0
    except HTTPError as exc:
        print(f"FAIL: HTTP {exc.code} from provider")
    except (URLError, TimeoutError) as exc:
        print(f"FAIL: network {type(exc).__name__}")
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        print(f"FAIL: invalid provider response ({type(exc).__name__})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
