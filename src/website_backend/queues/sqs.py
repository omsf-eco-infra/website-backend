from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

import boto3

from website_backend.queues.aws_utils import derive_message_attributes
from website_backend.queues.protocols import InputQueue, OutputQueue, QueueDelivery
from website_backend.queues.types import (
    AWSMessageAttributesMapping,
    MessageT,
    SQSDeliveryFields,
)


def decode_sqs_delivery(
    message: SQSDeliveryFields,
    *,
    message_decoder: Callable[[Any], MessageT],
    body_field: str = "Body",
    ack_token_field: str = "ReceiptHandle",
    message_id_field: str = "MessageId",
    attributes_field: str = "Attributes",
    message_attributes_field: str = "MessageAttributes",
) -> QueueDelivery[MessageT]:
    """Decode one SQS delivery using the provided transport field names."""

    raw_body = message[body_field]
    parsed_body = json.loads(raw_body)
    decoded_message = message_decoder(parsed_body)

    return QueueDelivery(
        message=decoded_message,
        ack_token=message[ack_token_field],
        message_id=message.get(message_id_field),
        attributes=message.get(attributes_field, {}),
        message_attributes=message.get(message_attributes_field, {}),
        raw_body=raw_body,
    )


class LambdaEventQueue(InputQueue[MessageT]):
    """Single-delivery queue backed by one SQS-triggered Lambda event record."""

    def __init__(
        self,
        *,
        event: Mapping[str, Any],
        message_decoder: Callable[[Any], MessageT],
    ) -> None:
        records = event.get("Records", [])
        if len(records) != 1:
            raise ValueError(
                "Expected exactly one SQS record from the orchestration queue trigger"
            )
        self._delivery = decode_sqs_delivery(
            records[0],
            message_decoder=message_decoder,
            body_field="body",
            ack_token_field="receiptHandle",
            message_id_field="messageId",
            attributes_field="attributes",
            message_attributes_field="messageAttributes",
        )

    def get_message(self) -> QueueDelivery[MessageT] | None:
        delivery = self._delivery
        self._delivery = None
        return delivery

    def mark_message_completed(self, delivery: QueueDelivery[MessageT]) -> None:
        del delivery


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
    extra_message_attributes_getter : Callable[[MessageT], AWSMessageAttributesMapping] or None, default=None
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
        extra_message_attributes_getter: Callable[
            [MessageT], AWSMessageAttributesMapping
        ]
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

        return decode_sqs_delivery(
            messages[0],
            message_decoder=self.message_decoder,
        )

    def mark_message_completed(self, delivery: QueueDelivery[MessageT]) -> None:
        if not delivery.ack_token:
            raise ValueError("Queue delivery is missing an ack token")
        self.client.delete_message(
            QueueUrl=self.queue_url,
            ReceiptHandle=delivery.ack_token,
        )
