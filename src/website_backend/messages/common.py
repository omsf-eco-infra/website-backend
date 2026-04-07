from __future__ import annotations

__all__ = [
    "CURRENT_CONTRACT_VERSION",
    "GraphId",
    "MessageModel",
    "NonEmptyStr",
    "OpaqueDetails",
    "RunId",
    "TaskId",
    "TaskType",
    "UrlMap",
    "Version",
    "WorkflowName",
    "dump_message",
    "dump_message_json",
    "validate_contract_version",
]

from typing import Annotated, Any, TypeAlias, cast

from pydantic import AnyUrl, BaseModel, ConfigDict, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
Version = NonEmptyStr
WorkflowName = NonEmptyStr
RunId = NonEmptyStr
GraphId = NonEmptyStr
TaskId = NonEmptyStr
TaskType = NonEmptyStr
OpaqueDetails: TypeAlias = dict[str, Any]
UrlMap: TypeAlias = dict[NonEmptyStr, AnyUrl]
CURRENT_CONTRACT_VERSION: Version = "2026.04"


class MessageModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


MessageDict: TypeAlias = dict[str, Any]


def dump_message(message: MessageModel) -> MessageDict:
    return cast(MessageDict, message.model_dump(mode="json"))


def dump_message_json(message: MessageModel) -> str:
    return message.model_dump_json()


def validate_contract_version(version: Version) -> None:
    if version != CURRENT_CONTRACT_VERSION:
        raise ValueError(
            "Message version does not match current contract version: "
            f"{version!r} != {CURRENT_CONTRACT_VERSION!r}"
        )
