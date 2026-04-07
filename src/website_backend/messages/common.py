from __future__ import annotations

__all__ = [
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


class MessageModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


MessageDict: TypeAlias = dict[str, Any]


def dump_message(message: MessageModel) -> MessageDict:
    return cast(MessageDict, message.model_dump(mode="json"))


def dump_message_json(message: MessageModel) -> str:
    return message.model_dump_json()
