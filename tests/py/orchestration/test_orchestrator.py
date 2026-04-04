from __future__ import annotations

from contextlib import contextmanager

import sqlalchemy as sqla

from website_backend.messages.orchestration import validate_orchestration_message
from website_backend.orchestration.orchestrator import Orchestrator
from website_backend.orchestration.taskdb import TaskStatusDB


class StubOrchestrationQueue:
    def __init__(self, messages):
        self.messages = list(messages)

    def get_message(self):
        if not self.messages:
            return None, None
        return self.messages.pop(0)


class StubTaskQueue:
    def __init__(self):
        self.messages = []

    def add_message(self, message, metadata):
        self.messages.append((message, metadata))


class InMemoryOrchestrator(Orchestrator):
    def __init__(self, orchestration_queue, task_queue):
        super().__init__(orchestration_queue, task_queue)
        self.engine = sqla.create_engine("sqlite://")

    @contextmanager
    def taskdb(self, metadata):
        yield TaskStatusDB(self.engine)


class TestOrchestrator:
    def test_dispatches_ready_tasks_in_current_message_shape(self) -> None:
        metadata = {"source": "unit-test"}
        orchestration_queue = StubOrchestrationQueue(
            [
                (
                    validate_orchestration_message(
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
                                        "task_type": "openfold_predict",
                                        "details": {"protein": "AAA"},
                                    }
                                ]
                            },
                        }
                    ),
                    metadata,
                )
            ]
        )
        task_queue = StubTaskQueue()

        orchestrator = InMemoryOrchestrator(orchestration_queue, task_queue)

        assert orchestrator.process() is True
        assert orchestrator.process() is None
        assert len(task_queue.messages) == 1

        task_message, task_metadata = task_queue.messages[0]
        assert task_metadata == metadata
        assert task_message.version == "2026-05"
        assert task_message.graph_id == "run-123"
        assert task_message.task_id == "task-1"
        assert task_message.task_type == "openfold_predict"
        assert task_message.attempt == 1
        assert task_message.task_details == {"protein": "AAA"}

    def test_only_dispatches_newly_unblocked_tasks(self) -> None:
        metadata = {}
        orchestration_queue = StubOrchestrationQueue(
            [
                (
                    validate_orchestration_message(
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
                    ),
                    metadata,
                ),
                (
                    validate_orchestration_message(
                        {
                            "version": "2026-05",
                            "graph_id": "run-123",
                            "message_type": "TASK_COMPLETED",
                            "details": {"task_id": "task-1"},
                        }
                    ),
                    metadata,
                ),
            ]
        )
        task_queue = StubTaskQueue()

        orchestrator = InMemoryOrchestrator(orchestration_queue, task_queue)

        assert orchestrator.process() is True
        assert [message.task_id for message, _ in task_queue.messages] == ["task-1"]

        assert orchestrator.process() is True
        assert [message.task_id for message, _ in task_queue.messages] == [
            "task-1",
            "task-2",
        ]
        assert task_queue.messages[1][0].attempt == 1

    def test_requeues_failed_task_with_incremented_attempt(self) -> None:
        metadata = {}
        orchestration_queue = StubOrchestrationQueue(
            [
                (
                    validate_orchestration_message(
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
                                        "task_type": "run_model",
                                        "details": {"step": 1},
                                    }
                                ]
                            },
                        }
                    ),
                    metadata,
                ),
                (
                    validate_orchestration_message(
                        {
                            "version": "2026-05",
                            "graph_id": "run-123",
                            "message_type": "TASK_ERROR",
                            "details": {"task_id": "task-1", "error_msg": "boom"},
                        }
                    ),
                    metadata,
                ),
            ]
        )
        task_queue = StubTaskQueue()

        orchestrator = InMemoryOrchestrator(orchestration_queue, task_queue)

        assert orchestrator.process() is True
        assert task_queue.messages[0][0].attempt == 1

        assert orchestrator.process() is True
        assert [message.task_id for message, _ in task_queue.messages] == [
            "task-1",
            "task-1",
        ]
        assert task_queue.messages[1][0].attempt == 2
