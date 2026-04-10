from __future__ import annotations

from typing import Any

from website_backend.compute import process_task_available_event


def task_available_handler(event: dict[str, Any], context: Any) -> bool:
    del context
    process_task_available_event(event)
    return True
