from __future__ import annotations

import json
from pathlib import Path

import boto3
from moto import mock_aws

from website_backend.testing import publish_sqs_message


@mock_aws
def test_publish_sqs_message_calls_fifo_queue_and_returns_metadata(
    tmp_path: Path,
) -> None:
    sqs = boto3.client("sqs", region_name="us-east-1")
    queue_url = sqs.create_queue(
        QueueName="example.fifo",
        Attributes={"FifoQueue": "true", "ContentBasedDeduplication": "false"},
    )["QueueUrl"]

    payload_file = tmp_path / "payload.json"
    payload_file.write_text(json.dumps({"hello": "world"}), encoding="utf-8")

    result = publish_sqs_message.publish_message(
        queue_url=queue_url,
        payload_file=str(payload_file),
        message_group_id="group-1",
        message_deduplication_id="dedupe-1",
        client=sqs,
    )

    assert result["message_id"]
    assert result["md5_of_message_body"]

    messages = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,
        MessageAttributeNames=["All"],
        AttributeNames=["All"],
    )["Messages"]
    assert len(messages) == 1
    assert messages[0]["Body"] == '{"hello": "world"}'
