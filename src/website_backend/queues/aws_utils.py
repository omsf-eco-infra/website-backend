from __future__ import annotations

from typing import TypeVar

MessageT = TypeVar("MessageT")


def derive_message_attributes(message: MessageT) -> dict[str, dict[str, str]]:
    """Build default AWS string message attributes from common message fields.

    Parameters
    ----------
    message : MessageT
        Message object to inspect.

    Returns
    -------
    dict[str, dict[str, str]]
        AWS-compatible message attributes derived from `version`,
        `message_type`, and `task_type` when those fields are present.
    """
    attributes: dict[str, dict[str, str]] = {}
    for field_name in ("version", "message_type", "task_type"):
        value = getattr(message, field_name, None)
        if value is None:
            continue
        attributes[field_name] = {
            "DataType": "String",
            "StringValue": str(value),
        }
    return attributes
