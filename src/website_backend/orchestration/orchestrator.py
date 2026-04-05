from __future__ import annotations

import logging
from abc import abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from website_backend.messages.common import GraphId
from website_backend.messages.common import CURRENT_CONTRACT_VERSION
from website_backend.messages.common import validate_contract_version
from website_backend.messages.orchestration import OrchestrationMessage
from website_backend.messages.task import TaskMessage
from website_backend.queues import InputQueue, OutputQueue

from .taskdb import TaskStatusDB

_logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        orchestration_queue: InputQueue[OrchestrationMessage],
        task_queue: OutputQueue[TaskMessage],
    ) -> None:
        self.orchestration_queue = orchestration_queue
        self.task_queue = task_queue

    @contextmanager
    @abstractmethod
    def taskdb(self, graph_id: GraphId) -> Iterator[TaskStatusDB]:
        raise NotImplementedError()

    def process(self) -> bool | None:
        delivery = self.orchestration_queue.get_message()
        _logger.debug("Received delivery: %s", delivery)
        if delivery is None:
            return None
        msg = delivery.message
        validate_contract_version(msg.version)

        tasks: list[TaskMessage] = []
        with self.taskdb(msg.graph_id) as taskdb:
            msg.process(taskdb)
            while task_id := taskdb.check_out_task():
                _logger.debug("Checked out task %s", task_id)
                tasks.append(
                    TaskMessage(
                        version=CURRENT_CONTRACT_VERSION,
                        task_type=taskdb.get_task_type(task_id),
                        task_id=task_id,
                        attempt=taskdb.get_task_attempt(task_id),
                        graph_id=msg.graph_id,
                        task_details=taskdb.get_task_details(task_id),
                    )
                )

        for task in tasks:
            _logger.debug("Adding to task queue: %s", task)
            self.task_queue.add_message(task)

        self.orchestration_queue.mark_message_completed(delivery)

        return True

    def __call__(self) -> None:
        while self.process():
            pass


class LocalOrchestrator(Orchestrator):
    @contextmanager
    def taskdb(self, graph_id: GraphId) -> Iterator[TaskStatusDB]:
        taskdb_file = Path(graph_id)
        if not taskdb_file.is_absolute():
            raise ValueError(
                "LocalOrchestrator graph_id must be an absolute SQLite filename"
            )
        _logger.debug("Using %s as task status DB", taskdb_file)
        taskdb = TaskStatusDB.from_filename(taskdb_file)
        yield taskdb
        _logger.debug("Done with %s", taskdb_file)
