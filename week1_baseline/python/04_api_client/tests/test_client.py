from boukensha.errors import ApiError, UnknownToolError, UnsupportedModelError


def test_api_error_is_exception():
    err = ApiError("boom")
    assert isinstance(err, Exception)
    assert str(err) == "boom"


def test_existing_errors_still_present():
    assert issubclass(UnknownToolError, Exception)
    assert issubclass(UnsupportedModelError, Exception)


import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from io import BytesIO

from boukensha.client import Client
from boukensha.errors import ApiError


def _make_builder(url="https://api.example.com/v1/messages", payload=None):
    builder = MagicMock()
    builder.url = url
    builder.headers = {"Content-Type": "application/json", "x-api-key": "test-key"}
    builder.to_api_payload.return_value = payload or {"model": "test", "messages": []}
    return builder


def _fake_response(body: dict, status: int = 200):
    raw = json.dumps(body).encode()
    resp = MagicMock()
    resp.read.return_value = raw
    resp.status = status
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def test_client_returns_parsed_json():
    builder = _make_builder()
    expected = {"id": "msg_01", "content": [{"type": "text", "text": "Hello"}]}
    with patch("boukensha.client.urllib.request.urlopen", return_value=_fake_response(expected)):
        result = Client(builder).call()
    assert result == expected


def test_client_passes_max_output_tokens():
    builder = _make_builder()
    with patch("boukensha.client.urllib.request.urlopen", return_value=_fake_response({})) as mock_open:
        Client(builder).call(max_output_tokens=512)
    builder.to_api_payload.assert_called_once_with(max_output_tokens=512)


def test_client_raises_api_error_on_http_error():
    builder = _make_builder()
    http_err = HTTPError(
        url="https://api.example.com/v1/messages",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=BytesIO(b'{"error": "bad key"}'),
    )
    with patch("boukensha.client.urllib.request.urlopen", side_effect=http_err):
        try:
            Client(builder).call()
            assert False, "Expected ApiError"
        except ApiError as e:
            assert "401" in str(e)


def test_client_retries_on_transient_error_then_succeeds():
    builder = _make_builder()
    expected = {"id": "msg_02", "content": []}
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise URLError("connection reset")
        return _fake_response(expected)

    with patch("boukensha.client.urllib.request.urlopen", side_effect=side_effect):
        with patch("boukensha.client.time.sleep"):
            result = Client(builder).call()
    assert result == expected
    assert call_count == 2


def test_client_raises_after_max_retries():
    builder = _make_builder()
    with patch("boukensha.client.urllib.request.urlopen", side_effect=URLError("reset")):
        with patch("boukensha.client.time.sleep"):
            try:
                Client(builder).call()
                assert False, "Expected ApiError"
            except ApiError as e:
                assert "3" in str(e)


def test_top_level_exports():
    import boukensha
    assert hasattr(boukensha, "Client")
    assert hasattr(boukensha, "ApiError")
    assert hasattr(boukensha, "Config")
    assert hasattr(boukensha, "PromptBuilder")
