from __future__ import annotations

__all__ = ["InputsMessage", "validate_inputs_message"]

from typing import Any

from website_backend.messages.common import (
    MessageModel,
    OpaqueDetails,
    RunId,
    Version,
    WorkflowName,
)


class InputsMessage(MessageModel):
    version: Version
    workflow_name: WorkflowName
    run_id: RunId
    details: OpaqueDetails


def validate_inputs_message(data: Any) -> InputsMessage:
    return InputsMessage.model_validate(data)
