from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from website_backend.messages import (
    CURRENT_CONTRACT_VERSION,
    InputsMessage,
    dump_message,
    dump_message_json,
    validate_inputs_message,
)


def test_inputs_message_parses_opaque_nested_details() -> None:
    nested_details = {
        "input_urls": {
            "manifest": "s3://example-bucket/runs/run-123/input.json",
        },
        "metadata": {"submitted_by": "integration-test"},
    }
    message = validate_inputs_message(
        {
            "version": CURRENT_CONTRACT_VERSION,
            "workflow_name": "example-workflow",
            "run_id": "run-123",
            "details": nested_details,
        }
    )

    assert isinstance(message, InputsMessage)
    assert message.details == nested_details
    assert dump_message(message) == {
        "version": CURRENT_CONTRACT_VERSION,
        "workflow_name": "example-workflow",
        "run_id": "run-123",
        "details": nested_details,
    }
    assert json.loads(dump_message_json(message)) == dump_message(message)


def test_inputs_message_rejects_missing_required_fields() -> None:
    with pytest.raises(ValidationError):
        validate_inputs_message(
            {
                "version": CURRENT_CONTRACT_VERSION,
                "details": {},
            }
        )


def test_inputs_message_rejects_extra_top_level_fields() -> None:
    with pytest.raises(ValidationError):
        validate_inputs_message(
            {
                "version": CURRENT_CONTRACT_VERSION,
                "workflow_name": "example-workflow",
                "run_id": "run-123",
                "details": {},
                "unexpected": "value",
            }
        )
