# Python 04 API Client

Python port of `ruby/04_api_client`. Adds `Client` — takes a `PromptBuilder` and sends the assembled payload to the API via a single HTTP POST, returning the raw parsed JSON response.

## New Files

| File | Description |
|---|---|
| `src/boukensha/client.py` | `Client` — HTTP POST with exponential back-off retry |
| `src/boukensha/errors.py` | Updated with `ApiError` for failed HTTP requests |

## How It Works

```
PromptBuilder
      ↓
Client
      ↓
POST to API endpoint (urllib.request, no third-party libs)
      ↓
Raw JSON response (dict)
```

## `Client` API

| Method | Description |
|---|---|
| `Client(builder)` | Wraps any `PromptBuilder` |
| `client.call(*, max_output_tokens=1024)` | POSTs the payload and returns the parsed JSON response dict |

## Retry Behaviour

`Client` retries up to 3 times on network errors and HTTP 408/409/429/500/502/503/504. Back-off: `0.5 * 2^(attempt-1)` seconds. Raises `ApiError` if all retries are exhausted or on non-retryable HTTP errors.

## Run Example

```bash
cd week1_baseline/python/04_api_client
uv pip install -e .
python examples/example.py
```

Requires `ANTHROPIC_API_KEY` (or whichever provider is configured in `~/.boukensha/settings.yaml`).

## Run Tests

```bash
cd week1_baseline/python/04_api_client
uv pip install pytest
python -m pytest tests/ -v
```
