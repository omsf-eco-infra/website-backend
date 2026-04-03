from __future__ import annotations

__all__ = ["TaskMessage", "validate_task_message"]

from typing import Any

from pydantic import Field

from website_backend.messages.common import (
    GraphId,
    MessageModel,
    OpaqueDetails,
    TaskId,
    TaskType,
    Version,
)


class TaskMessage(MessageModel):
    version: Version
    task_type: TaskType
    task_id: TaskId
    attempt: int = Field(gt=0)
    graph_id: GraphId
    task_details: OpaqueDetails


def validate_task_message(data: Any) -> TaskMessage:
    return TaskMessage.model_validate(data)
