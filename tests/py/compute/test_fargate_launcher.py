from __future__ import annotations

import json
from typing import Any

import pytest
from botocore.exceptions import ClientError
from pydantic import ValidationError

from website_backend.compute import (
    FargateLauncherConfig,
    build_run_task_request,
    build_worker_environment_overrides,
    decode_sns_task_message,
    launch_task_for_message,
    load_fargate_launcher_config,
    process_task_available_event,
    task_message_client_token,
    validate_sns_lambda_event,
)
from website_backend.messages import CURRENT_CONTRACT_VERSION
from website_backend.messages import TaskMessage
from website_backend.messages import validate_task_message


def _task_message(
    *,
    version: str = CURRENT_CONTRACT_VERSION,
    attempt: int = 1,
) -> TaskMessage:
    return validate_task_message(
        {
            "version": version,
            "task_type": "prepare_inputs",
            "task_id": "task-1",
            "attempt": attempt,
            "graph_id": "run-123",
            "task_details": {"step": 1},
        }
    )


def _sns_event_for(message: TaskMessage) -> dict[str, object]:
    return {
        "Records": [
            {
                "EventSource": "aws:sns",
                "Sns": {
                    "MessageId": "message-123",
                    "Message": message.model_dump_json(),
                },
            }
        ]
    }


class StubECSClient:
    def __init__(
        self,
        *,
        response: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response or {
            "tasks": [{"taskArn": "arn:aws:ecs:us-east-1:123456789012:task/example"}],
            "failures": [],
        }
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def run_task(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


@pytest.fixture
def config() -> FargateLauncherConfig:
    return FargateLauncherConfig(
        ecs_cluster_arn="arn:aws:ecs:us-east-1:123456789012:cluster/example",
        ecs_task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/example:3",
        ecs_container_name="worker",
        subnet_ids=("subnet-123", "subnet-456"),
        security_group_ids=("sg-123",),
        assign_public_ip="DISABLED",
    )


class TestLoadFargateLauncherConfig:
    def test_loads_required_env_contract_and_defaults_assign_public_ip(self) -> None:
        config = load_fargate_launcher_config(
            {
                "ECS_CLUSTER_ARN": "cluster-arn",
                "ECS_TASK_DEFINITION_ARN": "task-def-arn",
                "ECS_CONTAINER_NAME": "worker",
                "SUBNET_IDS": json.dumps(["subnet-123", "subnet-456"]),
                "SECURITY_GROUP_IDS": json.dumps(["sg-123"]),
            }
        )

        assert config == FargateLauncherConfig(
            ecs_cluster_arn="cluster-arn",
            ecs_task_definition_arn="task-def-arn",
            ecs_container_name="worker",
            subnet_ids=("subnet-123", "subnet-456"),
            security_group_ids=("sg-123",),
            assign_public_ip="DISABLED",
        )

    def test_normalizes_assign_public_ip(self) -> None:
        config = load_fargate_launcher_config(
            {
                "ECS_CLUSTER_ARN": "cluster-arn",
                "ECS_TASK_DEFINITION_ARN": "task-def-arn",
                "ECS_CONTAINER_NAME": "worker",
                "SUBNET_IDS": json.dumps(["subnet-123"]),
                "SECURITY_GROUP_IDS": json.dumps(["sg-123"]),
                "ASSIGN_PUBLIC_IP": "enabled",
            }
        )

        assert config.assign_public_ip == "ENABLED"

    def test_rejects_invalid_assign_public_ip(self) -> None:
        with pytest.raises(
            RuntimeError,
            match="Environment variable ASSIGN_PUBLIC_IP must be ENABLED or DISABLED",
        ):
            load_fargate_launcher_config(
                {
                    "ECS_CLUSTER_ARN": "cluster-arn",
                    "ECS_TASK_DEFINITION_ARN": "task-def-arn",
                    "ECS_CONTAINER_NAME": "worker",
                    "SUBNET_IDS": json.dumps(["subnet-123"]),
                    "SECURITY_GROUP_IDS": json.dumps(["sg-123"]),
                    "ASSIGN_PUBLIC_IP": "sometimes",
                }
            )


class TestDecodeSnsTaskMessage:
    def test_validate_sns_lambda_event_returns_sns_payload(self) -> None:
        message = _task_message()

        sns_record = validate_sns_lambda_event(_sns_event_for(message))

        assert sns_record["Message"] == message.model_dump_json()

    def test_decodes_single_sns_record(self) -> None:
        message = _task_message()

        decoded = decode_sns_task_message(_sns_event_for(message))

        assert decoded == message

    def test_validate_sns_lambda_event_rejects_non_single_record_event(self) -> None:
        with pytest.raises(
            ValueError,
            match="Expected exactly one SNS record from the task topic trigger",
        ):
            validate_sns_lambda_event({"Records": []})

    def test_validate_sns_lambda_event_rejects_wrong_event_source(self) -> None:
        message = _task_message()
        event = _sns_event_for(message)
        event["Records"][0]["EventSource"] = "aws:sqs"

        with pytest.raises(ValueError, match="Expected an SNS Lambda event record"):
            validate_sns_lambda_event(event)

    def test_validate_sns_lambda_event_rejects_non_mapping_record(self) -> None:
        with pytest.raises(ValueError, match="Expected an SNS Lambda event record"):
            validate_sns_lambda_event({"Records": ["bad-record"]})

    def test_validate_sns_lambda_event_rejects_missing_sns_payload(self) -> None:
        with pytest.raises(ValueError, match="missing Sns payload"):
            validate_sns_lambda_event({"Records": [{"EventSource": "aws:sns"}]})

    def test_rejects_missing_sns_message(self) -> None:
        with pytest.raises(ValueError, match="missing Sns.Message"):
            decode_sns_task_message(
                {"Records": [{"EventSource": "aws:sns", "Sns": {}}]}
            )

    def test_rejects_invalid_json_body(self) -> None:
        with pytest.raises(ValueError, match="invalid JSON message body"):
            decode_sns_task_message(
                {
                    "Records": [
                        {
                            "EventSource": "aws:sns",
                            "Sns": {"Message": "{not-json"},
                        }
                    ]
                }
            )

    def test_rejects_invalid_task_message(self) -> None:
        with pytest.raises(ValidationError):
            decode_sns_task_message(
                {
                    "Records": [
                        {
                            "EventSource": "aws:sns",
                            "Sns": {"Message": json.dumps({"task_id": "task-1"})},
                        }
                    ]
                }
            )

    def test_rejects_contract_version_mismatch(self) -> None:
        with pytest.raises(ValueError, match="current contract version"):
            decode_sns_task_message(_sns_event_for(_task_message(version="1776.07")))


class TestRunTaskRequest:
    def test_builds_worker_environment_overrides(self) -> None:
        environment = build_worker_environment_overrides(_task_message(attempt=2))

        assert environment == [
            {"name": "GRAPH_ID", "value": "run-123"},
            {"name": "TASK_ID", "value": "task-1"},
            {"name": "TASK_TYPE", "value": "prepare_inputs"},
            {"name": "TASK_ATTEMPT", "value": "2"},
        ]

    def test_builds_ecs_run_task_request(self, config: FargateLauncherConfig) -> None:
        message = _task_message()

        request = build_run_task_request(message, config=config)

        assert request == {
            "cluster": config.ecs_cluster_arn,
            "taskDefinition": config.ecs_task_definition_arn,
            "launchType": "FARGATE",
            "networkConfiguration": {
                "awsvpcConfiguration": {
                    "subnets": ["subnet-123", "subnet-456"],
                    "securityGroups": ["sg-123"],
                    "assignPublicIp": "DISABLED",
                }
            },
            "overrides": {
                "containerOverrides": [
                    {
                        "name": "worker",
                        "environment": [
                            {"name": "GRAPH_ID", "value": "run-123"},
                            {"name": "TASK_ID", "value": "task-1"},
                            {"name": "TASK_TYPE", "value": "prepare_inputs"},
                            {"name": "TASK_ATTEMPT", "value": "1"},
                        ],
                    }
                ]
            },
            "clientToken": task_message_client_token(message),
        }

    def test_duplicate_message_uses_same_client_token(
        self,
        config: FargateLauncherConfig,
    ) -> None:
        first = _task_message(attempt=1)
        duplicate = _task_message(attempt=1)
        retry = _task_message(attempt=2)

        assert task_message_client_token(first) == task_message_client_token(duplicate)
        assert task_message_client_token(first) != task_message_client_token(retry)
        assert (
            build_run_task_request(
                first,
                config=config,
            )["clientToken"]
            == build_run_task_request(
                duplicate,
                config=config,
            )["clientToken"]
        )


class TestLaunchTaskForMessage:
    def test_calls_ecs_run_task_and_returns_response(
        self,
        config: FargateLauncherConfig,
    ) -> None:
        ecs = StubECSClient()

        response = launch_task_for_message(
            _task_message(),
            config=config,
            ecs_client=ecs,
        )

        assert response["tasks"][0]["taskArn"].endswith(":task/example")
        assert len(ecs.calls) == 1
        assert ecs.calls[0]["cluster"] == config.ecs_cluster_arn

    def test_process_task_available_event_loads_message_and_launches_task(
        self,
        config: FargateLauncherConfig,
    ) -> None:
        ecs = StubECSClient()
        message = _task_message(attempt=2)

        response = process_task_available_event(
            _sns_event_for(message),
            config=config,
            ecs_client=ecs,
        )

        assert response["tasks"][0]["taskArn"].endswith(":task/example")
        assert ecs.calls[0]["clientToken"] == task_message_client_token(message)

    def test_raises_client_error_from_ecs(
        self,
        config: FargateLauncherConfig,
    ) -> None:
        ecs = StubECSClient(
            error=ClientError(
                {"Error": {"Code": "ThrottlingException", "Message": "slow down"}},
                "RunTask",
            )
        )

        with pytest.raises(ClientError):
            launch_task_for_message(
                _task_message(),
                config=config,
                ecs_client=ecs,
            )

    def test_raises_when_ecs_returns_failures(
        self,
        config: FargateLauncherConfig,
    ) -> None:
        ecs = StubECSClient(
            response={
                "tasks": [],
                "failures": [
                    {
                        "arn": "arn:aws:ecs:us-east-1:123456789012:cluster/example",
                        "reason": "RESOURCE:MEMORY",
                    }
                ],
            }
        )

        with pytest.raises(RuntimeError, match="ECS run_task returned failures"):
            launch_task_for_message(
                _task_message(),
                config=config,
                ecs_client=ecs,
            )

    def test_raises_when_ecs_returns_no_tasks_and_no_failures(
        self,
        config: FargateLauncherConfig,
    ) -> None:
        ecs = StubECSClient(response={"tasks": [], "failures": []})

        with pytest.raises(RuntimeError, match="ECS run_task returned no tasks"):
            launch_task_for_message(
                _task_message(),
                config=config,
                ecs_client=ecs,
            )
