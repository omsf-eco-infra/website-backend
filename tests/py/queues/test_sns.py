from __future__ import annotations

import boto3
from moto import mock_aws

from website_backend.messages import CURRENT_CONTRACT_VERSION
from website_backend.messages import dump_message_json
from website_backend.queues import SNSQueue


class TestSNSQueue:
    @mock_aws
    def test_add_message_publishes_raw_body_and_attributes_to_sqs_subscription(
        self, task_message
    ) -> None:
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
            Attributes={"RawMessageDelivery": "true"},
        )
        queue = SNSQueue(
            topic_arn=topic_arn,
            message_encoder=dump_message_json,
            client=sns,
            extra_message_attributes_getter=lambda _message: {
                "workflow_name": {
                    "DataType": "String",
                    "StringValue": "example-workflow",
                }
            },
            subject_getter=lambda _message: "task-created",
        )

        queue.add_message(task_message)

        response = sqs.receive_message(
            QueueUrl=queue_url,
            MessageAttributeNames=["All"],
            WaitTimeSeconds=1,
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
