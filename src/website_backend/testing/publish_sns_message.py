from __future__ import annotations

import argparse
from typing import Any

import boto3

from website_backend.testing.common import (
    add_external_output_flag,
    emit_result,
    load_json,
    load_text,
)


def build_parser() -> argparse.ArgumentParser:  # pragma: no cover
    """Build the CLI parser for SNS message publishing.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser for this helper.
    """
    parser = argparse.ArgumentParser(description="Publish a message to SNS.")
    parser.add_argument("--topic-arn", required=True)
    parser.add_argument("--payload-file", required=True)
    parser.add_argument("--subject")
    parser.add_argument("--message-group-id")
    parser.add_argument("--message-deduplication-id")
    parser.add_argument("--message-attributes-file")
    add_external_output_flag(parser)
    return parser


def publish_message(
    *,
    topic_arn: str,
    payload_file: str,
    subject: str | None = None,
    message_group_id: str | None = None,
    message_deduplication_id: str | None = None,
    message_attributes_file: str | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Publish a message to an SNS topic.

    Parameters
    ----------
    topic_arn : str
        ARN of the target SNS topic.
    payload_file : str
        Path to the message payload file.
    subject : str or None, default=None
        Optional SNS subject line.
    message_group_id : str or None, default=None
        FIFO topic message group identifier.
    message_deduplication_id : str or None, default=None
        FIFO topic message deduplication identifier.
    message_attributes_file : str or None, default=None
        Optional path to a JSON file containing SNS message attributes.
    client : Any or None, default=None
        Optional SNS-compatible client used instead of creating a boto3 client.

    Returns
    -------
    dict[str, Any]
        Publish result summary containing the SNS message ID.
    """
    sns_client = client or boto3.client("sns")
    request: dict[str, Any] = {
        "TopicArn": topic_arn,
        "Message": load_text(payload_file),
    }
    if subject is not None:
        request["Subject"] = subject
    if message_group_id is not None:
        request["MessageGroupId"] = message_group_id
    if message_deduplication_id is not None:
        request["MessageDeduplicationId"] = message_deduplication_id
    if message_attributes_file is not None:
        request["MessageAttributes"] = load_json(message_attributes_file)

    response = sns_client.publish(**request)
    return {"message_id": response["MessageId"]}


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    """Run the SNS publish helper as a CLI program.

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
        topic_arn=args.topic_arn,
        payload_file=args.payload_file,
        subject=args.subject,
        message_group_id=args.message_group_id,
        message_deduplication_id=args.message_deduplication_id,
        message_attributes_file=args.message_attributes_file,
    )
    emit_result(result, external_output=args.external_output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
