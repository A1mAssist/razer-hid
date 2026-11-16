"""Chroma effect helpers (class 0x10)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple


@dataclass(frozen=True)
class EffectState:
    effect: int
    flags: int
    rate: int
    colors: Tuple[Tuple[int, int, int], ...]


def get(device) -> EffectState:
    response = device.send_raw(0x10, 0x83, b"", data_size=0).require_ok()
    args = response.arguments
    if len(args) < 4:
        raise ValueError("effect response is shorter than 4 bytes")
    count = args[3]
    if count > 2 or len(args) < 4 + count * 3:
        raise ValueError("effect response declares more than two colors")
    colors = tuple(
        (args[4 + index * 3], args[5 + index * 3], args[6 + index * 3])
        for index in range(count)
    )
    return EffectState(effect=args[0], flags=args[1], rate=args[2], colors=colors)


def set(
    device,
    effect: int,
    colors: Iterable[Tuple[int, int, int]] = (),
    *,
    flags: int = 0,
    rate: int = 0,
):
    color_list = list(colors)
    if len(color_list) > 2:
        raise ValueError("Chroma effects take at most two RGB colors")
    flat = []
    for color in color_list:
        if len(color) != 3:
            raise ValueError("each color must be an (r, g, b) triple")
        flat.extend(color)
    args = bytes([effect, flags, rate, len(color_list)] + flat)
    return device.send_raw(0x10, 0x03, args, data_size=len(args)).require_ok()
