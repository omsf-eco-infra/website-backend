from __future__ import annotations

import pytest

from website_backend.runtime import required_env


def test_required_env_returns_present_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXAMPLE_ENV", "configured-value")

    assert required_env("EXAMPLE_ENV") == "configured-value"


@pytest.mark.parametrize("value", [None, ""])
def test_required_env_rejects_missing_or_empty_value(
    monkeypatch: pytest.MonkeyPatch,
    value: str | None,
) -> None:
    if value is None:
        monkeypatch.delenv("EXAMPLE_ENV", raising=False)
    else:
        monkeypatch.setenv("EXAMPLE_ENV", value)

    with pytest.raises(RuntimeError, match="Missing required environment variable"):
        required_env("EXAMPLE_ENV")
