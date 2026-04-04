from __future__ import annotations

from website_backend.queues import InMemoryQueue


class TestInMemoryQueue:
    def test_get_message_returns_none_when_empty(self) -> None:
        queue = InMemoryQueue()

        assert queue.get_message() is None

    def test_get_message_hides_received_message_until_completed(
        self, task_message
    ) -> None:
        queue = InMemoryQueue()
        queue.add_message(task_message)

        delivery = queue.get_message()

        assert delivery is not None
        assert delivery.message == task_message
        assert queue.get_message() is None

    def test_mark_message_completed_removes_message(self, task_message) -> None:
        queue = InMemoryQueue()
        queue.add_message(task_message)

        delivery = queue.get_message()

        assert delivery is not None
        queue.mark_message_completed(delivery)
        assert queue.get_message() is None

    def test_get_message_requeues_uncompleted_message_after_visibility_timeout(
        self, task_message
    ) -> None:
        now = 100.0

        def timer() -> float:
            return now

        queue = InMemoryQueue(visibility_timeout_seconds=5.0, timer=timer)
        queue.add_message(task_message)

        delivery = queue.get_message()

        assert delivery is not None
        assert queue.get_message() is None

        now = 106.0

        next_delivery = queue.get_message()

        assert next_delivery is not None
        assert next_delivery.message == task_message
