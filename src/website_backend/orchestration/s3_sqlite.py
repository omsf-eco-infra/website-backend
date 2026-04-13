from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterator

import boto3
from botocore.exceptions import ClientError

from website_backend.messages.common import GraphId
from website_backend.messages.orchestration import OrchestrationMessage
from website_backend.messages.task import TaskMessage
from website_backend.queues import InputQueue, OutputQueue

from .orchestrator import Orchestrator
from .taskdb import TaskStatusDB

_logger = logging.getLogger(__name__)


def _is_not_found_error(error: ClientError) -> bool:
    code = error.response.get("Error", {}).get("Code", "")
    return code in {"404", "NoSuchKey", "NotFound"}


def _is_precondition_failed_error(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code", "") == "PreconditionFailed"


class S3SQLiteOrchestrator(Orchestrator):
    def __init__(
        self,
        orchestration_queue: InputQueue[OrchestrationMessage],
        task_queue: OutputQueue[TaskMessage],
        *,
        bucket: str,
        scratch_dir: str | Path,
        client: Any | None = None,
    ) -> None:
        super().__init__(orchestration_queue, task_queue)
        self.bucket = bucket
        self.scratch_dir = Path(scratch_dir)
        self.client = client or boto3.client("s3")

    @contextmanager
    def taskdb(self, graph_id: GraphId) -> Iterator[TaskStatusDB]:
        if graph_id.startswith("s3://"):
            raise ValueError(
                "S3SQLiteOrchestrator graph_id must be an S3 object key, not an s3:// URI"
            )

        self.scratch_dir.mkdir(parents=True, exist_ok=True)

        with TemporaryDirectory(dir=self.scratch_dir) as temp_dir:
            taskdb_file = Path(temp_dir) / "taskdb.sqlite"
            etag = self._download_snapshot(graph_id, taskdb_file)
            _logger.debug("Using s3://%s/%s as task status DB", self.bucket, graph_id)
            taskdb = TaskStatusDB.from_filename(taskdb_file)
            try:
                yield taskdb
            except Exception:
                taskdb.engine.dispose()
                raise
            else:
                taskdb.engine.dispose()
                self._upload_snapshot(graph_id, taskdb_file, etag)
                _logger.debug("Done with s3://%s/%s", self.bucket, graph_id)

    def _download_snapshot(self, graph_id: GraphId, taskdb_file: Path) -> str | None:
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=graph_id)
        except ClientError as error:
            if _is_not_found_error(error):
                _logger.debug(
                    "No existing task status DB at s3://%s/%s", self.bucket, graph_id
                )
                return None
            raise

        self.client.download_file(self.bucket, graph_id, str(taskdb_file))
        return response["ETag"]

    def _upload_snapshot(
        self, graph_id: GraphId, taskdb_file: Path, etag: str | None
    ) -> None:
        request: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": graph_id,
            "Body": taskdb_file.read_bytes(),
        }
        if etag is None:
            request["IfNoneMatch"] = "*"
        else:
            request["IfMatch"] = etag

        try:
            self.client.put_object(**request)
        except ClientError as error:
            if _is_precondition_failed_error(error):
                _logger.warning(
                    "Task status DB write conflict for s3://%s/%s",
                    self.bucket,
                    graph_id,
                )
            raise
