"""Time-gated access to the input requests."""

from __future__ import annotations

from collections.abc import Iterable

from elevator_sim.models import Request


class RequestStream:
    """Releases requests only once the clock reaches their time.

    This is the only path from input to simulation, and it enforces the
    no-peek rule: there is no way to see a request before ``pop_until``
    returns it. There is no peek, no next-time accessor, no iteration and no
    count of what remains.
    """

    def __init__(self, requests: Iterable[Request]) -> None:
        # sorted() builds a new list, so later changes to the caller's list
        # don't affect the stream. Requests are frozen, so a shallow copy is enough.
        self._requests: list[Request] = sorted(
            requests, key=lambda r: (r.time, r.input_order)
        )
        self._next = 0  # index of the first request not yet returned

    def pop_until(self, t: int) -> list[Request]:
        """Return, in order, every not-yet-returned request with ``time <= t``.

        A request is never returned twice. Calling again with the same or an
        earlier ``t`` returns an empty list.
        """
        start = self._next
        while self._next < len(self._requests) and self._requests[self._next].time <= t:
            self._next += 1
        return self._requests[start:self._next]

    @property
    def exhausted(self) -> bool:
        """True once every request has been returned."""
        return self._next == len(self._requests)

    @property
    def total(self) -> int:
        """Count of all requests. Reveals nothing about future times or floors."""
        return len(self._requests)
