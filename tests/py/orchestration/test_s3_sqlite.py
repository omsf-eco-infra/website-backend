from __future__ import annotations

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from website_backend.orchestration.s3_sqlite import S3SQLiteOrchestrator
from website_backend.orchestration.taskdb import TaskStatusDB


class ConflictOnPutS3Client:
    def __init__(self, client, *, bucket: str, key: str):
        self.client = client
        self.bucket = bucket
        self.key = key
        self.conflict_injected = False

    def __getattr__(self, name):
        return getattr(self.client, name)

    def put_object(self, **kwargs):
        if (
            not self.conflict_injected
            and kwargs.get("Bucket") == self.bucket
            and kwargs.get("Key") == self.key
            and "IfMatch" in kwargs
        ):
            self.client.put_object(
                Bucket=self.bucket,
                Key=self.key,
                Body=b"conflicting-write",
            )
            self.conflict_injected = True
        return self.client.put_object(**kwargs)


class TestS3SQLiteOrchestrator:
    @pytest.fixture(autouse=True)
    def _support(self, orchestration_test_support) -> None:
        self.support = orchestration_test_support

    @mock_aws
    def test_uses_graph_id_as_s3_object_key_and_persists_snapshot(
        self, tmp_path
    ) -> None:
        graph_id = "runs/run-123/taskdb.sqlite"
        bucket = "example-bucket"
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=bucket)
        orchestration_queue = self.support.orchestration_queue(
            [
                self.support.add_tasks_message(
                    graph_id,
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
                self.support.task_completed_message(graph_id, "task-1"),
            ]
        )
        task_queue = self.support.task_queue()

        orchestrator = S3SQLiteOrchestrator(
            orchestration_queue,
            task_queue,
            bucket=bucket,
            scratch_dir=tmp_path,
            client=s3,
        )

        assert orchestrator.process() is True
        s3.head_object(Bucket=bucket, Key=graph_id)
        assert [
            (message.graph_id, message.task_id) for message in task_queue.messages
        ] == [(graph_id, "task-1")]

        assert orchestrator.process() is True
        assert [
            (message.graph_id, message.task_id) for message in task_queue.messages
        ] == [
            (graph_id, "task-1"),
            (graph_id, "task-2"),
        ]
        assert len(orchestration_queue.completed_deliveries) == 2

        reopened_path = tmp_path / "reopened.sqlite"
        s3.download_file(bucket, graph_id, str(reopened_path))
        reopened = TaskStatusDB.from_filename(reopened_path)
        assert reopened.get_task_type("task-2") == "run_model"
        assert reopened.get_task_details("task-2") == {"step": 2}
        assert reopened.get_task_attempt("task-2") == 1

    def test_rejects_s3_uri_graph_id(self, tmp_path) -> None:
        graph_id = "s3://example-bucket/runs/run-123/taskdb.sqlite"
        orchestration_queue = self.support.orchestration_queue(
            [
                self.support.add_tasks_message(
                    graph_id,
                    [
                        {
                            "task_id": "task-1",
                            "requirements": [],
                            "task_type": "prepare_inputs",
                            "details": {"step": 1},
                        }
                    ],
                )
            ]
        )
        task_queue = self.support.task_queue()
        orchestrator = S3SQLiteOrchestrator(
            orchestration_queue,
            task_queue,
            bucket="example-bucket",
            scratch_dir=tmp_path,
            client=object(),
        )

        with pytest.raises(ValueError, match="S3 object key"):
            orchestrator.process()

        assert task_queue.messages == []
        assert orchestration_queue.completed_deliveries == []

    @mock_aws
    def test_conflicting_snapshot_write_does_not_ack_or_dispatch(
        self, tmp_path
    ) -> None:
        graph_id = "runs/run-123/taskdb.sqlite"
        bucket = "example-bucket"
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=bucket)

        seed_path = tmp_path / "seed.sqlite"
        self.support.create_taskdb_snapshot(seed_path)
        s3.put_object(Bucket=bucket, Key=graph_id, Body=seed_path.read_bytes())

        orchestration_queue = self.support.orchestration_queue(
            [
                self.support.add_tasks_message(
                    graph_id,
                    [
                        {
                            "task_id": "task-1",
                            "requirements": [],
                            "task_type": "prepare_inputs",
                            "details": {"step": 1},
                        }
                    ],
                )
            ]
        )
        task_queue = self.support.task_queue()
        orchestrator = S3SQLiteOrchestrator(
            orchestration_queue,
            task_queue,
            bucket=bucket,
            scratch_dir=tmp_path,
            client=ConflictOnPutS3Client(s3, bucket=bucket, key=graph_id),
        )

        with pytest.raises(ClientError) as excinfo:
            orchestrator.process()

        assert excinfo.value.response["Error"]["Code"] == "PreconditionFailed"
        assert task_queue.messages == []
        assert orchestration_queue.completed_deliveries == []
