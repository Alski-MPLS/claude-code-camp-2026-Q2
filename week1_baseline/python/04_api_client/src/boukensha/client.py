"""Boukensha::Client port: makes the HTTP POST and returns the parsed JSON response.

Uses Python stdlib urllib.request — no third-party HTTP library, matching the
Ruby implementation's 'no gems' principle.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from .errors import ApiError

RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
MAX_RETRIES = 3
BASE_RETRY_DELAY = 0.5


class Client:
    def __init__(self, builder: Any) -> None:
        self._builder = builder

    def call(self, *, max_output_tokens: int = 1024) -> dict[str, Any]:
        url = self._builder.url
        payload = self._builder.to_api_payload(max_output_tokens=max_output_tokens)
        body = json.dumps(payload).encode()
        headers = self._builder.headers

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        attempts = 0
        while True:
            attempts += 1
            try:
                with urllib.request.urlopen(req) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code in RETRYABLE_STATUS_CODES and attempts < MAX_RETRIES:
                    time.sleep(_retry_delay(attempts))
                    continue
                body_text = e.read().decode(errors="replace")
                raise ApiError(
                    f"API request failed after {attempts} attempt{'s' if attempts != 1 else ''}"
                    f" ({e.code}): {body_text}"
                ) from e
            except urllib.error.URLError as e:
                if attempts < MAX_RETRIES:
                    time.sleep(_retry_delay(attempts))
                    continue
                raise ApiError(
                    f"API request failed after {attempts} attempts: {type(e).__name__}: {e.reason}"
                ) from e


def _retry_delay(attempt: int) -> float:
    return BASE_RETRY_DELAY * (2 ** (attempt - 1))
