from __future__ import annotations

import json

import boto3
from moto import mock_aws

from website_backend.messages import CURRENT_CONTRACT_VERSION
from website_backend.messages import dump_message_json
from website_backend.messages import validate_orchestration_message
from website_backend.messages import validate_task_message
from website_backend.queues import SQSQueue


class TestSQSQueue:
    @mock_aws
    def test_add_message_serializes_body_and_attributes_for_fifo_queue(
        self, task_message
    ) -> None:
        sqs = boto3.client("sqs", region_name="us-east-1")
        queue_url = sqs.create_queue(
            QueueName="example.fifo",
            Attributes={"FifoQueue": "true", "ContentBasedDeduplication": "false"},
        )["QueueUrl"]
        queue = SQSQueue(
            queue_url=queue_url,
            message_encoder=dump_message_json,
            message_decoder=validate_task_message,
            client=sqs,
            extra_message_attributes_getter=lambda _message: {
                "workflow_name": {
                    "DataType": "String",
                    "StringValue": "example-workflow",
                }
            },
            message_group_id_getter=lambda _message: "group-1",
            message_deduplication_id_getter=lambda _message: "dedupe-1",
        )

        queue.add_message(task_message)

        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            MessageAttributeNames=["All"],
            AttributeNames=["All"],
        )
        messages = response["Messages"]
        assert len(messages) == 1
        assert messages[0]["Body"] == dump_message_json(task_message)
        assert messages[0]["MessageAttributes"] == {
            "task_type": {"DataType": "String", "StringValue": "prepare_inputs"},
            "version": {"DataType": "String", "StringValue": CURRENT_CONTRACT_VERSION},
            "workflow_name": {
                "DataType": "String",
                "StringValue": "example-workflow",
            },
        }

    @mock_aws
    def test_get_message_parses_body_and_mark_completed_deletes_message(
        self, orchestration_message
    ) -> None:
        sqs = boto3.client("sqs", region_name="us-east-1")
        queue_url = sqs.create_queue(QueueName="example-queue")["QueueUrl"]
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=dump_message_json(orchestration_message),
            MessageAttributes={
                "message_type": {
                    "DataType": "String",
                    "StringValue": "ADD_TASKS",
                }
            },
        )
        queue = SQSQueue(
            queue_url=queue_url,
            message_encoder=dump_message_json,
            message_decoder=validate_orchestration_message,
            client=sqs,
        )

        delivery = queue.get_message()

        assert delivery is not None
        assert delivery.message == orchestration_message
        assert json.loads(delivery.raw_body or "null") == json.loads(
            dump_message_json(orchestration_message)
        )
        assert delivery.message_attributes == {
            "message_type": {
                "DataType": "String",
                "StringValue": "ADD_TASKS",
            }
        }

        queue.mark_message_completed(delivery)

        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=0,
        )
        assert response.get("Messages") is None
