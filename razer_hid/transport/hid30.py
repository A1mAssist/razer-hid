"""Razer protocol 30 framing (HID 3.0 / BLE).

Requests use an 8-byte header and no checksum:
  0     transaction id (0..31)
  1..3  payload length, 24-bit little-endian
  4     command class
  5     command id
  6..7  header selectors
  8..   payload

Replies normally use a 20-byte header with status at byte 7. An 8-byte
header is accepted when the declared length matches the shorter form.
"""

from __future__ import annotations

import time
from typing import Optional

from .base import Response, TransportError

REQUEST_HEADER_LENGTH = 8
RESPONSE_HEADER_LENGTH = 20
MAX_PAYLOAD_LENGTH = 0xFFFFFF
MAX_TRANSACTION_ID = 31
STATUS_SUCCESS = 0x02


def build_request(
    transaction_id: int,
    command_class: int,
    command_id: int,
    payload: bytes = b"",
    *,
    header6: int = 0,
    header7: int = 0,
) -> bytes:
    if not 0 <= transaction_id <= MAX_TRANSACTION_ID:
        raise ValueError("protocol 30 transaction ids are 0..31")
    if len(payload) > MAX_PAYLOAD_LENGTH:
        raise ValueError("protocol 30 payloads fit in a 24-bit length")

    frame = bytearray(REQUEST_HEADER_LENGTH + len(payload))
    frame[0] = transaction_id
    frame[1] = len(payload) & 0xFF
    frame[2] = (len(payload) >> 8) & 0xFF
    frame[3] = (len(payload) >> 16) & 0xFF
    frame[4] = command_class
    frame[5] = command_id
    frame[6] = header6
    frame[7] = header7
    frame[REQUEST_HEADER_LENGTH:] = payload
    return bytes(frame)


def parse_response(request: bytes, response: bytes) -> Response:
    if len(request) < REQUEST_HEADER_LENGTH or len(response) < REQUEST_HEADER_LENGTH:
        raise TransportError("short protocol 30 frame")

    declared = response[1] | (response[2] << 8) | (response[3] << 16)
    header_length = -1
    if (
        len(response) >= RESPONSE_HEADER_LENGTH
        and declared == len(response) - RESPONSE_HEADER_LENGTH
    ):
        header_length = RESPONSE_HEADER_LENGTH
    elif declared == len(response) - REQUEST_HEADER_LENGTH:
        header_length = REQUEST_HEADER_LENGTH
    elif len(response) >= RESPONSE_HEADER_LENGTH and declared == 0:
        header_length = RESPONSE_HEADER_LENGTH

    if header_length < 0:
        raise TransportError(
            f"protocol 30 length mismatch: declared {declared}, got {len(response)} bytes"
        )
    if response[0] != request[0]:
        raise TransportError(
            f"protocol 30 transaction mismatch: reply {response[0]}, "
            f"request {request[0]}"
        )
    if response[4] != request[4] or response[5] != request[5]:
        raise TransportError(
            f"protocol 30 command mismatch: reply {response[4]:02X}:"
            f"{response[5]:02X}, request {request[4]:02X}:{request[5]:02X}"
        )

    payload = response[header_length:]
    return Response(
        raw=response,
        status=response[7],
        transaction_id=response[0],
        command_class=response[4],
        command_id=response[5],
        data_size=len(payload),
        arguments=payload,
        checksum_ok=True,
    )


class Hid30Transport:
    """Send protocol 30 frames through a hidapi-like device.

    USB HID 3.0 framing is not hardware-verified in this release. BLE uses the
    same frame layout through :class:`razer_hid.transport.ble30.Ble30Transport`.
    """

    def __init__(
        self,
        device,
        *,
        report_id: Optional[int] = None,
        read_size: int = 512,
        timeout_ms: int = 1000,
        retries: int = 2,
        retry_delay: float = 0.03,
    ):
        self.device = device
        self.report_id = report_id
        self.read_size = read_size
        self.timeout_ms = timeout_ms
        self.retries = max(1, retries)
        self.retry_delay = retry_delay
        self._transaction = 0

    def _next_transaction(self) -> int:
        value = self._transaction % (MAX_TRANSACTION_ID + 1)
        self._transaction += 1
        return value

    def exchange(
        self,
        command_class: int,
        command_id: int,
        payload: bytes = b"",
        *,
        header6: int = 0,
        header7: int = 0,
    ) -> Response:
        request = build_request(
            self._next_transaction(),
            command_class,
            command_id,
            payload,
            header6=header6,
            header7=header7,
        )
        last: Optional[Exception] = None
        for attempt in range(self.retries):
            wire = request if self.report_id is None else bytes([self.report_id]) + request
            written = self.device.write(wire)
            if isinstance(written, int) and written < 0:
                raise TransportError("HID write failed")
            response = self.device.read(self.read_size, self.timeout_ms)
            if not response:
                last = TransportError("empty protocol 30 response")
                time.sleep(self.retry_delay)
                continue
            if self.report_id is not None and response[0] == self.report_id:
                response = response[1:]
            try:
                parsed = parse_response(request, response)
            except TransportError as error:
                last = error
                time.sleep(self.retry_delay)
                continue
            if parsed.status == STATUS_SUCCESS:
                return parsed
            last = TransportError(
                f"protocol 30 status 0x{parsed.status:02X}", response=parsed
            )
            time.sleep(self.retry_delay)
        raise TransportError(
            f"no accepted protocol 30 reply for {command_class:02X}:{command_id:02X}",
            response=getattr(last, "response", None),
        )

    def close(self) -> None:
        close = getattr(self.device, "close", None)
        if close:
            close()
