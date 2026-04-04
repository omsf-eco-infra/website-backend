from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any, TypeVar

import boto3

from website_backend.queues.aws_utils import derive_message_attributes
from website_backend.queues.protocols import InputQueue, OutputQueue, QueueDelivery

MessageT = TypeVar("MessageT")
MessageAttributes = Mapping[str, Mapping[str, Any]]


class SQSQueue(InputQueue[MessageT], OutputQueue[MessageT]):
    """SQS-backed queue adapter for canonical project message payloads.

    Parameters
    ----------
    queue_url : str
        URL of the target SQS queue.
    message_encoder : Callable[[MessageT], str]
        Callable that serializes a message object into the exact queue body.
    message_decoder : Callable[[Any], MessageT]
        Callable that converts a JSON-decoded body into a validated message
        instance.
    client : Any or None, default=None
        Optional SQS-compatible client. When omitted, a boto3 SQS client is
        created.
    wait_time_seconds : int, default=0
        Long-poll wait time used by `get_message`.
    visibility_timeout : int or None, default=None
        Optional visibility timeout override applied to `get_message`.
    extra_message_attributes_getter : Callable[[MessageT], MessageAttributes] or None, default=None
        Optional callable that returns additional AWS message attributes to add
        when publishing.
    message_group_id_getter : Callable[[MessageT], str | None] or None, default=None
        Optional callable that returns the FIFO message group identifier.
    message_deduplication_id_getter : Callable[[MessageT], str | None] or None, default=None
        Optional callable that returns the FIFO deduplication identifier.
    """

    def __init__(
        self,
        *,
        queue_url: str,
        message_encoder: Callable[[MessageT], str],
        message_decoder: Callable[[Any], MessageT],
        client: Any | None = None,
        wait_time_seconds: int = 0,
        visibility_timeout: int | None = None,
        extra_message_attributes_getter: Callable[[MessageT], MessageAttributes]
        | None = None,
        message_group_id_getter: Callable[[MessageT], str | None] | None = None,
        message_deduplication_id_getter: Callable[[MessageT], str | None] | None = None,
    ) -> None:
        self.queue_url = queue_url
        self.message_encoder = message_encoder
        self.message_decoder = message_decoder
        self.client = client or boto3.client("sqs")
        self.wait_time_seconds = wait_time_seconds
        self.visibility_timeout = visibility_timeout
        self.extra_message_attributes_getter = extra_message_attributes_getter
        self.message_group_id_getter = message_group_id_getter
        self.message_deduplication_id_getter = message_deduplication_id_getter

    def add_message(self, message: MessageT) -> None:
        request: dict[str, Any] = {
            "QueueUrl": self.queue_url,
            "MessageBody": self.message_encoder(message),
        }

        message_attributes = derive_message_attributes(message)
        if self.extra_message_attributes_getter is not None:
            message_attributes.update(
                {
                    name: dict(value)
                    for name, value in self.extra_message_attributes_getter(
                        message
                    ).items()
                }
            )
        if message_attributes:
            request["MessageAttributes"] = message_attributes

        if self.message_group_id_getter is not None:
            message_group_id = self.message_group_id_getter(message)
            if message_group_id is not None:
                request["MessageGroupId"] = message_group_id

        if self.message_deduplication_id_getter is not None:
            message_deduplication_id = self.message_deduplication_id_getter(message)
            if message_deduplication_id is not None:
                request["MessageDeduplicationId"] = message_deduplication_id

        self.client.send_message(**request)

    def get_message(self) -> QueueDelivery[MessageT] | None:
        request: dict[str, Any] = {
            "QueueUrl": self.queue_url,
            "MaxNumberOfMessages": 1,
            "WaitTimeSeconds": self.wait_time_seconds,
            "AttributeNames": ["All"],
            "MessageAttributeNames": ["All"],
        }
        if self.visibility_timeout is not None:
            request["VisibilityTimeout"] = self.visibility_timeout

        response = self.client.receive_message(**request)
        messages = response.get("Messages", [])
        if not messages:
            return None

        message = messages[0]
        raw_body = message["Body"]
        parsed_body = json.loads(raw_body)
        decoded_message = self.message_decoder(parsed_body)

        return QueueDelivery(
            message=decoded_message,
            ack_token=message["ReceiptHandle"],
            message_id=message.get("MessageId"),
            attributes=message.get("Attributes", {}),
            message_attributes=message.get("MessageAttributes", {}),
            raw_body=raw_body,
        )

    def mark_message_completed(self, delivery: QueueDelivery[MessageT]) -> None:
        if not delivery.ack_token:
            raise ValueError("Queue delivery is missing an ack token")
        self.client.delete_message(
            QueueUrl=self.queue_url,
            ReceiptHandle=delivery.ack_token,
        )
