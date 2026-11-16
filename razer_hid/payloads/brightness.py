"""Chroma brightness helpers (class 0x10)."""

from __future__ import annotations


def read(device) -> int:
    response = device.send_raw(0x10, 0x85, b"", data_size=1).require_ok()
    if not response.arguments:
        raise ValueError("brightness response is empty")
    return round(response.arguments[0] * 100 / 255)


def set(device, percent: int):
    if not 0 <= percent <= 100:
        raise ValueError("brightness must be 0..100")
    raw = round(percent * 255 / 100)
    return device.send_raw(0x10, 0x05, bytes([raw]), data_size=1).require_ok()
