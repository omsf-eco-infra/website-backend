from __future__ import annotations

from website_backend.queues.types import AWSMessageAttributes, MessageT


def derive_message_attributes(message: MessageT) -> AWSMessageAttributes:
    """Build default AWS string message attributes from common message fields.

    Parameters
    ----------
    message : MessageT
        Message object to inspect.

    Returns
    -------
    AWSMessageAttributes
        AWS-compatible message attributes derived from `version`,
        `message_type`, and `task_type` when those fields are present.
    """
    attributes: AWSMessageAttributes = {}
    for field_name in ("version", "message_type", "task_type"):
        value = getattr(message, field_name, None)
        if value is None:
            continue
        attributes[field_name] = {
            "DataType": "String",
            "StringValue": str(value),
        }
    return attributes
