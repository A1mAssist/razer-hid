"""BlackShark V3 Pro headset controls (protocol 64)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from .battery import BatteryStatus

SIDETONE_CLASS = 0x99
THX_CLASS = 0x9E
ANC_CLASS = 0x92
GAME_CHAT_CLASS = 0xDC


class AncMode(IntEnum):
    OFF = 0x00
    ANC = 0x01
    AMBIENT = 0x50


@dataclass(frozen=True)
class AncStatus:
    mode: AncMode
    level: int


def _value(device, command_class: int, command_id: int) -> int:
    response = device.send_raw(command_class, command_id, b"").require_ok()
    if not response.arguments:
        raise ValueError(
            f"BlackShark response {command_class:02X}:{command_id:02X} is empty"
        )
    return response.arguments[0]


def read_battery(device) -> BatteryStatus:
    response = device.send_raw(0x21, 0x00, b"").require_ok()
    if not response.arguments:
        raise ValueError("BlackShark battery response is empty")
    # The service uses Arguments[0] directly as the percent; there is no scaling.
    return BatteryStatus(percent=response.arguments[0], raw=response.arguments)


def read_charging(device) -> bool:
    return _value(device, 0x2A, 0x00) != 0


def get_sidetone(device) -> int:
    return _value(device, 0x19, 0x00)


def set_sidetone(device, level: int):
    if not 0 <= level <= 15:
        raise ValueError("BlackShark sidetone level must be 0..15")
    return device.send_raw(SIDETONE_CLASS, 0x01, bytes([level])).require_ok()


def get_thx(device) -> bool:
    return _value(device, 0x1E, 0x00) != 0


def set_thx(device, enabled: bool):
    return device.send_raw(
        THX_CLASS, 0x01, bytes([1 if enabled else 0])
    ).require_ok()


def get_anc(device) -> AncStatus:
    response = device.send_raw(0x12, 0x00, b"").require_ok()
    if len(response.arguments) < 2:
        raise ValueError("BlackShark ANC response is shorter than 2 bytes")
    try:
        mode = AncMode(response.arguments[0])
    except ValueError as error:
        raise ValueError(
            f"unknown BlackShark ANC mode 0x{response.arguments[0]:02X}"
        ) from error
    return AncStatus(mode=mode, level=response.arguments[1])


def set_anc(device, mode, level: int):
    try:
        mode = AncMode(mode)
    except ValueError as error:
        raise ValueError(f"unknown BlackShark ANC mode {mode!r}") from error

    if mode is AncMode.ANC:
        level = max(1, min(4, level))
    elif mode is AncMode.AMBIENT:
        level = 1
    else:
        level = 0
    return device.send_raw(
        ANC_CLASS, 0x02, bytes([int(mode), level])
    ).require_ok()


def get_game_chat(device) -> int:
    wire = _value(device, 0x5C, 0x00)
    return 20 - min(wire, 20)


def set_game_chat(device, balance: int):
    if not 0 <= balance <= 20:
        raise ValueError("BlackShark game/chat balance must be 0..20")
    return device.send_raw(
        GAME_CHAT_CLASS, 0x01, bytes([20 - balance])
    ).require_ok()
