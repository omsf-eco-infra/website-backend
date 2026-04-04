from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, TypeVar

import boto3

from website_backend.queues.aws_utils import derive_message_attributes
from website_backend.queues.protocols import OutputQueue

MessageT = TypeVar("MessageT")
MessageAttributes = Mapping[str, Mapping[str, Any]]


class SNSQueue(OutputQueue[MessageT]):
    """SNS-backed output adapter for canonical project message payloads.

    Parameters
    ----------
    topic_arn : str
        ARN of the target SNS topic.
    message_encoder : Callable[[MessageT], str]
        Callable that serializes a message object into the exact published
        message body.
    client : Any or None, default=None
        Optional SNS-compatible client. When omitted, a boto3 SNS client is
        created.
    extra_message_attributes_getter : Callable[[MessageT], MessageAttributes] or None, default=None
        Optional callable that returns additional AWS message attributes to add
        when publishing.
    subject_getter : Callable[[MessageT], str | None] or None, default=None
        Optional callable that returns the SNS message subject.
    message_group_id_getter : Callable[[MessageT], str | None] or None, default=None
        Optional callable that returns the FIFO message group identifier.
    message_deduplication_id_getter : Callable[[MessageT], str | None] or None, default=None
        Optional callable that returns the FIFO deduplication identifier.
    """

    def __init__(
        self,
        *,
        topic_arn: str,
        message_encoder: Callable[[MessageT], str],
        client: Any | None = None,
        extra_message_attributes_getter: Callable[[MessageT], MessageAttributes]
        | None = None,
        subject_getter: Callable[[MessageT], str | None] | None = None,
        message_group_id_getter: Callable[[MessageT], str | None] | None = None,
        message_deduplication_id_getter: Callable[[MessageT], str | None] | None = None,
    ) -> None:
        self.topic_arn = topic_arn
        self.message_encoder = message_encoder
        self.client = client or boto3.client("sns")
        self.extra_message_attributes_getter = extra_message_attributes_getter
        self.subject_getter = subject_getter
        self.message_group_id_getter = message_group_id_getter
        self.message_deduplication_id_getter = message_deduplication_id_getter

    def add_message(self, message: MessageT) -> None:
        request: dict[str, Any] = {
            "TopicArn": self.topic_arn,
            "Message": self.message_encoder(message),
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

        if self.subject_getter is not None:
            subject = self.subject_getter(message)
            if subject is not None:
                request["Subject"] = subject

        if self.message_group_id_getter is not None:
            message_group_id = self.message_group_id_getter(message)
            if message_group_id is not None:
                request["MessageGroupId"] = message_group_id

        if self.message_deduplication_id_getter is not None:
            message_deduplication_id = self.message_deduplication_id_getter(message)
            if message_deduplication_id is not None:
                request["MessageDeduplicationId"] = message_deduplication_id

        self.client.publish(**request)
