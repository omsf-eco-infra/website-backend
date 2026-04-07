from __future__ import annotations

__all__ = [
    "AddTasksDetails",
    "AddTasksMessage",
    "OrchestrationMessage",
    "OrchestrationTaskSpec",
    "TaskCompletedDetails",
    "TaskCompletedMessage",
    "TaskErrorDetails",
    "TaskErrorMessage",
    "validate_orchestration_message",
]

from typing import Annotated, Any, Literal, TypeAlias

from pydantic import Field, TypeAdapter

from website_backend.messages.common import (
    GraphId,
    MessageModel,
    NonEmptyStr,
    OpaqueDetails,
    TaskId,
    TaskType,
    Version,
)


class OrchestrationTaskSpec(MessageModel):
    task_id: TaskId
    requirements: list[TaskId] = Field(default_factory=list)
    task_type: TaskType
    details: OpaqueDetails


class AddTasksDetails(MessageModel):
    tasks: list[OrchestrationTaskSpec]


class TaskCompletedDetails(MessageModel):
    task_id: TaskId


class TaskErrorDetails(MessageModel):
    task_id: TaskId
    error_msg: NonEmptyStr


class AddTasksMessage(MessageModel):
    version: Version
    graph_id: GraphId
    message_type: Literal["ADD_TASKS"]
    details: AddTasksDetails


class TaskCompletedMessage(MessageModel):
    version: Version
    graph_id: GraphId
    message_type: Literal["TASK_COMPLETED"]
    details: TaskCompletedDetails


class TaskErrorMessage(MessageModel):
    version: Version
    graph_id: GraphId
    message_type: Literal["TASK_ERROR"]
    details: TaskErrorDetails


OrchestrationMessage: TypeAlias = Annotated[
    AddTasksMessage | TaskCompletedMessage | TaskErrorMessage,
    Field(discriminator="message_type"),
]

_ORCHESTRATION_MESSAGE_ADAPTER = TypeAdapter(OrchestrationMessage)


def validate_orchestration_message(
    data: Any,
) -> AddTasksMessage | TaskCompletedMessage | TaskErrorMessage:
    return _ORCHESTRATION_MESSAGE_ADAPTER.validate_python(data)
