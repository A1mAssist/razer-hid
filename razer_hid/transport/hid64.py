"""Razer protocol 64 (BlackShark V3 Pro headset).

Frame layout:
  0      HID report id (0x02)
  1      status (request: 0)
  2      transaction id (0x60)
  3..5   zero
  6      4 + argument count
  7..8   zero
  9      direction (0x80 wireless, 0x00 wired)
  10     command class
  11     subtype (request: 0, success reply: 0x01)
  12     command id (request) / argument count (reply)
  13..   arguments
  62     XOR checksum over bytes 0..61
  63     zero
"""

from __future__ import annotations

import time
from typing import Optional

from .base import Response, TransportError

REPORT_LENGTH = 64
REPORT_ID = 0x02
TRANSACTION_ID = 0x60
ARGUMENTS_OFFSET = 13
DATA_SIZE_OFFSET = 6
DIRECTION_OFFSET = 9
CLASS_OFFSET = 10
SUBTYPE_OFFSET = 11
COMMAND_OFFSET = 12
CRC_OFFSET = 62
STATUS_OFFSET = 1
TRANSACTION_OFFSET = 2

# Byte 62 is the checksum and byte 63 is unused, so a request carries at most
# 49 argument bytes even though a reply count byte could describe up to 51.
MAX_ARGUMENTS = 49
MAX_RESPONSE_ARGUMENTS = 51

STATUS_BUSY = 0x01
STATUS_SUCCESS = 0x02
STATUS_RESEND = 0x03
SUBTYPE_SUCCESS = 0x01


def xor_checksum(report: bytes) -> int:
    if len(report) < CRC_OFFSET:
        raise ValueError(f"protocol 64 reports must be at least {CRC_OFFSET} bytes")
    value = 0
    for byte in report[:CRC_OFFSET]:
        value ^= int(byte) & 0xFF
    return value


def build_request(
    command_class: int,
    command_id: int,
    arguments: bytes = b"",
    *,
    wireless: bool = True,
    transaction_id: int = TRANSACTION_ID,
    report_id: int = REPORT_ID,
) -> bytes:
    for name, value in (
        ("command class", command_class),
        ("command id", command_id),
        ("transaction id", transaction_id),
        ("report id", report_id),
    ):
        if not 0 <= value <= 0xFF:
            raise ValueError(f"{name} must be 0..255")
    if len(arguments) > MAX_ARGUMENTS:
        raise ValueError(
            f"protocol 64 arguments must fit in {MAX_ARGUMENTS} bytes"
        )

    report = bytearray(REPORT_LENGTH)
    report[0] = report_id
    report[TRANSACTION_OFFSET] = transaction_id
    report[DATA_SIZE_OFFSET] = 4 + len(arguments)
    report[DIRECTION_OFFSET] = 0x80 if wireless else 0x00
    report[CLASS_OFFSET] = command_class
    report[SUBTYPE_OFFSET] = 0x00
    report[COMMAND_OFFSET] = command_id
    report[ARGUMENTS_OFFSET : ARGUMENTS_OFFSET + len(arguments)] = arguments
    report[CRC_OFFSET] = xor_checksum(report)
    return bytes(report)


def parse_response(raw: bytes, request: Optional[bytes] = None) -> Response:
    if len(raw) == REPORT_LENGTH - 1:
        raw = bytes([request[0] if request else REPORT_ID]) + bytes(raw)
    if len(raw) < REPORT_LENGTH:
        raise TransportError(
            f"short protocol 64 response: {len(raw)} bytes, expected {REPORT_LENGTH}"
        )
    raw = bytes(raw[:REPORT_LENGTH])

    expected_report_id = request[0] if request is not None else REPORT_ID
    if raw[0] != expected_report_id:
        raise TransportError(
            f"protocol 64 report id mismatch: reply 0x{raw[0]:02X}, "
            f"expected 0x{expected_report_id:02X}"
        )

    count = raw[COMMAND_OFFSET]
    if count > MAX_RESPONSE_ARGUMENTS:
        raise TransportError(f"invalid protocol 64 argument count {count}")

    if request is not None:
        if len(request) != REPORT_LENGTH:
            raise ValueError("request must be a 64-byte protocol 64 report")
        if raw[TRANSACTION_OFFSET] != request[TRANSACTION_OFFSET]:
            raise TransportError(
                f"transaction mismatch: reply 0x{raw[TRANSACTION_OFFSET]:02X}, "
                f"request 0x{request[TRANSACTION_OFFSET]:02X}"
            )
        if raw[CLASS_OFFSET] != request[CLASS_OFFSET]:
            raise TransportError(
                f"command class mismatch: reply 0x{raw[CLASS_OFFSET]:02X}, "
                f"request 0x{request[CLASS_OFFSET]:02X}"
            )

    return Response(
        raw=raw,
        status=raw[STATUS_OFFSET],
        transaction_id=raw[TRANSACTION_OFFSET],
        command_class=raw[CLASS_OFFSET],
        command_id=request[COMMAND_OFFSET] if request is not None else 0,
        data_size=count,
        arguments=raw[ARGUMENTS_OFFSET : ARGUMENTS_OFFSET + count],
        checksum_ok=raw[CRC_OFFSET] == xor_checksum(raw),
        subtype=raw[SUBTYPE_OFFSET],
    )


class Hid64Transport:
    """Send protocol 64 frames through a hidapi-like device."""

    def __init__(
        self,
        device,
        *,
        wireless: bool = True,
        report_id: int = REPORT_ID,
        transaction_id: Optional[int] = None,
        timeout_ms: int = 1000,
        retries: int = 5,
        retry_delay: float = 0.01,
    ):
        self.device = device
        self.wireless = wireless
        self.report_id = report_id
        self.transaction_id = (
            TRANSACTION_ID if transaction_id is None else transaction_id & 0xFF
        )
        self.timeout_ms = timeout_ms
        self.retries = max(1, retries)
        self.retry_delay = retry_delay
        self._woken = False

    def _write(self, frame: bytes) -> None:
        written = self.device.write(frame)
        if isinstance(written, int) and written < 0:
            raise TransportError("HID write failed")

    def _wake(self) -> None:
        if self._woken:
            return
        for command_class, wireless in ((0x02, False), (0x2A, False), (0x2A, True)):
            self._write(
                build_request(
                    command_class,
                    0x00,
                    wireless=wireless,
                    transaction_id=self.transaction_id,
                    report_id=self.report_id,
                )
            )
            time.sleep(0.002)
        self._woken = True

    def exchange(
        self,
        command_class: int,
        command_id: int,
        arguments: bytes = b"",
        *,
        data_size: Optional[int] = None,
        allow_oversize: bool = False,
    ) -> Response:
        # data_size and allow_oversize exist for RazerDevice dispatch parity;
        # protocol 64 derives byte 6 from len(arguments).
        del data_size, allow_oversize
        self._wake()
        request = build_request(
            command_class,
            command_id,
            arguments,
            wireless=self.wireless,
            transaction_id=self.transaction_id,
            report_id=self.report_id,
        )

        last: Optional[Response] = None
        for attempt in range(self.retries):
            self._write(request)
            raw = self.device.read(REPORT_LENGTH, self.timeout_ms)
            if not raw:
                raise TransportError(
                    f"empty protocol 64 reply for {command_class:02X}:{command_id:02X}"
                )
            response = parse_response(raw, request)
            if response.status in (STATUS_BUSY, STATUS_RESEND):
                last = response
                if attempt + 1 < self.retries:
                    time.sleep(self.retry_delay)
                continue
            if response.ok:
                return response
            if response.status == STATUS_SUCCESS and not response.checksum_ok:
                raise TransportError(
                    f"command {command_class:02X}:{command_id:02X} "
                    "returned a bad checksum",
                    response=response,
                )
            raise TransportError(
                f"command {command_class:02X}:{command_id:02X} returned "
                f"status 0x{response.status:02X}, subtype 0x{response.subtype:02X}",
                response=response,
            )

        raise TransportError(
            f"no accepted protocol 64 reply for {command_class:02X}:{command_id:02X} "
            f"after {self.retries} attempts",
            response=last,
        )

    def close(self) -> None:
        close = getattr(self.device, "close", None)
        if close:
            close()
