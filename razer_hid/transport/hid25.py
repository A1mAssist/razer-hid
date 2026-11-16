"""Razer protocol 2.5: one 91-byte HID feature report.

Frame layout:
  0      HID report id
  1      status (request: 0)
  2      transaction id
  3..5   echoed packet fields (request: 0)
  6      declared data size (0..80)
  7      command class
  8      command id
  9..88  arguments (80 bytes)
  89     XOR checksum over bytes 3..88 (some firmware includes byte 2)
  90     zero
"""

from __future__ import annotations

import time
from typing import Iterable, Optional, Sequence

from .base import Response, TransportError

REPORT_LENGTH = 91
ARGUMENTS_OFFSET = 9
DATA_SIZE_OFFSET = 6
CLASS_OFFSET = 7
COMMAND_OFFSET = 8
CRC_OFFSET = 89
STATUS_OFFSET = 1
TRANSACTION_OFFSET = 2
MAX_ARGUMENTS = 80

STATUS_BUSY = 0x01
STATUS_SUCCESS = 0x02


def xor_checksum(report: Sequence[int], include_transaction: bool = False) -> int:
    if len(report) != REPORT_LENGTH:
        raise ValueError(f"protocol 2.5 reports must be {REPORT_LENGTH} bytes")
    start = 2 if include_transaction else 3
    value = 0
    for byte in report[start:CRC_OFFSET]:
        value ^= int(byte) & 0xFF
    return value


def build_request(
    transaction_id: int,
    data_size: int,
    command_class: int,
    command_id: int,
    arguments: bytes = b"",
    report_id: int = 0,
    allow_oversize: bool = False,
) -> bytes:
    """Build one protocol 2.5 request.

    ``data_size`` is the wire ``data_size`` field, not necessarily
    ``len(arguments)``. Some commands (notably DPI stages) declare a smaller
    size than they send; pass ``allow_oversize=True`` for those.
    """

    if not 0 <= transaction_id <= 0xFF:
        raise ValueError("transaction id must be 0..255")
    if not 0 <= report_id <= 0xFF:
        raise ValueError("report id must be 0..255")
    if not 0 <= data_size <= MAX_ARGUMENTS:
        raise ValueError("data size must be 0..80")
    if len(arguments) > MAX_ARGUMENTS:
        raise ValueError("protocol 2.5 arguments must fit in 80 bytes")
    if not allow_oversize and len(arguments) > data_size:
        raise ValueError(
            f"{len(arguments)} argument bytes exceed declared data size {data_size}"
        )

    report = bytearray(REPORT_LENGTH)
    report[0] = report_id
    report[TRANSACTION_OFFSET] = transaction_id
    report[DATA_SIZE_OFFSET] = data_size
    report[CLASS_OFFSET] = command_class
    report[COMMAND_OFFSET] = command_id
    report[ARGUMENTS_OFFSET : ARGUMENTS_OFFSET + len(arguments)] = arguments
    report[CRC_OFFSET] = xor_checksum(report)
    return bytes(report)


def parse_response(
    raw: bytes,
    request: Optional[bytes] = None,
    *,
    accept_transaction_checksum: bool = False,
) -> Response:
    if len(raw) == REPORT_LENGTH - 1:
        raw = bytes([request[0] if request else 0]) + raw
    if len(raw) < REPORT_LENGTH:
        raise TransportError(
            f"short protocol 2.5 response: {len(raw)} bytes, expected {REPORT_LENGTH}"
        )
    raw = raw[:REPORT_LENGTH]

    data_size = raw[DATA_SIZE_OFFSET]
    if data_size > MAX_ARGUMENTS:
        raise TransportError(f"invalid protocol 2.5 data size {data_size}")

    checksum_ok = raw[CRC_OFFSET] == xor_checksum(raw)
    if not checksum_ok and accept_transaction_checksum:
        checksum_ok = raw[CRC_OFFSET] == xor_checksum(raw, include_transaction=True)

    if request is not None:
        if len(request) != REPORT_LENGTH:
            raise ValueError("request must be a 91-byte protocol 2.5 report")
        if raw[TRANSACTION_OFFSET] != request[TRANSACTION_OFFSET] and request[
            TRANSACTION_OFFSET
        ] != 0xFF:
            raise TransportError(
                f"transaction mismatch: reply 0x{raw[TRANSACTION_OFFSET]:02X}, "
                f"request 0x{request[TRANSACTION_OFFSET]:02X}"
            )
        if raw[CLASS_OFFSET] != request[CLASS_OFFSET] or raw[
            COMMAND_OFFSET
        ] != request[COMMAND_OFFSET]:
            raise TransportError(
                f"command mismatch: reply {raw[CLASS_OFFSET]:02X}:"
                f"{raw[COMMAND_OFFSET]:02X}, request {request[CLASS_OFFSET]:02X}:"
                f"{request[COMMAND_OFFSET]:02X}"
            )

    return Response(
        raw=raw,
        status=raw[STATUS_OFFSET],
        transaction_id=raw[TRANSACTION_OFFSET],
        command_class=raw[CLASS_OFFSET],
        command_id=raw[COMMAND_OFFSET],
        data_size=data_size,
        arguments=raw[ARGUMENTS_OFFSET : ARGUMENTS_OFFSET + data_size],
        checksum_ok=checksum_ok,
    )


class Hid25Transport:
    """Send protocol 2.5 frames through a hidapi-like device."""

    def __init__(
        self,
        device,
        *,
        report_id: int = 0,
        transaction_id: Optional[int] = None,
        transaction_base: int = 0,
        transaction_modulo: int = 32,
        timeout_ms: int = 1000,
        retries: int = 5,
        retry_delays: Iterable[float] = (0.010, 0.005),
        accept_transaction_checksum: bool = False,
    ):
        self.device = device
        self.report_id = report_id
        self.transaction_id = transaction_id
        self.transaction_base = transaction_base
        self.transaction_modulo = max(1, transaction_modulo)
        self.timeout_ms = timeout_ms
        self.retries = max(1, retries)
        self.retry_delays = tuple(retry_delays)
        self.accept_transaction_checksum = accept_transaction_checksum
        self._counter = 0

    def _next_transaction(self) -> int:
        if self.transaction_id is not None:
            return self.transaction_id & 0xFF
        value = self.transaction_base + (self._counter % self.transaction_modulo)
        self._counter += 1
        return value & 0xFF

    def exchange(
        self,
        command_class: int,
        command_id: int,
        arguments: bytes = b"",
        *,
        data_size: Optional[int] = None,
        allow_oversize: bool = False,
    ) -> Response:
        size = len(arguments) if data_size is None else data_size
        request = build_request(
            self._next_transaction(),
            size,
            command_class,
            command_id,
            arguments,
            self.report_id,
            allow_oversize,
        )

        last: Optional[Response] = None
        for attempt in range(self.retries):
            written = self.device.send_feature_report(request)
            if isinstance(written, int) and written < 0:
                raise TransportError("send_feature_report failed")
            raw = self.device.get_feature_report(self.report_id, REPORT_LENGTH)
            response = parse_response(
                raw,
                request,
                accept_transaction_checksum=self.accept_transaction_checksum,
            )
            if response.status == STATUS_BUSY:
                last = response
                time.sleep(self.retry_delays[min(attempt, len(self.retry_delays) - 1)])
                continue
            if response.status == STATUS_SUCCESS and response.checksum_ok:
                return response
            hint = (
                " (device may be asleep, off, or the command is unsupported in this mode)"
                if response.status == 0x04
                else ""
            )
            raise TransportError(
                f"command {command_class:02X}:{command_id:02X} returned "
                f"status 0x{response.status:02X}{hint}",
                response=response,
            )

        raise TransportError(
            f"no accepted reply for {command_class:02X}:{command_id:02X} "
            f"after {self.retries} busy attempts",
            response=last,
        )

    def close(self) -> None:
        close = getattr(self.device, "close", None)
        if close:
            close()
