from __future__ import annotations

import pytest
from pydantic import ValidationError

from website_backend.messages.orchestration import (
    AddTasksMessage,
    TaskCompletedMessage,
    TaskErrorMessage,
    validate_orchestration_message,
)


def test_add_tasks_message_parses_and_defaults_requirements() -> None:
    nested_details = {
        "queries": [
            {
                "protein_chains": ["AAA", "BBB"],
                "ligand_smiles": "CCO",
                "outputs": {"result_url": "https://example.com/result.pdb"},
            }
        ]
    }
    message = validate_orchestration_message(
        {
            "version": "2026-05",
            "graph_id": "run-123",
            "message_type": "ADD_TASKS",
            "details": {
                "tasks": [
                    {
                        "task_id": "task-1",
                        "task_type": "openfold_predict",
                        "details": nested_details,
                    }
                ]
            },
        }
    )

    assert isinstance(message, AddTasksMessage)
    assert message.details.tasks[0].requirements == []
    assert message.details.tasks[0].details == nested_details


@pytest.mark.parametrize(
    ("payload", "expected_type"),
    [
        (
            {
                "version": "2026-05",
                "graph_id": "run-123",
                "message_type": "TASK_COMPLETED",
                "details": {"task_id": "task-2"},
            },
            TaskCompletedMessage,
        ),
        (
            {
                "version": "2026-05",
                "graph_id": "run-123",
                "message_type": "TASK_ERROR",
                "details": {"task_id": "task-3", "error_msg": "task failed"},
            },
            TaskErrorMessage,
        ),
    ],
)
def test_orchestration_message_parses_other_message_types(
    payload: dict[str, object], expected_type: type[object]
) -> None:
    message = validate_orchestration_message(payload)

    assert isinstance(message, expected_type)


def test_orchestration_message_rejects_invalid_message_type() -> None:
    with pytest.raises(ValidationError):
        validate_orchestration_message(
            {
                "version": "2026-05",
                "graph_id": "run-123",
                "message_type": "NOT_A_REAL_TYPE",
                "details": {},
            }
        )


def test_orchestration_message_rejects_missing_required_fields() -> None:
    with pytest.raises(ValidationError):
        validate_orchestration_message(
            {
                "version": "2026-05",
                "graph_id": "run-123",
                "message_type": "TASK_COMPLETED",
                "details": {},
            }
        )


def test_orchestration_message_rejects_extra_top_level_fields() -> None:
    with pytest.raises(ValidationError):
        validate_orchestration_message(
            {
                "version": "2026-05",
                "graph_id": "run-123",
                "message_type": "TASK_ERROR",
                "details": {"task_id": "task-3", "error_msg": "task failed"},
                "unexpected": "value",
            }
        )
