from __future__ import annotations

import json
from typing import Any

import boto3
from moto import mock_aws

from website_backend.testing import read_sqs_messages


@mock_aws
def test_read_sqs_messages_returns_raw_sqs_message_payload() -> None:
    sqs = boto3.client("sqs", region_name="us-east-1")
    queue_url = sqs.create_queue(QueueName="example-queue")["QueueUrl"]
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({"result": "ok"}),
        MessageAttributes={
            "task_type": {
                "StringValue": "example",
                "DataType": "String",
            }
        },
    )

    result = read_sqs_messages.read_messages(
        queue_url=queue_url,
        timeout_seconds=1,
        poll_interval_seconds=0,
        client=sqs,
    )

    assert result["message_count"] == 1
    assert json.loads(result["messages"][0]["Body"]) == {"result": "ok"}
    assert result["messages"][0]["MessageAttributes"] == {
        "task_type": {
            "DataType": "String",
            "StringValue": "example",
        }
    }


def test_read_sqs_messages_clamps_long_poll_to_remaining_timeout() -> None:
    wait_times: list[int] = []

    class RecordingClient:
        def receive_message(self, **kwargs: Any) -> dict[str, Any]:
            wait_times.append(kwargs["WaitTimeSeconds"])
            return {}

    timer_values = iter([100.0, 100.0, 103.0])

    result = read_sqs_messages.read_messages(
        queue_url="https://example.invalid/queue",
        wait_time_seconds=10,
        timeout_seconds=3,
        poll_interval_seconds=0,
        client=RecordingClient(),
        sleeper=lambda _: None,
        timer=lambda: next(timer_values),
    )

    assert wait_times == [3]
    assert result == {
        "message_count": 0,
        "messages": [],
    }
