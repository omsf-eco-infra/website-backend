from __future__ import annotations

import argparse
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

from website_backend.testing.common import (
    add_external_output_flag,
    add_polling_args,
    emit_result,
    maybe_parse_json,
)


def build_parser() -> argparse.ArgumentParser:  # pragma: no cover
    """Build the CLI parser for S3 object reads.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser for this helper.
    """
    parser = argparse.ArgumentParser(description="Read an S3 object.")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--key", required=True)
    add_polling_args(parser)
    add_external_output_flag(parser)
    return parser


def _is_not_found_error(error: ClientError) -> bool:
    """Return whether an S3 client error represents a missing object.

    Parameters
    ----------
    error : botocore.exceptions.ClientError
        Error raised by the S3 client.

    Returns
    -------
    bool
        `True` when the error code indicates the object does not exist.
    """
    code = error.response.get("Error", {}).get("Code", "")
    return code in {"404", "NoSuchKey", "NotFound"}


def read_object(
    *,
    bucket: str,
    key: str,
    timeout_seconds: int = 180,
    poll_interval_seconds: int = 5,
    client: Any | None = None,
    sleeper: Any = time.sleep,
    timer: Any = time.monotonic,
) -> dict[str, Any]:
    """Read an S3 object, polling until it appears or the timeout expires.

    Parameters
    ----------
    bucket : str
        Name of the S3 bucket.
    key : str
        Object key to read.
    timeout_seconds : int, default=180
        Maximum time to wait for the object to appear.
    poll_interval_seconds : int, default=5
        Delay between polling attempts when the object is missing.
    client : Any or None, default=None
        Optional S3-compatible client used instead of creating a boto3 client.
    sleeper : Any, default=time.sleep
        Sleep callable used between polling attempts.
    timer : Any, default=time.monotonic
        Monotonic timer callable used to compute the polling deadline.

    Returns
    -------
    dict[str, Any]
        Structured object details, including decoded body text and parsed JSON
        when available. Returns `{"exists": False}` on timeout.
    """
    s3_client = client or boto3.client("s3")
    deadline = timer() + timeout_seconds

    while True:
        try:
            head = s3_client.head_object(Bucket=bucket, Key=key)
            response = s3_client.get_object(Bucket=bucket, Key=key)
            body_bytes = response["Body"].read()
            body_text = body_bytes.decode("utf-8")
            result: dict[str, Any] = {
                "exists": True,
                "content_length": head.get("ContentLength"),
                "content_type": head.get("ContentType"),
                "etag": head.get("ETag"),
                "metadata": head.get("Metadata", {}),
                "body_text": body_text,
            }
            body_is_json, body_json = maybe_parse_json(body_text)
            if body_is_json:
                result["body_json"] = body_json
            return result
        except ClientError as error:
            if not _is_not_found_error(error):
                raise
            if timer() >= deadline:
                return {"exists": False}
            sleeper(poll_interval_seconds)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    """Run the S3 object reader as a CLI program.

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
    result = read_object(
        bucket=args.bucket,
        key=args.key,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
    )
    emit_result(result, external_output=args.external_output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
