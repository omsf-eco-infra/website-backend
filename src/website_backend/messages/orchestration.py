from __future__ import annotations

__all__ = [
    "AddTasksDetails",
    "AddTasksMessage",
    "NonEmptyStr",
    "OrchestrationMessage",
    "OrchestrationTaskSpec",
    "TaskCompletedDetails",
    "TaskCompletedMessage",
    "TaskErrorDetails",
    "TaskErrorMessage",
    "validate_orchestration_message",
]

from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrchestrationTaskSpec(StrictModel):
    task_id: NonEmptyStr
    requirements: list[NonEmptyStr] = Field(default_factory=list)
    task_type: NonEmptyStr
    details: dict[str, Any]


class AddTasksDetails(StrictModel):
    tasks: list[OrchestrationTaskSpec]


class TaskCompletedDetails(StrictModel):
    task_id: NonEmptyStr


class TaskErrorDetails(StrictModel):
    task_id: NonEmptyStr
    error_msg: NonEmptyStr


class AddTasksMessage(StrictModel):
    version: NonEmptyStr
    graph_id: NonEmptyStr
    message_type: Literal["ADD_TASKS"]
    details: AddTasksDetails


class TaskCompletedMessage(StrictModel):
    version: NonEmptyStr
    graph_id: NonEmptyStr
    message_type: Literal["TASK_COMPLETED"]
    details: TaskCompletedDetails


class TaskErrorMessage(StrictModel):
    version: NonEmptyStr
    graph_id: NonEmptyStr
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
