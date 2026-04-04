from __future__ import annotations

import json

import pytest
import sqlalchemy as sqla
from pydantic import ValidationError

from website_backend.messages import dump_message, dump_message_json
from website_backend.messages.orchestration import (
    AddTasksMessage,
    OrchestrationMessage,
    TaskCompletedMessage,
    TaskErrorMessage,
    validate_orchestration_message,
)
from website_backend.orchestration.taskdb import TaskStatusDB


def _new_taskdb() -> TaskStatusDB:
    return TaskStatusDB(sqla.create_engine("sqlite://"))


class TestAddTasksMessage:
    def test_parses_defaults_and_round_trips(self) -> None:
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
        assert isinstance(message, OrchestrationMessage)
        assert message.details.tasks[0].requirements == []
        assert message.details.tasks[0].max_tries == 1
        assert message.details.tasks[0].details == nested_details
        assert dump_message(message) == {
            "version": "2026-05",
            "graph_id": "run-123",
            "message_type": "ADD_TASKS",
            "details": {
                "tasks": [
                    {
                        "task_id": "task-1",
                        "requirements": [],
                        "max_tries": 1,
                        "task_type": "openfold_predict",
                        "details": nested_details,
                    }
                ]
            },
        }
        assert json.loads(dump_message_json(message)) == dump_message(message)

    def test_accepts_explicit_max_tries(self) -> None:
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
                            "max_tries": 3,
                            "details": {"protein": "AAA"},
                        }
                    ]
                },
            }
        )

        assert isinstance(message, AddTasksMessage)
        assert message.details.tasks[0].max_tries == 3
        assert dump_message(message)["details"]["tasks"][0]["max_tries"] == 3

    def test_processes_tasks_into_taskdb(self) -> None:
        message = validate_orchestration_message(
            {
                "version": "2026-05",
                "graph_id": "run-123",
                "message_type": "ADD_TASKS",
                "details": {
                    "tasks": [
                        {
                            "task_id": "task-1",
                            "requirements": [],
                            "max_tries": 2,
                            "task_type": "prepare_inputs",
                            "details": {"step": 1},
                        },
                        {
                            "task_id": "task-2",
                            "requirements": ["task-1"],
                            "task_type": "run_model",
                            "details": {"step": 2},
                        },
                    ]
                },
            }
        )
        taskdb = _new_taskdb()

        message.process(taskdb)

        assert taskdb.check_out_task() == "task-1"
        assert taskdb.get_task_type("task-1") == "prepare_inputs"
        assert taskdb.get_task_details("task-1") == {"step": 1}
        assert taskdb.get_task_attempt("task-1") == 1
        assert taskdb.check_out_task() is None

        taskdb.mark_task_completed("task-1", success=True)

        assert taskdb.check_out_task() == "task-2"
        assert taskdb.get_task_type("task-2") == "run_model"
        assert taskdb.get_task_details("task-2") == {"step": 2}
        assert taskdb.get_task_attempt("task-2") == 1


class TestTaskCompletedMessage:
    def test_processes_into_taskdb(self) -> None:
        message = validate_orchestration_message(
            {
                "version": "2026-05",
                "graph_id": "run-123",
                "message_type": "TASK_COMPLETED",
                "details": {"task_id": "task-2"},
            }
        )
        taskdb = _new_taskdb()
        taskdb.add_task(
            taskid="task-2",
            task_type="prepare_inputs",
            task_details={"step": 1},
            requirements=[],
            max_tries=1,
        )
        taskdb.add_task(
            taskid="task-3",
            task_type="run_model",
            task_details={"step": 2},
            requirements=["task-2"],
            max_tries=1,
        )

        assert isinstance(message, TaskCompletedMessage)
        assert isinstance(message, OrchestrationMessage)
        assert taskdb.check_out_task() == "task-2"
        assert taskdb.check_out_task() is None

        message.process(taskdb)

        assert taskdb.check_out_task() == "task-3"
        assert taskdb.get_task_attempt("task-3") == 1


class TestTaskErrorMessage:
    def test_processes_into_taskdb(self) -> None:
        message = validate_orchestration_message(
            {
                "version": "2026-05",
                "graph_id": "run-123",
                "message_type": "TASK_ERROR",
                "details": {"task_id": "task-3", "error_msg": "task failed"},
            }
        )
        taskdb = _new_taskdb()
        taskdb.add_task(
            taskid="task-3",
            task_type="run_model",
            task_details={"step": 1},
            requirements=[],
            max_tries=2,
        )

        assert isinstance(message, TaskErrorMessage)
        assert isinstance(message, OrchestrationMessage)
        assert taskdb.check_out_task() == "task-3"

        message.process(taskdb)

        assert taskdb.check_out_task() == "task-3"
        assert taskdb.get_task_attempt("task-3") == 2


class TestOrchestrationMessage:
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
    def test_parses_other_message_types(
        self, payload: dict[str, object], expected_type: type[object]
    ) -> None:
        message = validate_orchestration_message(payload)

        assert isinstance(message, expected_type)
        assert isinstance(message, OrchestrationMessage)

    def test_rejects_invalid_message_type(self) -> None:
        with pytest.raises(ValidationError):
            validate_orchestration_message(
                {
                    "version": "2026-05",
                    "graph_id": "run-123",
                    "message_type": "NOT_A_REAL_TYPE",
                    "details": {},
                }
            )

    def test_rejects_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            validate_orchestration_message(
                {
                    "version": "2026-05",
                    "graph_id": "run-123",
                    "message_type": "TASK_COMPLETED",
                    "details": {},
                }
            )

    def test_rejects_extra_top_level_fields(self) -> None:
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

    def test_rejects_separate_run_id_field(self) -> None:
        with pytest.raises(ValidationError):
            validate_orchestration_message(
                {
                    "version": "2026-05",
                    "graph_id": "run-123",
                    "run_id": "run-123",
                    "message_type": "TASK_COMPLETED",
                    "details": {"task_id": "task-2"},
                }
            )
