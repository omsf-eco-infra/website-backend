from __future__ import annotations

import argparse
from typing import Any

import boto3

from website_backend.testing.common import (
    add_external_output_flag,
    emit_result,
    load_text,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for SQS message publishing.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser for this helper.
    """
    parser = argparse.ArgumentParser(description="Publish a message to SQS.")
    parser.add_argument("--queue-url", required=True)
    parser.add_argument("--payload-file", required=True)
    parser.add_argument("--message-group-id")
    parser.add_argument("--message-deduplication-id")
    add_external_output_flag(parser)
    return parser


def publish_message(
    *,
    queue_url: str,
    payload_file: str,
    message_group_id: str | None = None,
    message_deduplication_id: str | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Publish a message to an SQS queue.

    Parameters
    ----------
    queue_url : str
        URL of the target SQS queue.
    payload_file : str
        Path to the message payload file.
    message_group_id : str or None, default=None
        FIFO queue message group identifier.
    message_deduplication_id : str or None, default=None
        FIFO queue message deduplication identifier.
    client : Any or None, default=None
        Optional SQS-compatible client used instead of creating a boto3 client.

    Returns
    -------
    dict[str, Any]
        Send result summary containing message identifiers returned by SQS.
    """
    sqs_client = client or boto3.client("sqs")
    payload = load_text(payload_file)
    request: dict[str, Any] = {
        "QueueUrl": queue_url,
        "MessageBody": payload,
    }
    if message_group_id is not None:
        request["MessageGroupId"] = message_group_id
    if message_deduplication_id is not None:
        request["MessageDeduplicationId"] = message_deduplication_id

    response = sqs_client.send_message(**request)
    result = {
        "message_id": response["MessageId"],
        "md5_of_message_body": response.get("MD5OfMessageBody"),
    }
    if "SequenceNumber" in response:
        result["sequence_number"] = response["SequenceNumber"]
    return result


def main(argv: list[str] | None = None) -> int:
    """Run the SQS publish helper as a CLI program.

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
    result = publish_message(
        queue_url=args.queue_url,
        payload_file=args.payload_file,
        message_group_id=args.message_group_id,
        message_deduplication_id=args.message_deduplication_id,
    )
    emit_result(result, external_output=args.external_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
