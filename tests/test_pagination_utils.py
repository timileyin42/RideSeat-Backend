import pytest

from app.utils.pagination import normalize_pagination


def test_normalize_pagination_defaults():
    pagination = normalize_pagination(None, None)
    assert pagination.limit == 50
    assert pagination.offset == 0


def test_normalize_pagination_caps_limit():
    pagination = normalize_pagination(200, 0, max_limit=100)
    assert pagination.limit == 100


def test_normalize_pagination_rejects_negative():
    with pytest.raises(ValueError):
        normalize_pagination(0, -1)
