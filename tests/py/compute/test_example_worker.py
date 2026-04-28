from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from website_backend.messages import CURRENT_CONTRACT_VERSION

ROOT = Path(__file__).resolve().parents[3]
WORKER_FILE = (
    ROOT / "examples" / "containers" / "website-backend-example-worker" / "worker.py"
)


def _load_worker_module():
    spec = importlib.util.spec_from_file_location(
        "website_backend_example_worker",
        WORKER_FILE,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load example worker from {WORKER_FILE}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _task_payload(
    *,
    graph_id: str = "run-123",
    task_id: str = "task-1",
) -> dict[str, Any]:
    return {
        "attempt": 1,
        "graph_id": graph_id,
        "task_details": {"step": "hello"},
        "task_id": task_id,
        "task_type": "example_hello_world",
        "version": CURRENT_CONTRACT_VERSION,
    }


def _worker_env(*, queue_url: str) -> dict[str, str]:
    return {
        "GRAPH_ID": "run-123",
        "RESULTS_BUCKET": "results-bucket",
        "RESULTS_PREFIX": "tests/fargate-compute/run-123",
        "TASK_ATTEMPT": "1",
        "TASK_ID": "task-1",
        "TASK_QUEUE_URL": queue_url,
        "TASK_TYPE": "example_hello_world",
        "WORKFLOW_NAME": "example-workflow",
    }


def _create_fifo_queue(sqs: Any) -> str:
    return sqs.create_queue(
        QueueName="example.fifo",
        Attributes={
            "ContentBasedDeduplication": "true",
            "FifoQueue": "true",
            "VisibilityTimeout": "0",
        },
    )["QueueUrl"]


def _send_task_message(sqs: Any, *, queue_url: str, payload: dict[str, Any]) -> None:
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(payload),
        MessageGroupId=payload["graph_id"],
    )


def test_example_worker_config_from_env_parses_required_env() -> None:
    worker_module = _load_worker_module()

    config = worker_module.ExampleWorkerConfig.from_env(
        _worker_env(queue_url="https://sqs.us-east-1.amazonaws.com/123/example")
    )

    assert config.workflow_name == "example-workflow"
    assert config.task_queue_url.endswith("/example")
    assert config.task_attempt == 1
    assert config.results_prefix == "tests/fargate-compute/run-123"


@mock_aws
def test_run_example_worker_writes_result_and_deletes_message() -> None:
    worker_module = _load_worker_module()
    sqs = boto3.client("sqs", region_name="us-east-1")
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="results-bucket")
    queue_url = _create_fifo_queue(sqs)
    payload = _task_payload()
    _send_task_message(sqs, queue_url=queue_url, payload=payload)

    result = worker_module.run_example_worker(
        env=_worker_env(queue_url=queue_url),
        sqs_client=sqs,
        s3_client=s3,
        timeout_seconds=1,
        poll_interval_seconds=0,
        wait_time_seconds=1,
        sleeper=lambda _: None,
        timer=lambda: 0,
    )

    assert result == {
        "bucket": "results-bucket",
        "key": "tests/fargate-compute/run-123/task-1.json",
        "task_message": payload,
    }

    response = s3.get_object(
        Bucket="results-bucket",
        Key="tests/fargate-compute/run-123/task-1.json",
    )
    written_body = json.loads(response["Body"].read().decode("utf-8"))
    assert written_body["workflow_name"] == "example-workflow"
    assert written_body["env"] == {
        "graph_id": "run-123",
        "task_attempt": 1,
        "task_id": "task-1",
        "task_type": "example_hello_world",
    }
    assert written_body["queue_body"] == payload

    empty_response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=0,
    )
    assert empty_response.get("Messages") is None


@mock_aws
def test_run_example_worker_rejects_mismatched_queue_body_without_ack() -> None:
    worker_module = _load_worker_module()
    sqs = boto3.client("sqs", region_name="us-east-1")
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="results-bucket")
    queue_url = _create_fifo_queue(sqs)
    _send_task_message(
        sqs,
        queue_url=queue_url,
        payload=_task_payload(graph_id="wrong-run"),
    )

    with pytest.raises(RuntimeError, match="graph_id did not match GRAPH_ID"):
        worker_module.run_example_worker(
            env=_worker_env(queue_url=queue_url),
            sqs_client=sqs,
            s3_client=s3,
            timeout_seconds=1,
            poll_interval_seconds=0,
            wait_time_seconds=1,
            sleeper=lambda _: None,
            timer=lambda: 0,
        )

    with pytest.raises(ClientError):
        s3.get_object(
            Bucket="results-bucket",
            Key="tests/fargate-compute/run-123/task-1.json",
        )

    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=0,
    )
    assert response["Messages"][0]["Body"] == json.dumps(
        _task_payload(graph_id="wrong-run")
    )
