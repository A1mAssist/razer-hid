"""Synchronous HID device wrapper."""

from __future__ import annotations

from typing import Optional

from .devices import DeviceInfo, VENDOR_ID, load_devices
from .transport.base import Response, TransportError, UnsupportedTransport
from .transport.hid25 import Hid25Transport
from .transport.hid30 import Hid30Transport
from .transport.hid64 import Hid64Transport


def _import_hid():
    try:
        import hid  # type: ignore
    except ImportError as error:  # pragma: no cover - depends on environment
        raise TransportError(
            "hidapi is not installed; run `pip install hidapi`"
        ) from error
    return hid


def find_hid_path(pid: str, transport: str = "hid25") -> bytes:
    hid = _import_hid()
    matches = hid.enumerate(VENDOR_ID, int(pid, 16))
    if not matches:
        raise TransportError(f"no HID device found for PID {pid}")

    if transport == "hid64":
        control = [
            item
            for item in matches
            if item.get("usage_page") in (0xFF13, 0xFF14)
            and item.get("usage") == 1
            and (item.get("output_report_length") or 0) >= 64
        ]
        if control:
            return min(
                control,
                key=lambda item: (
                    0 if item.get("usage_page") == 0xFF14 else 1,
                    item.get("interface_number")
                    if item.get("interface_number") is not None
                    else 99,
                ),
            )["path"]
        fallback = [
            item
            for item in matches
            if isinstance(item.get("interface_number"), int)
            and item["interface_number"] >= 0
        ]
        return min(
            fallback or matches,
            key=lambda item: (
                item.get("interface_number")
                if item.get("interface_number") is not None
                else 99
            ),
        )["path"]

    def score(item: dict) -> tuple:
        interface = item.get("interface_number", 99)
        return (
            0 if item.get("usage_page") == 1 and item.get("usage") == 2 else 1,
            0 if interface is not None and interface >= 0 else 1,
            interface if interface is not None else 99,
        )

    return min(matches, key=score)["path"]


class RazerDevice:
    def __init__(
        self,
        info: DeviceInfo,
        transport,
        path: Optional[bytes],
        wireless: bool = False,
    ):
        self.info = info
        self.transport = transport
        self.path = path
        self.wireless = wireless

    @classmethod
    def open(
        cls,
        pid: str,
        *,
        path: Optional[bytes] = None,
        transport: Optional[str] = None,
        report_id: Optional[int] = None,
        transaction_id: Optional[int] = None,
        timeout_ms: int = 1000,
    ) -> "RazerDevice":
        pid = pid.upper()
        info = load_devices().get(pid)
        if info is None:
            if transport is None:
                raise UnsupportedTransport(
                    f"unknown PID {pid}; pass transport='hid25', 'hid30', or 'hid64'"
                )
            info = DeviceInfo(
                pid=pid,
                product=f"PID {pid}",
                transport=transport,
                report_id=(
                    report_id
                    if report_id is not None
                    else {"hid25": 0, "hid64": 0x02}.get(transport)
                ),
                report_size={"hid25": 91, "hid64": 64}.get(transport),
                connection="unknown",
                supported=True,
            )

        name = transport or info.transport
        if not info.supported:
            raise UnsupportedTransport(
                f"{info.product} uses {info.transport}; {info.notes or 'not implemented'}"
            )

        if name not in ("hid25", "hid30", "hid64"):
            raise UnsupportedTransport(
                f"{info.product} uses {name}; {info.notes or 'not implemented'}"
            )
        if path is None:
            path = find_hid_path(pid, name)

        hid = _import_hid()
        device = hid.device()
        device.open_path(path)
        wireless = info.connection == "wireless"

        if name == "hid25":
            transport_obj = Hid25Transport(
                device,
                report_id=report_id if report_id is not None else (info.report_id or 0),
                transaction_id=(
                    transaction_id if transaction_id is not None else info.transaction_id
                ),
                transaction_base=info.transaction_base,
                transaction_modulo=info.transaction_modulo,
                timeout_ms=timeout_ms,
                accept_transaction_checksum=info.transaction_checksum,
            )
        elif name == "hid64":
            transport_obj = Hid64Transport(
                device,
                wireless=wireless,
                report_id=(
                    report_id
                    if report_id is not None
                    else (info.report_id if info.report_id is not None else 0x02)
                ),
                transaction_id=(
                    transaction_id if transaction_id is not None else info.transaction_id
                ),
                timeout_ms=timeout_ms,
            )
        else:
            effective_report_id = (
                report_id
                if report_id is not None
                else (info.report_id if info.transport == "hid30" else None)
            )
            transport_obj = Hid30Transport(
                device,
                report_id=effective_report_id,
                read_size=info.report_size or 512,
                timeout_ms=timeout_ms,
            )
        return cls(info, transport_obj, path, wireless)

    @classmethod
    def probe(cls, pid: str, timeout_ms: int = 1000) -> "RazerDevice":
        errors = []
        info = load_devices().get(pid.upper())
        candidates = []
        if info is not None and info.transport == "hid64":
            candidates.append(("hid64", 0x02))
        candidates += [
            ("hid25", 0),
            ("hid25", 2),
            ("hid25", 4),
            ("hid25", 7),
            ("hid30", None),
        ]
        for name, report_id in candidates:
            device = None
            try:
                device = cls.open(
                    pid,
                    transport=name,
                    report_id=report_id,
                    timeout_ms=timeout_ms,
                )
                probes = (
                    ((0x21, 0x00, None),)
                    if name == "hid64"
                    else ((0x00, 0xBF, 0x50), (0x00, 0x87, 4))
                )
                for command_class, command, size in probes:
                    try:
                        response = device.send_raw(
                            command_class, command, b"", data_size=size
                        )
                    except Exception as error:  # noqa: BLE001 - try the next probe
                        errors.append(f"{name}/{report_id}: {error}")
                        continue
                    if response.ok:
                        return device
                    errors.append(
                        f"{name}/{report_id}: {command_class:02X}:{command:02X} status "
                        f"0x{response.status:02X}"
                    )
                device.close()
            except Exception as error:  # noqa: BLE001 - probe reports every attempt
                errors.append(f"{name}/{report_id}: {error}")
                if device is not None:
                    device.close()
        raise TransportError(f"could not probe {pid}: " + "; ".join(errors))

    def send_raw(
        self,
        command_class: int,
        command_id: int,
        payload: bytes = b"",
        *,
        data_size: Optional[int] = None,
        allow_oversize: bool = False,
    ) -> Response:
        if isinstance(self.transport, Hid64Transport):
            return self.transport.exchange(command_class, command_id, payload)
        if isinstance(self.transport, Hid30Transport):
            return self.transport.exchange(command_class, command_id, payload)
        return self.transport.exchange(
            command_class,
            command_id,
            payload,
            data_size=data_size,
            allow_oversize=allow_oversize,
        )

    def read_raw(
        self,
        command_class: int,
        command_id: int,
        payload: bytes = b"",
        *,
        data_size: Optional[int] = None,
    ) -> Response:
        return self.send_raw(
            command_class, command_id, payload, data_size=data_size
        )

    def read_battery(self):
        if isinstance(self.transport, Hid64Transport):
            from .payloads import blackshark

            return blackshark.read_battery(self)
        from .payloads import battery

        return battery.read(self)

    def read_charging(self) -> bool:
        if isinstance(self.transport, Hid64Transport):
            from .payloads import blackshark

            return blackshark.read_charging(self)
        from .payloads import battery

        return battery.read_charging(self)

    def _blackshark(self):
        from .payloads import blackshark

        if not isinstance(self.transport, Hid64Transport):
            raise UnsupportedTransport(
                f"{self.info.product} does not use the 64-byte headset transport"
            )
        return blackshark

    def read_sidetone(self) -> int:
        return self._blackshark().get_sidetone(self)

    def set_sidetone(self, level: int):
        return self._blackshark().set_sidetone(self, level)

    def get_thx(self) -> bool:
        return self._blackshark().get_thx(self)

    def set_thx(self, enabled: bool):
        return self._blackshark().set_thx(self, enabled)

    def get_anc(self):
        return self._blackshark().get_anc(self)

    def set_anc(self, mode, level: int):
        return self._blackshark().set_anc(self, mode, level)

    def get_game_chat(self) -> int:
        return self._blackshark().get_game_chat(self)

    def set_game_chat(self, balance: int):
        return self._blackshark().set_game_chat(self, balance)

    def read_wireless_link(self):
        from .payloads import link

        return link.read(self)

    def read_polling(self) -> int:
        from .payloads import polling

        return polling.read(self)

    def set_polling(self, hertz: int):
        from .payloads import polling

        return polling.set(self, hertz)

    def read_brightness(self) -> int:
        from .payloads import brightness

        return brightness.read(self)

    def set_brightness(self, percent: int):
        from .payloads import brightness

        return brightness.set(self, percent)

    def read_dpi(self):
        from .payloads import dpi

        return dpi.read(self)

    def set_dpi(self, x: int, y: int):
        from .payloads import dpi

        return dpi.set(self, x, y)

    def get_effect(self):
        from .payloads import effect

        return effect.get(self)

    def set_effect(self, effect_id: int, colors=(), *, flags: int = 0, rate: int = 0):
        from .payloads import effect

        return effect.set(self, effect_id, colors, flags=flags, rate=rate)

    def close(self) -> None:
        self.transport.close()

    def __enter__(self) -> "RazerDevice":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
