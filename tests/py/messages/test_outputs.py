from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from website_backend.messages import (
    CURRENT_CONTRACT_VERSION,
    OutputsMessage,
    dump_message,
    dump_message_json,
    validate_outputs_message,
)


def test_outputs_message_parses_urls_and_polling_guidance() -> None:
    nested_details = {"graph_id": "graph-123", "status": "accepted"}
    message = validate_outputs_message(
        {
            "version": CURRENT_CONTRACT_VERSION,
            "workflow_name": "example-workflow",
            "run_id": "run-123",
            "output_urls": {
                "status": "https://example.com/runs/run-123/status",
                "results": "https://example.com/runs/run-123/results",
            },
            "poll_after_seconds": 30,
            "details": nested_details,
        }
    )

    assert isinstance(message, OutputsMessage)
    assert (
        str(message.output_urls["status"]) == "https://example.com/runs/run-123/status"
    )
    assert (
        str(message.output_urls["results"])
        == "https://example.com/runs/run-123/results"
    )
    assert message.details == nested_details
    assert dump_message(message) == {
        "version": CURRENT_CONTRACT_VERSION,
        "workflow_name": "example-workflow",
        "run_id": "run-123",
        "output_urls": {
            "status": "https://example.com/runs/run-123/status",
            "results": "https://example.com/runs/run-123/results",
        },
        "poll_after_seconds": 30,
        "details": nested_details,
    }
    assert json.loads(dump_message_json(message)) == dump_message(message)


def test_outputs_message_rejects_invalid_url_values() -> None:
    with pytest.raises(ValidationError):
        validate_outputs_message(
            {
                "version": CURRENT_CONTRACT_VERSION,
                "workflow_name": "example-workflow",
                "run_id": "run-123",
                "output_urls": {"status": "not-a-url"},
                "poll_after_seconds": 30,
                "details": {},
            }
        )


def test_outputs_message_rejects_non_positive_poll_after_seconds() -> None:
    with pytest.raises(ValidationError):
        validate_outputs_message(
            {
                "version": CURRENT_CONTRACT_VERSION,
                "workflow_name": "example-workflow",
                "run_id": "run-123",
                "output_urls": {
                    "status": "https://example.com/runs/run-123/status",
                },
                "poll_after_seconds": 0,
                "details": {},
            }
        )


def test_outputs_message_rejects_wrong_scalar_types() -> None:
    with pytest.raises(ValidationError):
        validate_outputs_message(
            {
                "version": "2026-05",
                "workflow_name": "example-workflow",
                "run_id": "run-123",
                "output_urls": {
                    "status": "https://example.com/runs/run-123/status",
                },
                "poll_after_seconds": "30",
                "details": {},
            }
        )


def test_outputs_message_rejects_extra_top_level_fields() -> None:
    with pytest.raises(ValidationError):
        validate_outputs_message(
            {
                "version": CURRENT_CONTRACT_VERSION,
                "workflow_name": "example-workflow",
                "run_id": "run-123",
                "output_urls": {
                    "status": "https://example.com/runs/run-123/status",
                },
                "poll_after_seconds": 30,
                "details": {},
                "unexpected": "value",
            }
        )
