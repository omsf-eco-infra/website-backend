from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

import boto3

from website_backend.messages import TaskMessage
from website_backend.messages import validate_contract_version
from website_backend.messages import validate_task_message
from website_backend.runtime import required_env_from


@dataclass(frozen=True, slots=True)
class ExampleWorkerConfig:
    workflow_name: str
    task_queue_url: str
    graph_id: str
    task_id: str
    task_type: str
    task_attempt: int
    results_bucket: str
    results_prefix: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        """Load worker configuration from environment variables.

        Parameters
        ----------
        env
            Optional environment mapping. When omitted, `os.environ` is used.

        Returns
        -------
        ExampleWorkerConfig
            Parsed worker configuration.

        Raises
        ------
        RuntimeError
            If any required value is missing or `TASK_ATTEMPT` is invalid.
        """
        source = env if env is not None else os.environ

        raw_attempt = required_env_from(source, "TASK_ATTEMPT")
        try:
            task_attempt = int(raw_attempt)
        except ValueError as exc:
            raise RuntimeError("TASK_ATTEMPT must be a whole number.") from exc

        if task_attempt < 1:
            raise RuntimeError("TASK_ATTEMPT must be greater than or equal to 1.")

        return cls(
            workflow_name=required_env_from(source, "WORKFLOW_NAME"),
            task_queue_url=required_env_from(source, "TASK_QUEUE_URL"),
            graph_id=required_env_from(source, "GRAPH_ID"),
            task_id=required_env_from(source, "TASK_ID"),
            task_type=required_env_from(source, "TASK_TYPE"),
            task_attempt=task_attempt,
            results_bucket=required_env_from(source, "RESULTS_BUCKET"),
            results_prefix=required_env_from(source, "RESULTS_PREFIX").strip("/"),
        )


def poll_for_task_message(
    *,
    queue_url: str,
    client: Any | None = None,
    timeout_seconds: int = 180,
    poll_interval_seconds: int = 5,
    wait_time_seconds: int = 20,
    sleeper: Any = time.sleep,
    timer: Any = time.monotonic,
) -> dict[str, Any]:
    """Poll SQS until one task message is available.

    Parameters
    ----------
    queue_url
        URL of the SQS queue to poll.
    client
        Optional SQS-compatible client. When omitted, a boto3 SQS client is
        created.
    timeout_seconds
        Maximum total time to wait for a message.
    poll_interval_seconds
        Delay between empty receives.
    wait_time_seconds
        SQS long-poll duration per receive attempt.
    sleeper
        Sleep callable used between polling attempts.
    timer
        Monotonic timer callable used to compute the polling deadline.

    Returns
    -------
    dict[str, Any]
        Raw SQS message dictionary.

    Raises
    ------
    TimeoutError
        If no message is available before the timeout expires.
    """
    sqs_client = client or boto3.client("sqs")
    deadline = timer() + timeout_seconds

    while True:
        remaining_seconds = deadline - timer()
        if remaining_seconds <= 0:
            break

        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=min(wait_time_seconds, max(1, int(remaining_seconds))),
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
        )
        messages = response.get("Messages", [])
        if messages:
            return messages[0]

        if timer() >= deadline:
            break

        sleeper(poll_interval_seconds)

    raise TimeoutError(f"Timed out waiting for a task message on {queue_url}.")


def decode_and_validate_task_message(
    raw_message: Mapping[str, Any],
    *,
    config: ExampleWorkerConfig,
) -> tuple[TaskMessage, dict[str, Any]]:
    """Decode a queue body and verify it matches launcher-provided context.

    Parameters
    ----------
    raw_message
        Raw SQS message dictionary returned by `receive_message`.
    config
        Worker configuration loaded from environment variables.

    Returns
    -------
    tuple[TaskMessage, dict[str, Any]]
        Validated task message plus the decoded JSON body.

    Raises
    ------
    RuntimeError
        If the SQS body is missing, invalid, or does not match the launcher
        context.
    """
    raw_body = raw_message.get("Body")
    if not isinstance(raw_body, str) or not raw_body:
        raise RuntimeError("SQS message is missing Body.")

    try:
        parsed_body = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("SQS message Body is not valid JSON.") from exc

    task_message = validate_task_message(parsed_body)
    validate_contract_version(task_message.version)

    if task_message.graph_id != config.graph_id:
        raise RuntimeError("Queue task graph_id did not match GRAPH_ID.")
    if task_message.task_id != config.task_id:
        raise RuntimeError("Queue task task_id did not match TASK_ID.")
    if task_message.task_type != config.task_type:
        raise RuntimeError("Queue task task_type did not match TASK_TYPE.")
    if task_message.attempt != config.task_attempt:
        raise RuntimeError("Queue task attempt did not match TASK_ATTEMPT.")

    return task_message, parsed_body


def result_object_key(config: ExampleWorkerConfig) -> str:
    """Return the S3 key where this worker should write its result.

    Parameters
    ----------
    config
        Worker configuration containing the result prefix and task ID.

    Returns
    -------
    str
        S3 object key for the result JSON document.
    """
    if config.results_prefix:
        return f"{config.results_prefix}/{config.task_id}.json"
    return f"{config.task_id}.json"


def write_result_object(
    *,
    bucket: str,
    key: str,
    payload: dict[str, Any],
    client: Any | None = None,
) -> None:
    """Write the worker result object to S3.

    Parameters
    ----------
    bucket
        Destination S3 bucket.
    key
        Destination S3 object key.
    payload
        JSON-serializable result payload.
    client
        Optional S3-compatible client. When omitted, a boto3 S3 client is
        created.
    """
    s3_client = client or boto3.client("s3")
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"),
        ContentType="application/json",
    )


def run_example_worker(
    *,
    config: ExampleWorkerConfig | None = None,
    env: Mapping[str, str] | None = None,
    sqs_client: Any | None = None,
    s3_client: Any | None = None,
    timeout_seconds: int = 180,
    poll_interval_seconds: int = 5,
    wait_time_seconds: int = 20,
    sleeper: Any = time.sleep,
    timer: Any = time.monotonic,
) -> dict[str, Any]:
    """Run one happy-path example worker invocation.

    Parameters
    ----------
    config
        Optional pre-parsed worker configuration.
    env
        Optional environment mapping used when `config` is not supplied.
    sqs_client
        Optional SQS-compatible client.
    s3_client
        Optional S3-compatible client.
    timeout_seconds
        Maximum time to wait for a queue message.
    poll_interval_seconds
        Delay between empty receives.
    wait_time_seconds
        SQS long-poll duration per receive attempt.
    sleeper
        Sleep callable used between polling attempts.
    timer
        Monotonic timer callable used to compute the polling deadline.

    Returns
    -------
    dict[str, Any]
        Summary of the result object and processed task.
    """
    resolved_config = config or ExampleWorkerConfig.from_env(env)
    resolved_sqs_client = sqs_client or boto3.client("sqs")

    raw_message = poll_for_task_message(
        queue_url=resolved_config.task_queue_url,
        client=resolved_sqs_client,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        wait_time_seconds=wait_time_seconds,
        sleeper=sleeper,
        timer=timer,
    )

    receipt_handle = raw_message.get("ReceiptHandle")
    if not isinstance(receipt_handle, str) or not receipt_handle:
        raise RuntimeError("SQS message is missing ReceiptHandle.")

    task_message, parsed_body = decode_and_validate_task_message(
        raw_message,
        config=resolved_config,
    )
    result_key = result_object_key(resolved_config)
    result_payload = {
        "workflow_name": resolved_config.workflow_name,
        "env": {
            "graph_id": resolved_config.graph_id,
            "task_attempt": resolved_config.task_attempt,
            "task_id": resolved_config.task_id,
            "task_type": resolved_config.task_type,
        },
        "queue_body": parsed_body,
        "queue_message_id": raw_message.get("MessageId"),
        "result_key": result_key,
    }

    write_result_object(
        bucket=resolved_config.results_bucket,
        key=result_key,
        payload=result_payload,
        client=s3_client,
    )
    resolved_sqs_client.delete_message(
        QueueUrl=resolved_config.task_queue_url,
        ReceiptHandle=receipt_handle,
    )

    return {
        "bucket": resolved_config.results_bucket,
        "key": result_key,
        "task_message": task_message.model_dump(mode="json"),
    }


def main() -> int:
    """Run the example worker entrypoint.

    Returns
    -------
    int
        Process exit code.
    """
    result = run_example_worker()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
