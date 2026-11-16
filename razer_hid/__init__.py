"""Razer HID protocol 2.5/3.0/64 reference client."""

from .commands import Command, CommandDb
from .device import RazerDevice
from .devices import DeviceInfo, load_devices
from .payload_db import PayloadDb, PayloadField, PayloadTemplate

__all__ = [
    "Command",
    "CommandDb",
    "RazerDevice",
    "DeviceInfo",
    "load_devices",
    "PayloadDb",
    "PayloadField",
    "PayloadTemplate",
]
__version__ = "0.2.0"
