"""Behavior tests for the public API of sheets_sync."""

from __future__ import annotations

import pytest

import sheets_sync


def test_normalize_trims_and_lowercases() -> None:
    assert sheets_sync.normalize("  Hello World ") == "hello world"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_rejects_blank_input(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        sheets_sync.normalize(value)


def test_version_is_semver() -> None:
    parts = sheets_sync.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
