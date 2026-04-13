from __future__ import annotations

import pytest
import sqlalchemy as sqla

from website_backend.orchestration.taskdb import TaskStatusDB


@pytest.fixture
def taskdb_with_available_and_blocked_tasks() -> TaskStatusDB:
    taskdb = TaskStatusDB(sqla.create_engine("sqlite://"))
    taskdb.add_task(
        taskid="task-1",
        task_type="openfold_predict",
        task_details={"inputs": {"ligand": "CCO"}},
        requirements=[],
        max_tries=2,
    )
    taskdb.add_task(
        taskid="task-2",
        task_type="run_model",
        task_details={"step": 2},
        requirements=["task-1"],
        max_tries=1,
    )
    return taskdb


class TestTaskStatusDB:
    @pytest.mark.parametrize(
        ("task_id", "expected_task_type"),
        [
            ("task-1", "openfold_predict"),
            ("task-2", "run_model"),
        ],
    )
    def test_get_task_type(
        self,
        taskdb_with_available_and_blocked_tasks: TaskStatusDB,
        task_id: str,
        expected_task_type: str,
    ) -> None:
        assert (
            taskdb_with_available_and_blocked_tasks.get_task_type(task_id)
            == expected_task_type
        )

    @pytest.mark.parametrize(
        ("task_id", "expected_task_details"),
        [
            ("task-1", {"inputs": {"ligand": "CCO"}}),
            ("task-2", {"step": 2}),
        ],
    )
    def test_get_task_details(
        self,
        taskdb_with_available_and_blocked_tasks: TaskStatusDB,
        task_id: str,
        expected_task_details: dict[str, object],
    ) -> None:
        assert (
            taskdb_with_available_and_blocked_tasks.get_task_details(task_id)
            == expected_task_details
        )

    def test_persists_task_metadata_and_attempts_across_file_reopen(
        self, tmp_path
    ) -> None:
        db_path = tmp_path / "taskdb.sqlite"
        details = {"inputs": {"ligand": "CCO"}}

        taskdb = TaskStatusDB.from_filename(db_path)
        taskdb.add_task(
            taskid="task-1",
            task_type="openfold_predict",
            task_details=details,
            requirements=[],
            max_tries=2,
        )

        assert taskdb.check_out_task() == "task-1"
        assert taskdb.get_task_attempt("task-1") == 1

        reopened = TaskStatusDB.from_filename(db_path)
        assert reopened.get_task_type("task-1") == "openfold_predict"
        assert reopened.get_task_details("task-1") == details
        assert reopened.get_task_attempt("task-1") == 1
