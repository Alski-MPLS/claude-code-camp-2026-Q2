from boukensha.errors import ApiError, UnknownToolError, UnsupportedModelError


def test_api_error_is_exception():
    err = ApiError("boom")
    assert isinstance(err, Exception)
    assert str(err) == "boom"


def test_existing_errors_still_present():
    assert issubclass(UnknownToolError, Exception)
    assert issubclass(UnsupportedModelError, Exception)
