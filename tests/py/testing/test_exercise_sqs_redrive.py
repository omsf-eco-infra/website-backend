from __future__ import annotations

import json
from itertools import count
from typing import Any

from website_backend.testing import exercise_sqs_redrive


def test_exercise_sqs_redrive_detects_source_queue_drain() -> None:
    queue_url = "https://example.invalid/queue"
    responses = iter(
        [
            {
                "Messages": [
                    {
                        "MessageId": "message-1",
                        "Body": json.dumps({"task_id": "task-redrive"}),
                        "MessageAttributes": {
                            "task_type": {
                                "DataType": "String",
                                "StringValue": "stage_inputs",
                            }
                        },
                    }
                ]
            },
            {},
            {},
        ]
    )

    class SequenceClient:
        def receive_message(self, **kwargs: Any) -> dict[str, Any]:
            assert kwargs["QueueUrl"] == queue_url
            return next(responses, {})

    timer_values = count()

    result = exercise_sqs_redrive.exercise_redrive(
        queue_url=queue_url,
        timeout_seconds=20,
        poll_interval_seconds=0,
        client=SequenceClient(),
        sleeper=lambda _: None,
        timer=lambda: float(next(timer_values)),
    )

    assert result == {
        "did_drain_from_source": True,
        "empty_poll_count": 2,
        "message_count": 1,
        "messages": [
            {
                "Attributes": {},
                "Body": '{"task_id": "task-redrive"}',
                "MD5OfBody": None,
                "MD5OfMessageAttributes": None,
                "MessageAttributes": {
                    "task_type": {
                        "DataType": "String",
                        "StringValue": "stage_inputs",
                    }
                },
                "MessageId": "message-1",
                "ReceiptHandle": None,
            }
        ],
        "receive_count": 1,
    }


def test_exercise_sqs_redrive_returns_false_when_source_never_receives() -> None:
    class EmptyClient:
        def receive_message(self, **kwargs: Any) -> dict[str, Any]:
            return {}

    timer_values = count()

    result = exercise_sqs_redrive.exercise_redrive(
        queue_url="https://example.invalid/queue",
        timeout_seconds=3,
        poll_interval_seconds=0,
        client=EmptyClient(),
        sleeper=lambda _: None,
        timer=lambda: float(next(timer_values)),
    )

    assert result == {
        "did_drain_from_source": False,
        "empty_poll_count": 0,
        "message_count": 0,
        "messages": [],
        "receive_count": 0,
    }


def test_exercise_sqs_redrive_stops_when_deadline_passes_after_receive() -> None:
    class OneMessageClient:
        def receive_message(self, **kwargs: Any) -> dict[str, Any]:
            return {
                "Messages": [
                    {
                        "MessageId": "message-1",
                        "Body": json.dumps({"task_id": "task-redrive"}),
                    }
                ]
            }

    timer_values = iter([0.0, 0.5, 1.0])

    result = exercise_sqs_redrive.exercise_redrive(
        queue_url="https://example.invalid/queue",
        timeout_seconds=1,
        poll_interval_seconds=1,
        client=OneMessageClient(),
        sleeper=lambda _: (_ for _ in ()).throw(AssertionError("unexpected sleep")),
        timer=lambda: next(timer_values),
    )

    assert result["did_drain_from_source"] is False
    assert result["empty_poll_count"] == 0
    assert result["message_count"] == 1
    assert result["messages"][0]["MessageId"] == "message-1"
    assert result["receive_count"] == 1
