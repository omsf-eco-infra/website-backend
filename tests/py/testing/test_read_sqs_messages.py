from __future__ import annotations

import json

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


@mock_aws
def test_read_sqs_messages_optionally_deletes_messages_after_read() -> None:
    sqs = boto3.client("sqs", region_name="us-east-1")
    queue_url = sqs.create_queue(
        QueueName="example.fifo",
        Attributes={
            "FifoQueue": "true",
            "ContentBasedDeduplication": "false",
            "VisibilityTimeout": "0",
        },
    )["QueueUrl"]
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({"result": "ok"}),
        MessageGroupId="group-1",
        MessageDeduplicationId="dedupe-1",
    )

    result = read_sqs_messages.read_messages(
        queue_url=queue_url,
        delete_after_read=True,
        timeout_seconds=1,
        poll_interval_seconds=0,
        client=sqs,
    )

    assert result["message_count"] == 1
    follow_up = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=0,
    )
    assert follow_up.get("Messages") is None
