from __future__ import annotations

from contextlib import contextmanager

import pytest
import sqlalchemy as sqla

from website_backend.messages import CURRENT_CONTRACT_VERSION
from website_backend.orchestration.orchestrator import LocalOrchestrator, Orchestrator
from website_backend.orchestration.taskdb import TaskStatusDB


class InMemoryOrchestrator(Orchestrator):
    def __init__(self, orchestration_queue, task_queue):
        super().__init__(orchestration_queue, task_queue)
        self.engines = {}

    @contextmanager
    def taskdb(self, graph_id):
        if graph_id not in self.engines:
            self.engines[graph_id] = sqla.create_engine("sqlite://")
        yield TaskStatusDB(self.engines[graph_id])


class TestOrchestrator:
    @pytest.fixture(autouse=True)
    def _support(self, orchestration_test_support) -> None:
        self.support = orchestration_test_support

    def test_dispatches_ready_tasks_using_graph_id(self) -> None:
        orchestration_queue = self.support.orchestration_queue(
            [
                self.support.add_tasks_message(
                    "run-123",
                    [
                        {
                            "task_id": "task-1",
                            "requirements": [],
                            "max_tries": 2,
                            "task_type": "openfold_predict",
                            "details": {"protein": "AAA"},
                        }
                    ],
                )
            ]
        )
        task_queue = self.support.task_queue()

        orchestrator = InMemoryOrchestrator(orchestration_queue, task_queue)

        assert orchestrator.process() is True
        assert orchestrator.process() is None
        assert len(task_queue.messages) == 1
        assert set(orchestrator.engines) == {"run-123"}
        assert len(orchestration_queue.completed_deliveries) == 1

        task_message = task_queue.messages[0]
        assert task_message.version == CURRENT_CONTRACT_VERSION
        assert task_message.graph_id == "run-123"
        assert task_message.task_id == "task-1"
        assert task_message.task_type == "openfold_predict"
        assert task_message.attempt == 1
        assert task_message.task_details == {"protein": "AAA"}

    def test_rejects_message_with_unsupported_contract_version(self) -> None:
        orchestration_queue = self.support.orchestration_queue(
            [
                self.support.add_tasks_message(
                    "run-123",
                    [
                        {
                            "task_id": "task-1",
                            "requirements": [],
                            "task_type": "prepare_inputs",
                            "details": {"step": 1},
                        }
                    ],
                    version="1776.07",
                )
            ]
        )
        task_queue = self.support.task_queue()

        orchestrator = InMemoryOrchestrator(orchestration_queue, task_queue)

        with pytest.raises(ValueError, match="current contract version"):
            orchestrator.process()

        assert task_queue.messages == []
        assert orchestration_queue.completed_deliveries == []

    def test_only_dispatches_newly_unblocked_tasks(self) -> None:
        orchestration_queue = self.support.orchestration_queue(
            [
                self.support.add_tasks_message(
                    "run-123",
                    [
                        {
                            "task_id": "task-1",
                            "requirements": [],
                            "task_type": "prepare_inputs",
                            "details": {"step": 1},
                        },
                        {
                            "task_id": "task-2",
                            "requirements": ["task-1"],
                            "task_type": "run_model",
                            "details": {"step": 2},
                        },
                    ],
                ),
                self.support.task_completed_message("run-123", "task-1"),
            ]
        )
        task_queue = self.support.task_queue()

        orchestrator = InMemoryOrchestrator(orchestration_queue, task_queue)

        assert orchestrator.process() is True
        assert [message.task_id for message in task_queue.messages] == ["task-1"]

        assert orchestrator.process() is True
        assert [message.task_id for message in task_queue.messages] == [
            "task-1",
            "task-2",
        ]
        assert task_queue.messages[1].attempt == 1
        assert len(orchestration_queue.completed_deliveries) == 2

    def test_isolates_backing_taskdbs_for_different_graph_ids(self) -> None:
        orchestration_queue = self.support.orchestration_queue(
            [
                self.support.add_tasks_message(
                    "graph-a",
                    [
                        {
                            "task_id": "task-1",
                            "requirements": [],
                            "task_type": "prepare_inputs",
                            "details": {"graph": "a", "step": 1},
                        },
                        {
                            "task_id": "task-2",
                            "requirements": ["task-1"],
                            "task_type": "run_model",
                            "details": {"graph": "a", "step": 2},
                        },
                    ],
                ),
                self.support.add_tasks_message(
                    "graph-b",
                    [
                        {
                            "task_id": "task-1",
                            "requirements": [],
                            "task_type": "prepare_inputs",
                            "details": {"graph": "b", "step": 1},
                        },
                        {
                            "task_id": "task-2",
                            "requirements": ["task-1"],
                            "task_type": "run_model",
                            "details": {"graph": "b", "step": 2},
                        },
                    ],
                ),
                self.support.task_completed_message("graph-a", "task-1"),
            ]
        )
        task_queue = self.support.task_queue()

        orchestrator = InMemoryOrchestrator(orchestration_queue, task_queue)

        assert orchestrator.process() is True
        assert [
            (message.graph_id, message.task_id) for message in task_queue.messages
        ] == [("graph-a", "task-1")]

        assert orchestrator.process() is True
        assert [
            (message.graph_id, message.task_id) for message in task_queue.messages
        ] == [
            ("graph-a", "task-1"),
            ("graph-b", "task-1"),
        ]

        assert orchestrator.process() is True
        assert [
            (message.graph_id, message.task_id) for message in task_queue.messages
        ] == [
            ("graph-a", "task-1"),
            ("graph-b", "task-1"),
            ("graph-a", "task-2"),
        ]
        assert len(orchestration_queue.completed_deliveries) == 3

    def test_requeues_failed_task_with_incremented_attempt(self) -> None:
        orchestration_queue = self.support.orchestration_queue(
            [
                self.support.add_tasks_message(
                    "run-123",
                    [
                        {
                            "task_id": "task-1",
                            "requirements": [],
                            "max_tries": 2,
                            "task_type": "run_model",
                            "details": {"step": 1},
                        }
                    ],
                ),
                self.support.task_error_message("run-123", "task-1"),
            ]
        )
        task_queue = self.support.task_queue()

        orchestrator = InMemoryOrchestrator(orchestration_queue, task_queue)

        assert orchestrator.process() is True
        assert task_queue.messages[0].attempt == 1

        assert orchestrator.process() is True
        assert [message.task_id for message in task_queue.messages] == [
            "task-1",
            "task-1",
        ]
        assert task_queue.messages[1].attempt == 2
        assert len(orchestration_queue.completed_deliveries) == 2

    def test_duplicate_add_tasks_is_invalid_and_not_acked(self) -> None:
        orchestration_queue = self.support.orchestration_queue(
            [
                self.support.add_tasks_message(
                    "run-123",
                    [
                        {
                            "task_id": "task-1",
                            "requirements": [],
                            "task_type": "prepare_inputs",
                            "details": {"step": 1},
                        }
                    ],
                ),
                self.support.add_tasks_message(
                    "run-123",
                    [
                        {
                            "task_id": "task-1",
                            "requirements": [],
                            "task_type": "prepare_inputs",
                            "details": {"step": 1},
                        }
                    ],
                ),
            ]
        )
        task_queue = self.support.task_queue()

        orchestrator = InMemoryOrchestrator(orchestration_queue, task_queue)

        assert orchestrator.process() is True

        with pytest.raises(sqla.exc.IntegrityError):
            orchestrator.process()

        assert [message.task_id for message in task_queue.messages] == ["task-1"]
        assert len(orchestration_queue.completed_deliveries) == 1

    def test_duplicate_task_completed_is_acked_as_no_op(self) -> None:
        orchestration_queue = self.support.orchestration_queue(
            [
                self.support.add_tasks_message(
                    "run-123",
                    [
                        {
                            "task_id": "task-1",
                            "requirements": [],
                            "task_type": "prepare_inputs",
                            "details": {"step": 1},
                        }
                    ],
                ),
                self.support.task_completed_message("run-123", "task-1"),
                self.support.task_completed_message("run-123", "task-1"),
            ]
        )
        task_queue = self.support.task_queue()

        orchestrator = InMemoryOrchestrator(orchestration_queue, task_queue)

        assert orchestrator.process() is True
        assert orchestrator.process() is True
        assert orchestrator.process() is True

        assert [message.task_id for message in task_queue.messages] == ["task-1"]
        assert len(orchestration_queue.completed_deliveries) == 3

    def test_unknown_task_completed_is_acked_as_no_op(self) -> None:
        orchestration_queue = self.support.orchestration_queue(
            [
                self.support.task_completed_message("run-123", "missing-task"),
            ]
        )
        task_queue = self.support.task_queue()

        orchestrator = InMemoryOrchestrator(orchestration_queue, task_queue)

        assert orchestrator.process() is True

        assert task_queue.messages == []
        assert len(orchestration_queue.completed_deliveries) == 1

    @pytest.mark.xfail(
        raises=NameError,
        reason=(
            "Upstream exorcist.TaskStatusDB failure transitions raise NameError "
            "instead of treating zero-row TASK_ERROR updates as stale/unknown no-ops"
        ),
        strict=True,
    )
    def test_unknown_task_error_should_be_acked_as_no_op(self) -> None:
        orchestration_queue = self.support.orchestration_queue(
            [
                self.support.task_error_message("run-123", "missing-task"),
            ]
        )
        task_queue = self.support.task_queue()

        orchestrator = InMemoryOrchestrator(orchestration_queue, task_queue)

        assert orchestrator.process() is True

        assert task_queue.messages == []
        assert len(orchestration_queue.completed_deliveries) == 1

    def test_retry_exhaustion_does_not_redispatch_task(self) -> None:
        orchestration_queue = self.support.orchestration_queue(
            [
                self.support.add_tasks_message(
                    "run-123",
                    [
                        {
                            "task_id": "task-1",
                            "requirements": [],
                            "max_tries": 1,
                            "task_type": "run_model",
                            "details": {"step": 1},
                        }
                    ],
                ),
                self.support.task_error_message("run-123", "task-1"),
            ]
        )
        task_queue = self.support.task_queue()

        orchestrator = InMemoryOrchestrator(orchestration_queue, task_queue)

        assert orchestrator.process() is True
        assert orchestrator.process() is True

        assert [message.task_id for message in task_queue.messages] == ["task-1"]
        assert len(orchestration_queue.completed_deliveries) == 2

    @pytest.mark.xfail(
        raises=NameError,
        reason=(
            "Upstream exorcist.TaskStatusDB failure transitions raise NameError "
            "for stale duplicate TASK_ERROR notifications after retry exhaustion"
        ),
        strict=True,
    )
    def test_stale_duplicate_task_error_is_acked_after_retry_exhaustion(self) -> None:
        orchestration_queue = self.support.orchestration_queue(
            [
                self.support.add_tasks_message(
                    "run-123",
                    [
                        {
                            "task_id": "task-1",
                            "requirements": [],
                            "max_tries": 1,
                            "task_type": "run_model",
                            "details": {"step": 1},
                        }
                    ],
                ),
                self.support.task_error_message("run-123", "task-1"),
                self.support.task_error_message("run-123", "task-1"),
            ]
        )
        task_queue = self.support.task_queue()

        orchestrator = InMemoryOrchestrator(orchestration_queue, task_queue)

        assert orchestrator.process() is True
        assert orchestrator.process() is True
        assert orchestrator.process() is True

        assert [message.task_id for message in task_queue.messages] == ["task-1"]
        assert len(orchestration_queue.completed_deliveries) == 3


class TestLocalOrchestrator:
    @pytest.fixture(autouse=True)
    def _support(self, orchestration_test_support) -> None:
        self.support = orchestration_test_support

    def test_uses_absolute_graph_id_as_sqlite_filename(self, tmp_path) -> None:
        graph_id = tmp_path / "taskdb.sqlite"
        orchestration_queue = self.support.orchestration_queue(
            [
                self.support.add_tasks_message(
                    str(graph_id),
                    [
                        {
                            "task_id": "task-1",
                            "requirements": [],
                            "task_type": "prepare_inputs",
                            "details": {"step": 1},
                        },
                        {
                            "task_id": "task-2",
                            "requirements": ["task-1"],
                            "task_type": "run_model",
                            "details": {"step": 2},
                        },
                    ],
                ),
                self.support.task_completed_message(str(graph_id), "task-1"),
            ]
        )
        task_queue = self.support.task_queue()

        orchestrator = LocalOrchestrator(orchestration_queue, task_queue)

        assert orchestrator.process() is True
        assert graph_id.exists()
        assert [
            (message.graph_id, message.task_id) for message in task_queue.messages
        ] == [(str(graph_id), "task-1")]

        assert orchestrator.process() is True
        assert [
            (message.graph_id, message.task_id) for message in task_queue.messages
        ] == [
            (str(graph_id), "task-1"),
            (str(graph_id), "task-2"),
        ]
        assert len(orchestration_queue.completed_deliveries) == 2

        reopened = TaskStatusDB.from_filename(graph_id)
        assert reopened.get_task_type("task-2") == "run_model"
        assert reopened.get_task_attempt("task-2") == 1
