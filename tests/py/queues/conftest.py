from __future__ import annotations

import pytest

from website_backend.messages import validate_inputs_message
from website_backend.messages import validate_orchestration_message
from website_backend.messages import validate_task_message


@pytest.fixture
def task_message():
    return validate_task_message(
        {
            "version": "2026-05",
            "task_type": "prepare_inputs",
            "task_id": "task-1",
            "attempt": 1,
            "graph_id": "run-123",
            "task_details": {"step": 1},
        }
    )


@pytest.fixture
def orchestration_message():
    return validate_orchestration_message(
        {
            "version": "2026-05",
            "graph_id": "run-123",
            "message_type": "ADD_TASKS",
            "details": {
                "tasks": [
                    {
                        "task_id": "task-1",
                        "requirements": [],
                        "task_type": "prepare_inputs",
                        "details": {"step": 1},
                    }
                ]
            },
        }
    )


@pytest.fixture
def inputs_message():
    return validate_inputs_message(
        {
            "version": "2026-05",
            "workflow_name": "example-workflow",
            "run_id": "run-123",
            "details": {},
        }
    )
