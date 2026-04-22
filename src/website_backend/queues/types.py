from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeAlias, TypeVar, TypedDict

MessageT = TypeVar("MessageT")


class AWSMessageAttributeValue(TypedDict):
    DataType: str
    StringValue: str


AWSMessageAttributes: TypeAlias = dict[str, AWSMessageAttributeValue]
AWSMessageAttributesMapping: TypeAlias = Mapping[str, AWSMessageAttributeValue]
SQSDeliveryFields: TypeAlias = Mapping[str, Any]
