from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from website_backend.messages import (
    dump_message,
    dump_message_json,
    validate_task_message,
)


def test_task_message_accepts_opaque_nested_details_and_round_trips() -> None:
    nested_details = {
        "ligands": ["CCO", "CCC"],
        "metadata": {
            "urls": ["https://example.com/a", "https://example.com/b"],
            "flags": {"dry_run": False},
        },
    }
    message = validate_task_message(
        {
            "version": "2026-05",
            "task_type": "openfe_ligand_network",
            "task_id": "task-2",
            "attempt": 1,
            "graph_id": "run-123",
            "task_details": nested_details,
        }
    )

    assert message.task_details == nested_details
    assert dump_message(message) == {
        "version": "2026-05",
        "task_type": "openfe_ligand_network",
        "task_id": "task-2",
        "attempt": 1,
        "graph_id": "run-123",
        "task_details": nested_details,
    }
    assert json.loads(dump_message_json(message)) == dump_message(message)


def test_task_message_rejects_non_positive_attempt() -> None:
    with pytest.raises(ValidationError):
        validate_task_message(
            {
                "version": "2026-05",
                "task_type": "openfe_ligand_network",
                "task_id": "task-2",
                "attempt": 0,
                "graph_id": "run-123",
                "task_details": {},
            }
        )


def test_task_message_rejects_wrong_scalar_types() -> None:
    with pytest.raises(ValidationError):
        validate_task_message(
            {
                "version": "2026-05",
                "task_type": "openfe_ligand_network",
                "task_id": "task-2",
                "attempt": "1",
                "graph_id": "run-123",
                "task_details": {},
            }
        )


def test_task_message_rejects_extra_top_level_fields() -> None:
    with pytest.raises(ValidationError):
        validate_task_message(
            {
                "version": "2026-05",
                "task_type": "openfe_ligand_network",
                "task_id": "task-2",
                "attempt": 1,
                "graph_id": "run-123",
                "task_details": {},
                "unexpected": "value",
            }
        )
