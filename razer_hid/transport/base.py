"""Shared transport types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class TransportError(Exception):
    """A frame could not be built, sent, or accepted by the device."""

    def __init__(self, message: str, response: Optional["Response"] = None):
        super().__init__(message)
        self.response = response


class UnsupportedTransport(TransportError):
    """The device uses a transport this release does not implement."""


@dataclass(frozen=True)
class Response:
    raw: bytes
    status: int
    transaction_id: int
    command_class: int
    command_id: int
    data_size: int
    arguments: bytes
    checksum_ok: bool = True
    subtype: int = 1

    @property
    def ok(self) -> bool:
        return self.status == 0x02 and self.checksum_ok and self.subtype == 0x01

    def require_ok(self) -> "Response":
        if not self.ok:
            raise TransportError(
                f"command {self.command_class:02X}:{self.command_id:02X} "
                f"returned status 0x{self.status:02X}",
                response=self,
            )
        return self
