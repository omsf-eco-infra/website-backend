from __future__ import annotations

__all__ = ["OutputsMessage", "validate_outputs_message"]

from typing import Any

from pydantic import Field

from website_backend.messages.common import (
    MessageModel,
    OpaqueDetails,
    RunId,
    UrlMap,
    Version,
    WorkflowName,
)


class OutputsMessage(MessageModel):
    version: Version
    workflow_name: WorkflowName
    run_id: RunId
    output_urls: UrlMap
    poll_after_seconds: int = Field(gt=0)
    details: OpaqueDetails


def validate_outputs_message(data: Any) -> OutputsMessage:
    return OutputsMessage.model_validate(data)
