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
    """Build the CLI parser for SQS message reads.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser for this helper.
    """
    parser = argparse.ArgumentParser(description="Read messages from SQS.")
    parser.add_argument("--queue-url", required=True)
    parser.add_argument("--min-message-count", type=int, default=1)
    parser.add_argument("--max-number-of-messages", type=int, default=10)
    parser.add_argument("--wait-time-seconds", type=int, default=5)
    parser.add_argument(
        "--delete-after-read",
        action="store_true",
        help="Delete the collected messages after reading them.",
    )
    add_polling_args(parser)
    add_external_output_flag(parser)
    return parser


def _serialize_message(message: dict[str, Any]) -> dict[str, Any]:
    """Copy an SQS message into a JSON-serializable result payload.

    Parameters
    ----------
    message : dict[str, Any]
        Message dictionary returned by `receive_message`.

    Returns
    -------
    dict[str, Any]
        Message record copied from the SQS response.
    """
    return {
        "MessageId": message["MessageId"],
        "ReceiptHandle": message.get("ReceiptHandle"),
        "MD5OfBody": message.get("MD5OfBody"),
        "MD5OfMessageAttributes": message.get("MD5OfMessageAttributes"),
        "Attributes": message.get("Attributes", {}),
        "MessageAttributes": message.get("MessageAttributes", {}),
        "Body": message["Body"],
    }


def read_messages(
    *,
    queue_url: str,
    min_message_count: int = 1,
    max_number_of_messages: int = 10,
    wait_time_seconds: int = 5,
    delete_after_read: bool = False,
    timeout_seconds: int = 180,
    poll_interval_seconds: int = 5,
    client: Any | None = None,
    sleeper: Any = time.sleep,
    timer: Any = time.monotonic,
) -> dict[str, Any]:
    """Read messages from an SQS queue until enough are collected or timeout.

    Parameters
    ----------
    queue_url : str
        URL of the target SQS queue.
    min_message_count : int, default=1
        Minimum number of distinct messages to collect before returning.
    max_number_of_messages : int, default=10
        Maximum number of messages to request per receive call.
    wait_time_seconds : int, default=5
        SQS long-poll duration for each receive call.
    delete_after_read : bool, default=False
        Whether to delete the collected messages after reading them.
    timeout_seconds : int, default=180
        Maximum total time to wait for messages.
    poll_interval_seconds : int, default=5
        Delay between receive attempts when more messages are needed.
    client : Any or None, default=None
        Optional SQS-compatible client used instead of creating a boto3 client.
    sleeper : Any, default=time.sleep
        Sleep callable used between polling attempts.
    timer : Any, default=time.monotonic
        Monotonic timer callable used to compute the polling deadline.

    Returns
    -------
    dict[str, Any]
        Summary containing the number of collected messages and their raw SQS
        message records.
    """
    sqs_client = client or boto3.client("sqs")
    deadline = timer() + timeout_seconds
    messages_by_id: dict[str, dict[str, Any]] = {}

    while True:
        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=max_number_of_messages,
            WaitTimeSeconds=wait_time_seconds,
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
        )
        for message in response.get("Messages", []):
            messages_by_id[message["MessageId"]] = _serialize_message(message)

        if len(messages_by_id) >= min_message_count:
            break

        if timer() >= deadline:
            break

        sleeper(poll_interval_seconds)

    if delete_after_read:
        for message in messages_by_id.values():
            receipt_handle = message.get("ReceiptHandle")
            if receipt_handle:
                sqs_client.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=receipt_handle,
                )

    return {
        "message_count": len(messages_by_id),
        "messages": list(messages_by_id.values()),
    }


def main(argv: list[str] | None = None) -> int:
    """Run the SQS reader as a CLI program.

    Parameters
    ----------
    argv : list[str] or None, default=None
        Explicit argument list. When `None`, arguments are read from `sys.argv`.

    Returns
    -------
    int
        Process exit code.
    """
    args = build_parser().parse_args(argv)
    result = read_messages(
        queue_url=args.queue_url,
        min_message_count=args.min_message_count,
        max_number_of_messages=args.max_number_of_messages,
        wait_time_seconds=args.wait_time_seconds,
        delete_after_read=args.delete_after_read,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
    )
    emit_result(result, external_output=args.external_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
