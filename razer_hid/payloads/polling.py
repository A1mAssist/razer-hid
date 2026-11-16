"""Polling-rate helpers (class 0x00)."""

from __future__ import annotations

RATES = {
    0x01: 1000,
    0x02: 500,
    0x03: 333,
    0x04: 250,
    0x05: 200,
    0x08: 125,
    0x0A: 100,
}
CODES = {rate: code for code, rate in RATES.items()}


def read(device) -> int:
    response = device.send_raw(0x00, 0x85, b"", data_size=1).require_ok()
    if not response.arguments:
        raise ValueError("polling response is empty")
    return RATES.get(response.arguments[0], response.arguments[0])


def set(device, hertz: int):
    if hertz not in CODES:
        raise ValueError(
            "polling rate must be one of " + ", ".join(str(rate) for rate in sorted(CODES))
        )
    return device.send_raw(
        0x00, 0x05, bytes([CODES[hertz]]), data_size=1
    ).require_ok()
