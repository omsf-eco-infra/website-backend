from __future__ import annotations

__all__ = ["TaskMessage"]

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from website_backend.messages.orchestration import NonEmptyStr


class TaskMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: NonEmptyStr
    task_type: NonEmptyStr
    task_id: NonEmptyStr
    attempt: int = Field(gt=0)
    graph_id: NonEmptyStr
    task_details: dict[str, Any]
