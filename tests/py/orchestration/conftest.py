from __future__ import annotations

from pathlib import Path

import pytest

from website_backend.messages import CURRENT_CONTRACT_VERSION
from website_backend.messages.orchestration import validate_orchestration_message
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


class OrchestrationTestSupport:
    def orchestration_queue(self, messages) -> StubOrchestrationQueue:
        return StubOrchestrationQueue(messages)

    def task_queue(self) -> StubTaskQueue:
        return StubTaskQueue()

    def add_tasks_message(self, graph_id, tasks, *, version=CURRENT_CONTRACT_VERSION):
        return validate_orchestration_message(
            {
                "version": version,
                "graph_id": graph_id,
                "message_type": "ADD_TASKS",
                "details": {"tasks": tasks},
            }
        )

    def task_completed_message(
        self, graph_id, task_id, *, version=CURRENT_CONTRACT_VERSION
    ):
        return validate_orchestration_message(
            {
                "version": version,
                "graph_id": graph_id,
                "message_type": "TASK_COMPLETED",
                "details": {"task_id": task_id},
            }
        )

    def task_error_message(
        self,
        graph_id,
        task_id,
        error_msg="boom",
        *,
        version=CURRENT_CONTRACT_VERSION,
    ):
        return validate_orchestration_message(
            {
                "version": version,
                "graph_id": graph_id,
                "message_type": "TASK_ERROR",
                "details": {"task_id": task_id, "error_msg": error_msg},
            }
        )

    def create_taskdb_snapshot(self, path: Path) -> None:
        taskdb = TaskStatusDB.from_filename(path)
        taskdb.engine.dispose()


@pytest.fixture
def orchestration_test_support() -> OrchestrationTestSupport:
    return OrchestrationTestSupport()
