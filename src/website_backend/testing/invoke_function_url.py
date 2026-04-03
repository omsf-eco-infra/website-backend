from __future__ import annotations

import argparse
from typing import Any

import requests

from website_backend.testing.common import (
    add_external_output_flag,
    emit_result,
    load_json,
    load_text,
    maybe_parse_json,
    write_json,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for Function URL invocation.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser for this helper.
    """
    parser = argparse.ArgumentParser(description="Invoke a Lambda Function URL.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--method", default="POST")
    parser.add_argument("--body-file")
    parser.add_argument("--headers-file")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    add_external_output_flag(parser)
    return parser


def invoke_function_url(
    *,
    url: str,
    output_file: str,
    method: str = "POST",
    body_file: str | None = None,
    headers_file: str | None = None,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """Invoke a Lambda Function URL and persist the HTTP response artifact.

    Parameters
    ----------
    url : str
        Function URL to invoke.
    output_file : str
        Artifact path where the captured response should be written as JSON.
    method : str, default="POST"
        HTTP method to use for the request.
    body_file : str or None, default=None
        Optional path to a request-body file.
    headers_file : str or None, default=None
        Optional path to a JSON file containing request headers.
    timeout_seconds : int, default=30
        Request timeout passed to `requests`.

    Returns
    -------
    dict[str, Any]
        Summary containing the artifact path and HTTP status code.
    """
    headers: dict[str, str] | None = None
    if headers_file is not None:
        headers = load_json(headers_file)
    body = load_text(body_file) if body_file is not None else None

    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        data=body,
        timeout=timeout_seconds,
    )
    body_text = response.text
    artifact: dict[str, Any] = {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body_text": body_text,
    }
    body_is_json, body_json = maybe_parse_json(body_text)
    if body_is_json:
        artifact["body_json"] = body_json

    artifact_path = write_json(output_file, artifact)
    return {
        "artifact_path": str(artifact_path),
        "status_code": response.status_code,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the Function URL helper as a CLI program.

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
    result = invoke_function_url(
        url=args.url,
        output_file=args.output_file,
        method=args.method,
        body_file=args.body_file,
        headers_file=args.headers_file,
        timeout_seconds=args.timeout_seconds,
    )
    emit_result(result, external_output=args.external_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
