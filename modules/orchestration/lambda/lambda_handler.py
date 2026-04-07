from __future__ import annotations

import os
from typing import Any

from website_backend.messages import dump_message_json
from website_backend.messages import validate_orchestration_message
from website_backend.orchestration.s3_sqlite import S3SQLiteOrchestrator
from website_backend.queues import LambdaEventQueue
from website_backend.queues import SNSQueue
from website_backend.runtime import required_env


def s3_sqlite_handler(event: dict[str, Any], context: Any) -> bool:
    del context

    required_env("WORKFLOW_NAME")
    bucket = required_env("STATE_BUCKET")
    topic_arn = required_env("TASK_TOPIC_ARN")

    # This runtime accepts STATE_PREFIX in its environment contract, but the
    # message graph_id remains the authoritative full S3 key in Phase 2.
    os.environ.get("STATE_PREFIX")

    # This handler expects to be invoked by the orchestration SQS queue event
    # source mapping, so Lambda owns queue acknowledgement and provides the
    # canonical message body in the incoming SQS record.
    orchestration_queue = LambdaEventQueue(
        event=event,
        message_decoder=validate_orchestration_message,
    )
    task_queue = SNSQueue(
        topic_arn=topic_arn,
        message_encoder=dump_message_json,
        message_group_id_getter=lambda message: message.graph_id,
    )
    orchestrator = S3SQLiteOrchestrator(
        orchestration_queue,
        task_queue,
        bucket=bucket,
        scratch_dir="/tmp",
    )

    return bool(orchestrator.process())
