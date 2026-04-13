from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Mapping, Protocol

from website_backend.queues.types import MessageT


@dataclass(frozen=True, slots=True)
class QueueDelivery(Generic[MessageT]):
    """A received queue message plus transport-specific delivery state.

    Parameters
    ----------
    message : MessageT
        Decoded message object returned by the queue adapter.
    ack_token : str
        Transport-specific token used to acknowledge successful processing.
    attributes : Mapping[str, Any]
        Provider-specific system attributes returned with the delivery.
    message_attributes : Mapping[str, Any]
        Provider-specific message attributes returned with the delivery.
    message_id : str or None, default=None
        Provider-specific message identifier, when available.
    raw_body : str or None, default=None
        Raw serialized queue body before decoding, when available.
    """

    message: MessageT
    ack_token: str
    attributes: Mapping[str, Any]
    message_attributes: Mapping[str, Any]
    message_id: str | None = None
    raw_body: str | None = None


class InputQueue(Protocol[MessageT]):
    """Protocol for a queue that hides messages until they are completed."""

    def get_message(self) -> QueueDelivery[MessageT] | None:
        """Return one delivery from the queue.

        Returns
        -------
        QueueDelivery[MessageT] or None
            The next available delivery, or `None` if the queue is empty.
        """

    def mark_message_completed(self, delivery: QueueDelivery[MessageT]) -> None:
        """Acknowledge a delivery so it is removed from the queue.

        Parameters
        ----------
        delivery : QueueDelivery[MessageT]
            Delivery previously returned by `get_message`.
        """


class OutputQueue(Protocol[MessageT]):
    """Protocol for a queue/topic that accepts canonical message payloads."""

    def add_message(self, message: MessageT) -> None:
        """Enqueue or publish one message.

        Parameters
        ----------
        message : MessageT
            Message object to serialize and send through the transport.
        """
