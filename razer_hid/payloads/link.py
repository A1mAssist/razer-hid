"""Wireless link status (class 0x00, command 0xBF)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WirelessLinkStatus:
    raw: bytes


def read(device) -> WirelessLinkStatus:
    response = device.send_raw(0x00, 0xBF, b"", data_size=0x50).require_ok()
    return WirelessLinkStatus(raw=response.arguments)
