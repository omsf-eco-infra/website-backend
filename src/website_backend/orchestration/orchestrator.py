from contextlib import contextmanager
from datetime import datetime

from . import orchestrationmessages as msgs
from .taskmessage import TaskMessage

from exapaths.taskdb import TaskStatusDB

import logging

_logger = logging.getLogger(__name__)


class Orchestrator:
    DISPATCH = {
        "COMPLETED": msgs.TaskCompleted,
        "INCOMPLETE": msgs.TaskIncomplete,
        "ERRORED": msgs.TaskErrored,
        "ADDTASKS": msgs.AddTasks,
        "ACKNOWLEDGE": msgs.Acknowledge,
        # "ACQUIRELOCKS": msgs.AcquireLocks,
        # "RELEASELOCKS": msgs.ReleaseLocks,
        # "ACQUIRELOCKANDCREATETASK": msgs.AcquireLockAndCreateTask,
    }

    def __init__(self, orchestration_queue, task_queue):
        self.orchestration_queue = orchestration_queue
        self.task_queue = task_queue

    @contextmanager
    def taskdb(self, metadata):
        raise NotImplementedError()

    def process(self):
        msg, metadata = self.orchestration_queue.get_message()
        _logger.debug(f"Received message: {msg}")
        _logger.debug(f"Metadata: {metadata}")
        tasks = []
        if msg is None:
            return None

        with self.taskdb(metadata) as taskdb:
            msg.process(taskdb)
            # tell taskdb to check out all tasks, then we submit them to the
            # queue
            while task_id := taskdb.check_out_task():
                _logger.debug(f"Checked out task {task_id}")
                ...  # get the rest of the info to make the task message
                task_type = taskdb.get_task_type(task_id)
                resources = []  # TODO: we should be able to extract this
                tasks.append(
                    TaskMessage(
                        task_type=task_type, task_id=task_id, task_resources=resources
                    )
                )

        for task in tasks:
            _logger.debug(f"Adding to task queue: {task}")
            self.task_queue.add_message(task, metadata)

        return True

    def __call__(self):
        # on AWS, we might add time limits here for extra safety
        # could also consider a local daemon version with a while True
        while self.process():
            pass


class LocalOrchestrator(Orchestrator):
    @contextmanager
    def taskdb(self, metadata):
        taskdb_file = metadata["taskdb"]
        _logger.debug(f"Using {taskdb_file} as task status DB")
        taskdb = TaskStatusDB.from_filename(taskdb_file)
        yield taskdb
        _logger.debug(f"Done with {taskdb_file}")
