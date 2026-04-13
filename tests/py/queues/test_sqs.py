from __future__ import annotations

import json

import boto3
import pytest
from moto import mock_aws

from website_backend.messages import CURRENT_CONTRACT_VERSION
from website_backend.messages import dump_message_json
from website_backend.messages import validate_orchestration_message
from website_backend.messages import validate_task_message
from website_backend.queues import LambdaEventQueue
from website_backend.queues import SQSQueue
from website_backend.queues import decode_sqs_delivery


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

    def test_decode_sqs_delivery_supports_receive_message_shape(
        self, orchestration_message
    ) -> None:
        delivery = decode_sqs_delivery(
            {
                "MessageId": "message-123",
                "ReceiptHandle": "receipt-123",
                "Body": dump_message_json(orchestration_message),
                "Attributes": {"ApproximateReceiveCount": "1"},
                "MessageAttributes": {
                    "message_type": {
                        "DataType": "String",
                        "StringValue": orchestration_message.message_type,
                    }
                },
            },
            message_decoder=validate_orchestration_message,
        )

        assert delivery.message == orchestration_message
        assert delivery.ack_token == "receipt-123"
        assert delivery.message_id == "message-123"
        assert delivery.attributes == {"ApproximateReceiveCount": "1"}
        assert delivery.message_attributes == {
            "message_type": {
                "DataType": "String",
                "StringValue": orchestration_message.message_type,
            }
        }


class TestLambdaEventQueue:
    def test_decode_sqs_delivery_supports_lambda_event_shape(
        self, orchestration_message
    ) -> None:
        delivery = decode_sqs_delivery(
            {
                "messageId": "message-123",
                "receiptHandle": "receipt-123",
                "body": dump_message_json(orchestration_message),
                "attributes": {"ApproximateReceiveCount": "1"},
                "messageAttributes": {
                    "message_type": {
                        "dataType": "String",
                        "stringValue": orchestration_message.message_type,
                    }
                },
            },
            message_decoder=validate_orchestration_message,
            body_field="body",
            ack_token_field="receiptHandle",
            message_id_field="messageId",
            attributes_field="attributes",
            message_attributes_field="messageAttributes",
        )

        assert delivery.message == orchestration_message
        assert delivery.ack_token == "receipt-123"
        assert delivery.message_id == "message-123"
        assert delivery.attributes == {"ApproximateReceiveCount": "1"}
        assert delivery.message_attributes == {
            "message_type": {
                "dataType": "String",
                "stringValue": orchestration_message.message_type,
            }
        }

    def test_lambda_event_queue_yields_single_delivery(
        self, orchestration_message
    ) -> None:
        queue = LambdaEventQueue(
            event={
                "Records": [
                    {
                        "messageId": "message-123",
                        "receiptHandle": "receipt-123",
                        "body": dump_message_json(orchestration_message),
                        "attributes": {"ApproximateReceiveCount": "1"},
                        "messageAttributes": {
                            "message_type": {
                                "dataType": "String",
                                "stringValue": orchestration_message.message_type,
                            }
                        },
                    }
                ]
            },
            message_decoder=validate_orchestration_message,
        )

        delivery = queue.get_message()

        assert delivery is not None
        assert delivery.message == orchestration_message
        assert delivery.ack_token == "receipt-123"
        assert delivery.message_id == "message-123"
        assert delivery.attributes == {"ApproximateReceiveCount": "1"}
        assert delivery.message_attributes == {
            "message_type": {
                "dataType": "String",
                "stringValue": orchestration_message.message_type,
            }
        }
        assert queue.get_message() is None

    def test_rejects_non_single_record_event(self) -> None:
        with pytest.raises(
            ValueError,
            match="Expected exactly one SQS record from the orchestration queue trigger",
        ):
            LambdaEventQueue(
                event={"Records": []},
                message_decoder=validate_orchestration_message,
            )
