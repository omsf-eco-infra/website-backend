from __future__ import annotations

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from website_backend.orchestration.taskdb import TaskStatusDB
from website_backend.testing import inspect_taskdb_snapshot


def _write_taskdb(path, *task_ids: str) -> None:
    taskdb = TaskStatusDB.from_filename(path)
    for task_id in task_ids:
        taskdb.add_task(
            taskid=task_id,
            task_type="example_task",
            task_details={"task_id": task_id},
            requirements=[],
            max_tries=1,
        )
    taskdb.engine.dispose()


@mock_aws
def test_inspect_taskdb_snapshot_returns_task_metadata(tmp_path) -> None:
    bucket = "example-bucket"
    key = "runs/run-123/taskdb.sqlite"

    db_path = tmp_path / "taskdb.sqlite"
    taskdb = TaskStatusDB.from_filename(db_path)
    taskdb.add_task(
        taskid="task-a",
        task_type="prepare_inputs",
        task_details={"stage": "a"},
        requirements=[],
        max_tries=2,
    )
    taskdb.add_task(
        taskid="task-c",
        task_type="collect_outputs",
        task_details={"stage": "c"},
        requirements=["task-a"],
        max_tries=1,
    )
    assert taskdb.check_out_task() == "task-a"
    taskdb.engine.dispose()

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=bucket)
    s3.put_object(Bucket=bucket, Key=key, Body=db_path.read_bytes())

    result = inspect_taskdb_snapshot.inspect_snapshot(
        bucket=bucket,
        key=key,
        timeout_seconds=1,
        poll_interval_seconds=0,
        client=s3,
    )

    assert result["exists"] is True
    assert result["content_length"] > 0
    assert result["task_count"] == 2
    assert result["task_ids"] == ["task-a", "task-c"]
    assert result["tasks_by_id"]["task-a"]["task_type"] == "prepare_inputs"
    assert result["tasks_by_id"]["task-a"]["task_details"] == {"stage": "a"}
    assert result["tasks_by_id"]["task-a"]["attempt"] == 1
    assert result["tasks_by_id"]["task-a"]["task_record"]["tries"] == 1
    assert isinstance(
        result["tasks_by_id"]["task-a"]["task_record"]["last_modified"], str
    )
    assert result["tasks_by_id"]["task-c"]["task_type"] == "collect_outputs"
    assert result["tasks_by_id"]["task-c"]["task_details"] == {"stage": "c"}
    assert result["tasks_by_id"]["task-c"]["attempt"] == 0
    assert isinstance(result["etag"], str)


@mock_aws
def test_inspect_taskdb_snapshot_returns_exists_false_for_missing_key() -> None:
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="example-bucket")

    result = inspect_taskdb_snapshot.inspect_snapshot(
        bucket="example-bucket",
        key="runs/missing.sqlite",
        timeout_seconds=0,
        poll_interval_seconds=0,
        client=s3,
    )

    assert result == {
        "exists": False,
        "etag": None,
        "content_length": None,
        "task_count": 0,
        "task_ids": [],
        "tasks_by_id": {},
    }


@mock_aws
def test_inspect_taskdb_snapshot_returns_current_state_when_etag_does_not_change(
    tmp_path,
) -> None:
    bucket = "example-bucket"
    key = "runs/run-123/taskdb.sqlite"

    db_path = tmp_path / "taskdb.sqlite"
    taskdb = TaskStatusDB.from_filename(db_path)
    taskdb.add_task(
        taskid="task-a",
        task_type="prepare_inputs",
        task_details={"stage": "a"},
        requirements=[],
        max_tries=1,
    )
    taskdb.engine.dispose()

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=bucket)
    response = s3.put_object(Bucket=bucket, Key=key, Body=db_path.read_bytes())

    result = inspect_taskdb_snapshot.inspect_snapshot(
        bucket=bucket,
        key=key,
        previous_etag=response["ETag"],
        timeout_seconds=0,
        poll_interval_seconds=0,
        client=s3,
    )

    assert result["exists"] is True
    assert result["etag"] == response["ETag"]
    assert result["task_ids"] == ["task-a"]


class AccessDeniedHeadClient:
    def head_object(self, *, Bucket, Key):  # noqa: N803
        del Bucket, Key
        raise ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}},
            "HeadObject",
        )


def test_inspect_taskdb_snapshot_reraises_unexpected_head_errors() -> None:
    with pytest.raises(ClientError) as excinfo:
        inspect_taskdb_snapshot.inspect_snapshot(
            bucket="example-bucket",
            key="runs/run-123/taskdb.sqlite",
            timeout_seconds=1,
            poll_interval_seconds=0,
            client=AccessDeniedHeadClient(),
        )

    assert excinfo.value.response["Error"]["Code"] == "AccessDenied"


@mock_aws
def test_inspect_taskdb_snapshot_waits_for_missing_key_to_appear(tmp_path) -> None:
    bucket = "example-bucket"
    key = "runs/run-123/taskdb.sqlite"

    db_path = tmp_path / "taskdb.sqlite"
    _write_taskdb(db_path, "task-a")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=bucket)

    def upload_snapshot(_seconds: int) -> None:
        s3.put_object(Bucket=bucket, Key=key, Body=db_path.read_bytes())

    result = inspect_taskdb_snapshot.inspect_snapshot(
        bucket=bucket,
        key=key,
        timeout_seconds=1,
        poll_interval_seconds=0,
        client=s3,
        sleeper=upload_snapshot,
    )

    assert result["exists"] is True
    assert result["task_ids"] == ["task-a"]


@mock_aws
def test_inspect_taskdb_snapshot_waits_for_etag_to_change(tmp_path) -> None:
    bucket = "example-bucket"
    key = "runs/run-123/taskdb.sqlite"

    initial_db_path = tmp_path / "initial.sqlite"
    updated_db_path = tmp_path / "updated.sqlite"
    _write_taskdb(initial_db_path, "task-a")
    _write_taskdb(updated_db_path, "task-a", "task-b")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=bucket)
    initial_response = s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=initial_db_path.read_bytes(),
    )

    def upload_updated_snapshot(_seconds: int) -> None:
        s3.put_object(Bucket=bucket, Key=key, Body=updated_db_path.read_bytes())

    result = inspect_taskdb_snapshot.inspect_snapshot(
        bucket=bucket,
        key=key,
        previous_etag=initial_response["ETag"],
        timeout_seconds=1,
        poll_interval_seconds=0,
        client=s3,
        sleeper=upload_updated_snapshot,
    )

    assert result["exists"] is True
    assert result["etag"] != initial_response["ETag"]
    assert result["task_ids"] == ["task-a", "task-b"]
