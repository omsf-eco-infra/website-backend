from __future__ import annotations

import json
import os
from collections.abc import Mapping


def required_env_from(source: Mapping[str, str], name: str) -> str:
    value = source.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def required_env(name: str) -> str:
    return required_env_from(os.environ, name)


def parse_json_string_list(raw_value: str, *, name: str) -> tuple[str, ...]:
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Environment variable {name} must be a JSON array of non-empty strings."
        ) from exc

    if not isinstance(parsed, list):
        raise RuntimeError(
            f"Environment variable {name} must be a JSON array of non-empty strings."
        )

    values: list[str] = []
    for item in parsed:
        if not isinstance(item, str):
            raise RuntimeError(
                f"Environment variable {name} must be a JSON array of non-empty strings."
            )
        normalized = item.strip()
        if not normalized:
            raise RuntimeError(
                f"Environment variable {name} must be a JSON array of non-empty strings."
            )
        values.append(normalized)

    if not values:
        raise RuntimeError(
            f"Environment variable {name} must be a JSON array of non-empty strings."
        )

    return tuple(values)
