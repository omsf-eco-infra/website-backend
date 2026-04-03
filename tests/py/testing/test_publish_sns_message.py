from __future__ import annotations

import json
from pathlib import Path

import boto3
from moto import mock_aws

from website_backend.testing import publish_sns_message


@mock_aws
def test_publish_sns_message_loads_attributes_file(tmp_path: Path) -> None:
    region = "us-east-1"
    sns = boto3.client("sns", region_name=region)
    sqs = boto3.client("sqs", region_name=region)
    topic_arn = sns.create_topic(Name="example-topic")["TopicArn"]
    queue_url = sqs.create_queue(QueueName="subscriber-queue")["QueueUrl"]
    queue_arn = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["QueueArn"],
    )["Attributes"]["QueueArn"]
    sns.subscribe(
        TopicArn=topic_arn,
        Protocol="sqs",
        Endpoint=queue_arn,
    )

    payload_file = tmp_path / "payload.json"
    payload = {"hello": "world"}
    payload_file.write_text(json.dumps(payload), encoding="utf-8")
    attributes_file = tmp_path / "attributes.json"
    attributes_file.write_text(
        json.dumps(
            {
                "task_type": {
                    "DataType": "String",
                    "StringValue": "example",
                }
            }
        ),
        encoding="utf-8",
    )

    result = publish_sns_message.publish_message(
        topic_arn=topic_arn,
        payload_file=str(payload_file),
        subject="example-subject",
        message_attributes_file=str(attributes_file),
        client=sns,
    )

    assert result["message_id"]

    response = sqs.receive_message(
        QueueUrl=queue_url,
        MessageAttributeNames=["All"],
        WaitTimeSeconds=1,
    )
    messages = response["Messages"]
    assert len(messages) == 1

    notification = json.loads(messages[0]["Body"])
    assert notification["Message"] == json.dumps(payload)
    assert notification["Subject"] == "example-subject"
    assert notification["MessageAttributes"] == {
        "task_type": {
            "Type": "String",
            "Value": "example",
        }
    }
