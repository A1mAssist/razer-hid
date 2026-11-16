"""Experimental protocol 30 transport over BLE GATT."""

from __future__ import annotations

import asyncio
from typing import Optional

from .base import TransportError
from .hid30 import build_request, parse_response

SERVICE_UUID = "52401523-f97c-7f90-0e7f-6c6f4e36db1c"
WRITE_UUID = "52401524-f97c-7f90-0e7f-6c6f4e36db1c"
NOTIFY_UUID = "52401525-f97c-7f90-0e7f-6c6f4e36db1c"


class Ble30Transport:
    """Send protocol 30 frames to a BLE device.

    Requires ``bleak``. This class is asynchronous and is not wired into the
    synchronous :class:`razer_hid.device.RazerDevice` in v0.2.
    """

    def __init__(
        self,
        address: str,
        *,
        service_uuid: str = SERVICE_UUID,
        write_uuid: str = WRITE_UUID,
        notify_uuid: str = NOTIFY_UUID,
        timeout: float = 1.0,
    ):
        self.address = address
        self.service_uuid = service_uuid
        self.write_uuid = write_uuid
        self.notify_uuid = notify_uuid
        self.timeout = timeout
        self._client = None
        self._buffer = bytearray()
        self._event = asyncio.Event()
        self._transaction = 0

    async def connect(self) -> None:
        try:
            from bleak import BleakClient
        except ImportError as error:  # pragma: no cover - depends on optional extra
            raise TransportError("install razer-hid[ble] to use BLE") from error
        self._client = BleakClient(self.address, timeout=self.timeout)
        await self._client.connect()
        await self._client.start_notify(self.notify_uuid, self._on_notify)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None

    async def __aenter__(self) -> "Ble30Transport":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    def _on_notify(self, _sender, data: bytearray) -> None:
        self._buffer.extend(data)
        self._event.set()

    def _next_transaction(self) -> int:
        value = self._transaction % 32
        self._transaction += 1
        return value

    async def exchange(
        self,
        command_class: int,
        command_id: int,
        payload: bytes = b"",
        *,
        header6: int = 0,
        header7: int = 0,
    ):
        if self._client is None:
            raise TransportError("BLE transport is not connected")
        request = build_request(
            self._next_transaction(),
            command_class,
            command_id,
            payload,
            header6=header6,
            header7=header7,
        )
        self._buffer.clear()
        self._event.clear()
        await self._client.write_gatt_char(self.write_uuid, request, response=False)

        deadline = asyncio.get_running_loop().time() + self.timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TransportError("BLE protocol 30 response timed out")
            try:
                await asyncio.wait_for(self._event.wait(), remaining)
            except asyncio.TimeoutError as error:
                raise TransportError("BLE protocol 30 response timed out") from error
            self._event.clear()
            try:
                parsed = parse_response(request, bytes(self._buffer))
            except TransportError:
                continue
            if parsed.status == 0x02:
                return parsed
            raise TransportError(
                f"BLE protocol 30 status 0x{parsed.status:02X}", response=parsed
            )
