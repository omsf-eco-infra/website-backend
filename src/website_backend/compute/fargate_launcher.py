from __future__ import annotations

__all__ = [
    "FargateLauncherConfig",
    "build_run_task_request",
    "build_worker_environment_overrides",
    "decode_sqs_task_message",
    "launch_task_for_message",
    "load_fargate_launcher_config",
    "process_task_available_event",
    "task_message_client_token",
    "validate_sqs_lambda_event",
]

import hashlib
import json
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import boto3

from website_backend.messages import TaskMessage
from website_backend.messages import validate_contract_version
from website_backend.messages import validate_task_message
from website_backend.runtime import parse_json_string_list
from website_backend.runtime import required_env_from

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FargateLauncherConfig:
    ecs_cluster_arn: str
    ecs_task_definition_arn: str
    ecs_container_name: str
    subnet_ids: tuple[str, ...]
    security_group_ids: tuple[str, ...]
    assign_public_ip: str = "DISABLED"


def _parse_assign_public_ip(raw_value: str) -> str:
    normalized = raw_value.strip().upper()
    if normalized in {"ENABLED", "DISABLED"}:
        return normalized
    raise RuntimeError(
        "Environment variable ASSIGN_PUBLIC_IP must be ENABLED or DISABLED."
    )


def load_fargate_launcher_config(
    env: Mapping[str, str] | None = None,
) -> FargateLauncherConfig:
    source = env if env is not None else os.environ
    return FargateLauncherConfig(
        ecs_cluster_arn=required_env_from(source, "ECS_CLUSTER_ARN"),
        ecs_task_definition_arn=required_env_from(source, "ECS_TASK_DEFINITION_ARN"),
        ecs_container_name=required_env_from(source, "ECS_CONTAINER_NAME"),
        subnet_ids=parse_json_string_list(
            required_env_from(source, "SUBNET_IDS"),
            name="SUBNET_IDS",
        ),
        security_group_ids=parse_json_string_list(
            required_env_from(source, "SECURITY_GROUP_IDS"),
            name="SECURITY_GROUP_IDS",
        ),
        assign_public_ip=_parse_assign_public_ip(
            source.get("ASSIGN_PUBLIC_IP", "DISABLED")
        ),
    )


def validate_sqs_lambda_event(event: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate the expected one-record SQS Lambda event shape."""
    records = event.get("Records", [])
    if not isinstance(records, list) or len(records) != 1:
        raise ValueError("Expected exactly one SQS record from the task topic trigger")

    record = records[0]
    if not isinstance(record, Mapping):
        raise ValueError("Expected an SQS Lambda event record")

    event_source = record.get("EventSource") or record.get("eventSource")
    if event_source not in {None, "aws:sqs"}:
        raise ValueError("Expected an SQS Lambda event record")

    return record


def decode_sqs_task_message(event: Mapping[str, Any]) -> TaskMessage:
    sqs_record = validate_sqs_lambda_event(event)

    raw_message = sqs_record.get("body")
    if not isinstance(raw_message, str) or not raw_message:
        raise ValueError("SQS Lambda event record is missing body")

    try:
        parsed_message = json.loads(raw_message)
    except json.JSONDecodeError as exc:
        raise ValueError("SQS Lambda event record contains invalid JSON body") from exc

    message = validate_task_message(parsed_message)
    validate_contract_version(message.version)
    return message


def build_worker_environment_overrides(message: TaskMessage) -> list[dict[str, str]]:
    return [
        {"name": "GRAPH_ID", "value": message.graph_id},
        {"name": "TASK_ID", "value": message.task_id},
        {"name": "TASK_TYPE", "value": message.task_type},
        {"name": "TASK_ATTEMPT", "value": str(message.attempt)},
    ]


def task_message_client_token(message: TaskMessage) -> str:
    """Return a stable ECS idempotency token for one task attempt.

    ECS uses `clientToken` to deduplicate equivalent `RunTask` requests. Using
    `graph_id`, `task_id`, and `attempt` makes SNS redelivery of the same task
    attempt safe while still allowing later retry attempts to launch new work.
    """
    payload = "\0".join((message.graph_id, message.task_id, str(message.attempt)))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_run_task_request(
    message: TaskMessage,
    *,
    config: FargateLauncherConfig,
) -> dict[str, Any]:
    return {
        "cluster": config.ecs_cluster_arn,
        "taskDefinition": config.ecs_task_definition_arn,
        "launchType": "FARGATE",
        "networkConfiguration": {
            "awsvpcConfiguration": {
                "subnets": list(config.subnet_ids),
                "securityGroups": list(config.security_group_ids),
                "assignPublicIp": config.assign_public_ip,
            }
        },
        "overrides": {
            "containerOverrides": [
                {
                    "name": config.ecs_container_name,
                    "environment": build_worker_environment_overrides(message),
                }
            ]
        },
        "clientToken": task_message_client_token(message),
    }


def launch_task_for_message(
    message: TaskMessage,
    *,
    config: FargateLauncherConfig | None = None,
    ecs_client: Any | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    validate_contract_version(message.version)
    resolved_config = config or load_fargate_launcher_config(env)
    client = ecs_client or boto3.client("ecs")
    request = build_run_task_request(message, config=resolved_config)
    response = client.run_task(**request)

    failures = response.get("failures", [])
    if failures:
        raise RuntimeError(f"ECS run_task returned failures: {failures!r}")

    launched_tasks = response.get("tasks", [])
    if not launched_tasks:
        raise RuntimeError("ECS run_task returned no tasks.")

    _logger.info(
        "Launched ECS task for graph_id=%s task_id=%s attempt=%s task_arns=%s",
        message.graph_id,
        message.task_id,
        message.attempt,
        [task.get("taskArn") for task in launched_tasks],
    )
    return response


def process_task_available_event(
    event: Mapping[str, Any],
    *,
    config: FargateLauncherConfig | None = None,
    ecs_client: Any | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    message = decode_sqs_task_message(event)
    return launch_task_for_message(
        message,
        config=config,
        ecs_client=ecs_client,
        env=env,
    )
