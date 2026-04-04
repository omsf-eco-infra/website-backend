from __future__ import annotations

from contextlib import contextmanager

import sqlalchemy as sqla

from website_backend.messages.orchestration import validate_orchestration_message
from website_backend.orchestration.orchestrator import LocalOrchestrator, Orchestrator
from website_backend.orchestration.taskdb import TaskStatusDB
from website_backend.queues import QueueDelivery


class StubOrchestrationQueue:
    def __init__(self, messages):
        self.messages = list(messages)
        self.completed_deliveries = []

    def get_message(self):
        if not self.messages:
            return None
        message = self.messages.pop(0)
        return QueueDelivery(
            message=message,
            ack_token=f"ack-{len(self.completed_deliveries)}-{len(self.messages)}",
            message_id=None,
            attributes={},
            message_attributes={},
            raw_body=None,
        )

    def mark_message_completed(self, delivery):
        self.completed_deliveries.append(delivery)


class StubTaskQueue:
    def __init__(self):
        self.messages = []

    def add_message(self, message):
        self.messages.append(message)


def _add_tasks_message(graph_id, tasks):
    return validate_orchestration_message(
        {
            "version": "2026-05",
            "graph_id": graph_id,
            "message_type": "ADD_TASKS",
            "details": {"tasks": tasks},
        }
    )


def _task_completed_message(graph_id, task_id):
    return validate_orchestration_message(
        {
            "version": "2026-05",
            "graph_id": graph_id,
            "message_type": "TASK_COMPLETED",
            "details": {"task_id": task_id},
        }
    )


def _task_error_message(graph_id, task_id, error_msg="boom"):
    return validate_orchestration_message(
        {
            "version": "2026-05",
            "graph_id": graph_id,
            "message_type": "TASK_ERROR",
            "details": {"task_id": task_id, "error_msg": error_msg},
        }
    )


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
    def test_dispatches_ready_tasks_using_graph_id(self) -> None:
        orchestration_queue = StubOrchestrationQueue(
            [
                _add_tasks_message(
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
        task_queue = StubTaskQueue()

        orchestrator = InMemoryOrchestrator(orchestration_queue, task_queue)

        assert orchestrator.process() is True
        assert orchestrator.process() is None
        assert len(task_queue.messages) == 1
        assert set(orchestrator.engines) == {"run-123"}
        assert len(orchestration_queue.completed_deliveries) == 1

        task_message = task_queue.messages[0]
        assert task_message.version == "2026-05"
        assert task_message.graph_id == "run-123"
        assert task_message.task_id == "task-1"
        assert task_message.task_type == "openfold_predict"
        assert task_message.attempt == 1
        assert task_message.task_details == {"protein": "AAA"}

    def test_only_dispatches_newly_unblocked_tasks(self) -> None:
        orchestration_queue = StubOrchestrationQueue(
            [
                _add_tasks_message(
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
                _task_completed_message("run-123", "task-1"),
            ]
        )
        task_queue = StubTaskQueue()

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
        orchestration_queue = StubOrchestrationQueue(
            [
                _add_tasks_message(
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
                _add_tasks_message(
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
                _task_completed_message("graph-a", "task-1"),
            ]
        )
        task_queue = StubTaskQueue()

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
        orchestration_queue = StubOrchestrationQueue(
            [
                _add_tasks_message(
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
                _task_error_message("run-123", "task-1"),
            ]
        )
        task_queue = StubTaskQueue()

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


class TestLocalOrchestrator:
    def test_uses_absolute_graph_id_as_sqlite_filename(self, tmp_path) -> None:
        graph_id = tmp_path / "taskdb.sqlite"
        orchestration_queue = StubOrchestrationQueue(
            [
                _add_tasks_message(
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
                _task_completed_message(str(graph_id), "task-1"),
            ]
        )
        task_queue = StubTaskQueue()

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
