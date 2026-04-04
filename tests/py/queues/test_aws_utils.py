from __future__ import annotations

from website_backend.queues.aws_utils import derive_message_attributes


def test_derive_message_attributes_includes_known_top_level_task_fields(
    task_message,
) -> None:
    assert derive_message_attributes(task_message) == {
        "task_type": {"DataType": "String", "StringValue": "prepare_inputs"},
        "version": {"DataType": "String", "StringValue": "2026-05"},
    }


def test_derive_message_attributes_includes_message_type_when_present(
    orchestration_message,
) -> None:
    assert derive_message_attributes(orchestration_message) == {
        "message_type": {"DataType": "String", "StringValue": "ADD_TASKS"},
        "version": {"DataType": "String", "StringValue": "2026-05"},
    }


def test_derive_message_attributes_omits_absent_fields(inputs_message) -> None:
    assert derive_message_attributes(inputs_message) == {
        "version": {"DataType": "String", "StringValue": "2026-05"},
    }
