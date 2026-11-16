"""Battery and charging helpers (class 0x07)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BatteryStatus:
    percent: int
    raw: bytes


def read(device) -> BatteryStatus:
    response = device.send_raw(0x07, 0x80, b"", data_size=2).require_ok()
    if len(response.arguments) < 2:
        raise ValueError("battery response is shorter than 2 bytes")
    return BatteryStatus(percent=response.arguments[1] * 100 // 255, raw=response.arguments)


def read_charging(device) -> bool:
    response = device.send_raw(0x07, 0x84, b"", data_size=2).require_ok()
    if len(response.arguments) < 2:
        raise ValueError("charging response is shorter than 2 bytes")
    return response.arguments[1] != 0
