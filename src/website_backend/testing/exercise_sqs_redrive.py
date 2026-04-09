from __future__ import annotations

import argparse
import time
from typing import Any

import boto3

from website_backend.testing.common import (
    add_external_output_flag,
    add_polling_args,
    emit_result,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for driving SQS redrive behavior."""
    parser = argparse.ArgumentParser(
        description="Receive from SQS until the message drains from the source queue.",
    )
    parser.add_argument("--queue-url", required=True)
    parser.add_argument("--min-receive-count", type=int, default=1)
    parser.add_argument("--max-number-of-messages", type=int, default=1)
    parser.add_argument("--wait-time-seconds", type=int, default=1)
    parser.add_argument("--required-empty-polls", type=int, default=2)
    add_polling_args(parser, timeout_seconds=60, poll_interval_seconds=2)
    add_external_output_flag(parser)
    return parser


def _serialize_message(message: dict[str, Any]) -> dict[str, Any]:
    """Copy an SQS message into a JSON-serializable result payload."""
    # Normalize the boto3 response to the same stable subset exposed by the
    # standard SQS reader helper so Terraform wrappers can consume both helpers
    # with one output shape.
    return {
        "MessageId": message["MessageId"],
        "ReceiptHandle": message.get("ReceiptHandle"),
        "MD5OfBody": message.get("MD5OfBody"),
        "MD5OfMessageAttributes": message.get("MD5OfMessageAttributes"),
        "Attributes": message.get("Attributes", {}),
        "MessageAttributes": message.get("MessageAttributes", {}),
        "Body": message["Body"],
    }


def exercise_redrive(
    *,
    queue_url: str,
    min_receive_count: int = 1,
    max_number_of_messages: int = 1,
    wait_time_seconds: int = 1,
    required_empty_polls: int = 2,
    timeout_seconds: int = 60,
    poll_interval_seconds: int = 2,
    client: Any | None = None,
    sleeper: Any = time.sleep,
    timer: Any = time.monotonic,
) -> dict[str, Any]:
    """Receive from a source queue until it drains after one or more receives.

    The helper intentionally does not delete any received messages. It exists to
    exercise a queue's redrive policy so Terraform tests can then read the DLQ
    with the standard SQS reader helper.
    """
    sqs_client = client or boto3.client("sqs")
    deadline = timer() + timeout_seconds
    empty_poll_count = 0
    messages_by_id: dict[str, dict[str, Any]] = {}
    receive_count = 0

    while True:
        remaining_seconds = deadline - timer()
        if remaining_seconds <= 0:
            break

        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=max_number_of_messages,
            WaitTimeSeconds=min(wait_time_seconds, int(remaining_seconds)),
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
        )
        messages = response.get("Messages", [])

        if messages:
            empty_poll_count = 0
            receive_count += len(messages)
            for message in messages:
                messages_by_id[message["MessageId"]] = _serialize_message(message)
        elif receive_count >= min_receive_count:
            empty_poll_count += 1
            if empty_poll_count >= required_empty_polls:
                break

        if timer() >= deadline:
            break

        sleeper(poll_interval_seconds)

    return {
        "did_drain_from_source": (
            receive_count >= min_receive_count
            and empty_poll_count >= required_empty_polls
        ),
        "empty_poll_count": empty_poll_count,
        "message_count": len(messages_by_id),
        "messages": list(messages_by_id.values()),
        "receive_count": receive_count,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the SQS redrive helper as a CLI program."""
    args = build_parser().parse_args(argv)
    result = exercise_redrive(
        queue_url=args.queue_url,
        min_receive_count=args.min_receive_count,
        max_number_of_messages=args.max_number_of_messages,
        wait_time_seconds=args.wait_time_seconds,
        required_empty_polls=args.required_empty_polls,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
    )
    emit_result(result, external_output=args.external_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
