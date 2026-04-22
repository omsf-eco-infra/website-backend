from __future__ import annotations

import argparse
import time
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import boto3
import sqlalchemy as sqla
from botocore.exceptions import ClientError

from website_backend.orchestration.taskdb import TaskStatusDB
from website_backend.testing.common import (
    add_external_output_flag,
    add_polling_args,
    emit_result,
)


def build_parser() -> argparse.ArgumentParser:  # pragma: no cover
    """Build the CLI parser for taskdb snapshot inspection."""
    parser = argparse.ArgumentParser(
        description="Inspect a taskdb SQLite snapshot in S3."
    )
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--previous-etag")
    add_polling_args(parser)
    add_external_output_flag(parser)
    return parser


def _is_not_found_error(error: ClientError) -> bool:
    code = error.response.get("Error", {}).get("Code", "")
    return code in {"404", "NoSuchKey", "NotFound"}


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_value(item) for item in value]
    return value


def _missing_snapshot_summary() -> dict[str, Any]:
    return {
        "exists": False,
        "etag": None,
        "content_length": None,
        "task_count": 0,
        "task_ids": [],
        "tasks_by_id": {},
    }


def _load_snapshot_summary(path: Path) -> dict[str, Any]:
    taskdb = TaskStatusDB.from_filename(path)
    try:
        with taskdb.engine.connect() as conn:
            task_rows = {
                row["taskid"]: {
                    column_name: _normalize_value(column_value)
                    for column_name, column_value in dict(row).items()
                }
                for row in conn.execute(sqla.select(taskdb.tasks_table)).mappings()
            }
            task_type_rows = {
                row["taskid"]: row["task_type"]
                for row in conn.execute(
                    sqla.select(
                        taskdb.task_types_table.c.taskid,
                        taskdb.task_types_table.c.task_type,
                    )
                ).mappings()
            }
            task_detail_rows = {
                row["taskid"]: _normalize_value(row["task_details"])
                for row in conn.execute(
                    sqla.select(
                        taskdb.task_details_table.c.taskid,
                        taskdb.task_details_table.c.task_details,
                    )
                ).mappings()
            }
    finally:
        taskdb.engine.dispose()

    task_ids = sorted(task_rows)
    return {
        "task_count": len(task_ids),
        "task_ids": task_ids,
        "tasks_by_id": {
            task_id: {
                "task_type": task_type_rows[task_id],
                "task_details": task_detail_rows[task_id],
                "attempt": task_rows[task_id]["tries"],
                "task_record": task_rows[task_id],
            }
            for task_id in task_ids
        },
    }


def inspect_snapshot(
    *,
    bucket: str,
    key: str,
    previous_etag: str | None = None,
    timeout_seconds: int = 180,
    poll_interval_seconds: int = 5,
    client: Any | None = None,
    sleeper: Any = time.sleep,
    timer: Any = time.monotonic,
) -> dict[str, Any]:
    """Inspect an S3-backed taskdb snapshot, optionally waiting for a new ETag."""
    s3_client = client or boto3.client("s3")
    deadline = timer() + timeout_seconds

    while True:
        try:
            head = s3_client.head_object(Bucket=bucket, Key=key)
        except ClientError as error:
            if not _is_not_found_error(error):
                raise
            if timer() >= deadline:
                return _missing_snapshot_summary()
            sleeper(poll_interval_seconds)
            continue

        etag = head["ETag"]
        if previous_etag is not None and etag == previous_etag and timer() < deadline:
            sleeper(poll_interval_seconds)
            continue

        with TemporaryDirectory() as temp_dir:
            snapshot_path = Path(temp_dir) / "taskdb.sqlite"
            s3_client.download_file(bucket, key, str(snapshot_path))
            summary = _load_snapshot_summary(snapshot_path)

        summary.update(
            {
                "exists": True,
                "etag": etag,
                "content_length": head.get("ContentLength"),
            }
        )
        return summary


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    """Run the taskdb snapshot inspector as a CLI program."""
    args = build_parser().parse_args(argv)
    result = inspect_snapshot(
        bucket=args.bucket,
        key=args.key,
        previous_etag=args.previous_etag,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
    )
    emit_result(result, external_output=args.external_output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
