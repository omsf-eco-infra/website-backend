from __future__ import annotations

import queue
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic

from website_backend.queues.protocols import InputQueue, OutputQueue, QueueDelivery
from website_backend.queues.types import MessageT


@dataclass(slots=True)
class _InFlightDelivery(Generic[MessageT]):
    """Internal record for a message currently hidden from other consumers.

    Parameters
    ----------
    message : MessageT
        Message currently held in flight.
    available_at : float or None
        Monotonic timestamp after which the message becomes visible again, or
        `None` when the message should stay hidden until acknowledged.
    """

    message: MessageT
    available_at: float | None


class InMemoryQueue(InputQueue[MessageT], OutputQueue[MessageT]):
    """In-memory queue adapter with optional visibility-timeout semantics.

    Parameters
    ----------
    visibility_timeout_seconds : float or None, default=None
        Duration that a received but unacknowledged message stays hidden before
        becoming visible again. When `None`, messages remain hidden until
        acknowledged.
    timer : Callable[[], float], default=time.monotonic
        Monotonic clock used to compute visibility timeout expiry.
    """

    def __init__(
        self,
        *,
        visibility_timeout_seconds: float | None = None,
        timer: Callable[[], float] = time.monotonic,
    ) -> None:
        self.available: queue.Queue[MessageT] = queue.Queue()
        self.in_flight: dict[str, _InFlightDelivery[MessageT]] = {}
        self.visibility_timeout_seconds = visibility_timeout_seconds
        self.timer = timer

    def add_message(self, message: MessageT) -> None:
        self.available.put(message)

    def get_message(self) -> QueueDelivery[MessageT] | None:
        self._requeue_expired_deliveries()
        try:
            message = self.available.get_nowait()
        except queue.Empty:
            return None

        ack_token = uuid.uuid4().hex
        available_at = None
        if self.visibility_timeout_seconds is not None:
            available_at = self.timer() + self.visibility_timeout_seconds
        self.in_flight[ack_token] = _InFlightDelivery(
            message=message,
            available_at=available_at,
        )
        return QueueDelivery(
            message=message,
            ack_token=ack_token,
            message_id=None,
            attributes={},
            message_attributes={},
            raw_body=None,
        )

    def mark_message_completed(self, delivery: QueueDelivery[MessageT]) -> None:
        if not delivery.ack_token:
            raise ValueError("Queue delivery is missing an ack token")
        if delivery.ack_token not in self.in_flight:
            raise KeyError(delivery.ack_token)
        del self.in_flight[delivery.ack_token]

    def _requeue_expired_deliveries(self) -> None:
        """Move expired in-flight messages back to the visible queue."""
        if self.visibility_timeout_seconds is None:
            return

        now = self.timer()
        expired_tokens = [
            ack_token
            for ack_token, delivery in self.in_flight.items()
            if delivery.available_at is not None and delivery.available_at <= now
        ]
        for ack_token in expired_tokens:
            delivery = self.in_flight.pop(ack_token)
            self.available.put(delivery.message)
