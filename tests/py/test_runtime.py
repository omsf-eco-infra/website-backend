from __future__ import annotations

import json

import pytest

from website_backend.runtime import parse_json_string_list
from website_backend.runtime import required_env
from website_backend.runtime import required_env_from


def test_required_env_from_returns_present_value() -> None:
    assert required_env_from({"EXAMPLE_ENV": "configured-value"}, "EXAMPLE_ENV") == (
        "configured-value"
    )


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


@pytest.mark.parametrize("value", [None, ""])
def test_required_env_from_rejects_missing_or_empty_value(
    value: str | None,
) -> None:
    source: dict[str, str] = {}
    if value is not None:
        source["EXAMPLE_ENV"] = value

    with pytest.raises(RuntimeError, match="Missing required environment variable"):
        required_env_from(source, "EXAMPLE_ENV")


def test_parse_json_string_list_returns_normalized_values() -> None:
    assert parse_json_string_list(
        json.dumps([" subnet-123 ", "subnet-456"]),
        name="SUBNET_IDS",
    ) == ("subnet-123", "subnet-456")


@pytest.mark.parametrize(
    "raw_value",
    [
        '"subnet-123"',
        "not-json",
        "[]",
        json.dumps(["subnet-123", ""]),
        json.dumps(["subnet-123", 7]),
    ],
)
def test_parse_json_string_list_rejects_invalid_values(raw_value: str) -> None:
    with pytest.raises(
        RuntimeError,
        match="Environment variable SUBNET_IDS must be a JSON array of non-empty strings",
    ):
        parse_json_string_list(raw_value, name="SUBNET_IDS")
