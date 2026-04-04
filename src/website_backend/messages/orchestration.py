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

from abc import ABC, abstractmethod
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
    max_tries: int = Field(default=1, gt=0)
    task_type: TaskType
    details: OpaqueDetails


class AddTasksDetails(MessageModel):
    tasks: list[OrchestrationTaskSpec]


class TaskCompletedDetails(MessageModel):
    task_id: TaskId


class TaskErrorDetails(MessageModel):
    task_id: TaskId
    error_msg: NonEmptyStr


class OrchestrationMessage(MessageModel, ABC):
    version: Version
    graph_id: GraphId

    @abstractmethod
    def process(self, taskdb) -> None:
        raise NotImplementedError


class AddTasksMessage(OrchestrationMessage):
    message_type: Literal["ADD_TASKS"]
    details: AddTasksDetails

    def process(self, taskdb) -> None:
        for task in self.details.tasks:
            taskdb.add_task(
                taskid=task.task_id,
                task_type=task.task_type,
                task_details=task.details,
                requirements=task.requirements,
                max_tries=task.max_tries,
            )


class TaskCompletedMessage(OrchestrationMessage):
    message_type: Literal["TASK_COMPLETED"]
    details: TaskCompletedDetails

    def process(self, taskdb) -> None:
        taskdb.mark_task_completed(self.details.task_id, success=True)


class TaskErrorMessage(OrchestrationMessage):
    message_type: Literal["TASK_ERROR"]
    details: TaskErrorDetails

    def process(self, taskdb) -> None:
        taskdb.mark_task_completed(self.details.task_id, success=False)


_ParsedOrchestrationMessage: TypeAlias = Annotated[
    AddTasksMessage | TaskCompletedMessage | TaskErrorMessage,
    Field(discriminator="message_type"),
]

_ORCHESTRATION_MESSAGE_ADAPTER = TypeAdapter(_ParsedOrchestrationMessage)


def validate_orchestration_message(data: Any) -> OrchestrationMessage:
    return _ORCHESTRATION_MESSAGE_ADAPTER.validate_python(data)
