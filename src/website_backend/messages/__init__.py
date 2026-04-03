"""Reusable cross-component message contracts.

Ownership:
- InputsMessage: website request into the reusable web interface.
- OutputsMessage: reusable web interface response back to the website.
- OrchestrationMessage: producer-to-orchestrator queue contract.
- TaskMessage: orchestrator-to-compute dispatch contract.
"""

from __future__ import annotations

__all__ = [
    "AddTasksDetails",
    "AddTasksMessage",
    "GraphId",
    "InputsMessage",
    "MessageModel",
    "NonEmptyStr",
    "OpaqueDetails",
    "OrchestrationMessage",
    "OrchestrationTaskSpec",
    "OutputsMessage",
    "RunId",
    "TaskCompletedDetails",
    "TaskCompletedMessage",
    "TaskErrorDetails",
    "TaskErrorMessage",
    "TaskId",
    "TaskMessage",
    "TaskType",
    "UrlMap",
    "Version",
    "WorkflowName",
    "dump_message",
    "dump_message_json",
    "validate_inputs_message",
    "validate_orchestration_message",
    "validate_outputs_message",
    "validate_task_message",
]

from website_backend.messages.common import (
    GraphId,
    MessageModel,
    NonEmptyStr,
    OpaqueDetails,
    RunId,
    TaskId,
    TaskType,
    UrlMap,
    Version,
    WorkflowName,
    dump_message,
    dump_message_json,
)
from website_backend.messages.inputs import InputsMessage, validate_inputs_message
from website_backend.messages.orchestration import (
    AddTasksDetails,
    AddTasksMessage,
    OrchestrationMessage,
    OrchestrationTaskSpec,
    TaskCompletedDetails,
    TaskCompletedMessage,
    TaskErrorDetails,
    TaskErrorMessage,
    validate_orchestration_message,
)
from website_backend.messages.outputs import OutputsMessage, validate_outputs_message
from website_backend.messages.task import TaskMessage, validate_task_message
