"""ISBN validation tests."""

import pytest

from app.isbn import normalize_isbn


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("978-0-306-40615-7", "9780306406157"),
        ("0-306-40615-2", "0306406152"),
        ("0-8044-2957-X", "080442957X"),
        ("", None),
        (None, None),
    ],
)
def test_normalizes_valid_optional_isbn(value: str | None, expected: str | None) -> None:
    assert normalize_isbn(value) == expected


@pytest.mark.parametrize("value", ["9780306406158", "0306406153", "123", "9780306406157X"])
def test_rejects_invalid_isbn(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_isbn(value)