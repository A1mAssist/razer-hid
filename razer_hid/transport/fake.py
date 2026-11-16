"""Test transport that records requests and returns queued responses."""

from __future__ import annotations

from typing import List, Optional

from .base import Response, TransportError


class FakeTransport:
    def __init__(self, responses: Optional[List[Response]] = None):
        self.responses = list(responses or [])
        self.requests = []

    def exchange(
        self,
        command_class: int,
        command_id: int,
        arguments: bytes = b"",
        *,
        data_size: Optional[int] = None,
        allow_oversize: bool = False,
    ) -> Response:
        self.requests.append(
            {
                "command_class": command_class,
                "command_id": command_id,
                "arguments": arguments,
                "data_size": data_size,
                "allow_oversize": allow_oversize,
            }
        )
        if not self.responses:
            raise TransportError("fake transport has no queued response")
        return self.responses.pop(0)

    def close(self) -> None:
        return None
