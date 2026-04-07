from __future__ import annotations

import boto3
from moto import mock_aws

from website_backend.orchestration.taskdb import TaskStatusDB
from website_backend.testing import inspect_taskdb_snapshot


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

    assert result == {"exists": False}


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
