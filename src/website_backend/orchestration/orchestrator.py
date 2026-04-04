import logging
from contextlib import contextmanager

from website_backend.messages.task import TaskMessage

from .taskdb import TaskStatusDB

_logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, orchestration_queue, task_queue):
        self.orchestration_queue = orchestration_queue
        self.task_queue = task_queue

    @contextmanager
    def taskdb(self, metadata):
        raise NotImplementedError()

    def process(self):
        msg, metadata = self.orchestration_queue.get_message()
        _logger.debug("Received message: %s", msg)
        _logger.debug("Metadata: %s", metadata)
        if msg is None:
            return None

        tasks = []
        with self.taskdb(metadata) as taskdb:
            msg.process(taskdb)
            while task_id := taskdb.check_out_task():
                _logger.debug("Checked out task %s", task_id)
                tasks.append(
                    TaskMessage(
                        version=msg.version,
                        task_type=taskdb.get_task_type(task_id),
                        task_id=task_id,
                        attempt=taskdb.get_task_attempt(task_id),
                        graph_id=msg.graph_id,
                        task_details=taskdb.get_task_details(task_id),
                    )
                )

        for task in tasks:
            _logger.debug("Adding to task queue: %s", task)
            self.task_queue.add_message(task, metadata)

        return True

    def __call__(self):
        while self.process():
            pass


class LocalOrchestrator(Orchestrator):
    @contextmanager
    def taskdb(self, metadata):
        taskdb_file = metadata["taskdb"]
        _logger.debug("Using %s as task status DB", taskdb_file)
        taskdb = TaskStatusDB.from_filename(taskdb_file)
        yield taskdb
        _logger.debug("Done with %s", taskdb_file)
