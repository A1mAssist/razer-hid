"""DPI helpers (class 0x04)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Dpi:
    x: int
    y: int


def _validate_dpi(value: int) -> None:
    if not 100 <= value <= 30000 or value % 50:
        raise ValueError("DPI must be 100..30000 and divisible by 50")


def read(device) -> Dpi:
    response = device.send_raw(0x04, 0x85, b"\x00", data_size=7).require_ok()
    args = response.arguments
    if len(args) < 5 or args[0] != 0x00:
        raise ValueError("DPI response is shorter than 5 bytes or has the wrong profile")
    x = (args[1] << 8) | args[2]
    y = (args[3] << 8) | args[4]
    _validate_dpi(x)
    _validate_dpi(y)
    return Dpi(x, y)


def set(device, x: int, y: int):
    _validate_dpi(x)
    _validate_dpi(y)
    payload = bytes([0x00, x >> 8, x & 0xFF, y >> 8, y & 0xFF])
    return device.send_raw(0x04, 0x05, payload, data_size=7).require_ok()
