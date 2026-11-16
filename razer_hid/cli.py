"""razerctl command line."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .commands import CommandDb
from .device import RazerDevice
from .devices import VENDOR_ID, load_devices
from .payloads import battery, brightness, dpi, effect, link, polling
from .transport.base import TransportError
from .transport.hid25 import build_request as build_request_25
from .transport.hid30 import build_request as build_request_30
from .transport.hid64 import (
    REPORT_ID as HID64_REPORT_ID,
    TRANSACTION_ID as HID64_TRANSACTION_ID,
    build_request as build_request_64,
)


def _int(value: str) -> int:
    return int(value, 0)


def _byte(value: str) -> int:
    return int(value, 0) if value.lower().startswith("0x") else int(value, 16)


def _hex(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


def cmd_list(args: argparse.Namespace) -> int:
    try:
        import hid  # type: ignore
    except ImportError:
        print("hidapi is not installed; run `pip install hidapi`", file=sys.stderr)
        return 2

    info = load_devices()
    rows = []
    for item in hid.enumerate(VENDOR_ID):
        pid = f"{item['product_id']:04X}"
        meta = info.get(pid)
        rows.append(
            {
                "pid": pid,
                "product": item.get("product_string") or (meta.product if meta else ""),
                "transport": meta.transport if meta else "unknown",
                "supported": meta.supported if meta else None,
                "path": item.get("path", b"").decode("utf-8", "replace")
                if isinstance(item.get("path"), bytes)
                else item.get("path"),
            }
        )
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            flag = "" if row["supported"] is not False else " (not implemented)"
            print(f"{row['pid']}  {row['transport']:<6}  {row['product']}{flag}")
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    device = RazerDevice.probe(args.pid, timeout_ms=args.timeout_ms)
    try:
        payload = {
            "pid": device.info.pid,
            "product": device.info.product,
            "transport": device.info.transport,
            "reportId": device.info.report_id,
            "path": device.path.decode("utf-8", "replace")
            if isinstance(device.path, bytes)
            else device.path,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    finally:
        device.close()
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    with RazerDevice.open(
        args.pid, path=args.path, timeout_ms=args.timeout_ms
    ) as device:
        if args.feature == "battery":
            value = device.read_battery()
        elif args.feature == "charging":
            value = device.read_charging()
        elif args.feature == "polling":
            value = polling.read(device)
        elif args.feature == "brightness":
            value = brightness.read(device)
        elif args.feature == "dpi":
            value = dpi.read(device)
        elif args.feature == "effect":
            value = effect.get(device)
        elif args.feature == "link":
            value = link.read(device)
        elif args.feature == "sidetone":
            value = device.read_sidetone()
        elif args.feature == "thx":
            value = device.get_thx()
        elif args.feature == "anc":
            value = device.get_anc()
        elif args.feature == "gamechat":
            value = device.get_game_chat()
        else:  # pragma: no cover - argparse prevents this
            raise ValueError(args.feature)
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


def cmd_raw(args: argparse.Namespace) -> int:
    payload = bytes.fromhex(args.payload) if args.payload else b""
    info = load_devices().get(args.pid.upper())
    transport = args.transport or (info.transport if info else "hid25")
    data_size = args.data_size
    if data_size is None:
        data_size = len(payload)
        if args.lookup:
            try:
                matches = CommandDb.load().get(args.pid, args.command_class, args.command_id)
            except FileNotFoundError:
                matches = []
            if matches:
                data_size = matches[0].data_size

    if args.dry_run:
        if transport == "hid30":
            frame = build_request_30(
                args.transaction_id or 0,
                args.command_class,
                args.command_id,
                payload,
                header6=args.header6,
                header7=args.header7,
            )
        elif transport == "hid64":
            frame = build_request_64(
                args.command_class,
                args.command_id,
                payload,
                wireless=(
                    info.connection == "wireless" if info is not None else True
                ),
                transaction_id=(
                    args.transaction_id
                    if args.transaction_id is not None
                    else (
                        info.transaction_id
                        if info and info.transaction_id is not None
                        else HID64_TRANSACTION_ID
                    )
                ),
                report_id=(
                    args.report_id
                    if args.report_id is not None
                    else (
                        info.report_id
                        if info and info.report_id is not None
                        else HID64_REPORT_ID
                    )
                ),
            )
        else:
            report_id = (
                args.report_id
                if args.report_id is not None
                else (info.report_id if info and info.report_id is not None else 0)
            )
            transaction_id = (
                args.transaction_id
                if args.transaction_id is not None
                else (
                    info.transaction_id
                    if info and info.transaction_id is not None
                    else (info.transaction_base if info else 0)
                )
            )
            frame = build_request_25(
                transaction_id,
                data_size,
                args.command_class,
                args.command_id,
                payload,
                report_id,
                allow_oversize=args.allow_oversize,
            )
        print(f"{transport} frame ({len(frame)} bytes):")
        print(_hex(frame))
        return 0

    if not args.allow_writes and not args.read:
        print(
            "raw commands require --allow-writes or --read; use --dry-run to inspect the frame",
            file=sys.stderr,
        )
        return 2

    with RazerDevice.open(
        args.pid,
        path=args.path,
        transport=args.transport,
        report_id=args.report_id,
        transaction_id=args.transaction_id,
        timeout_ms=args.timeout_ms,
    ) as device:
        response = device.send_raw(
            args.command_class,
            args.command_id,
            payload,
            data_size=data_size,
            allow_oversize=args.allow_oversize,
        )
    print(
        json.dumps(
            {
                "status": response.status,
                "ok": response.ok,
                "transactionId": response.transaction_id,
                "class": response.command_class,
                "command": response.command_id,
                "dataSize": response.data_size,
                "arguments": _hex(response.arguments),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if response.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="razerctl")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="list Razer HID devices")
    list_parser.set_defaults(func=cmd_list)

    probe = sub.add_parser("probe", help="probe a PID over protocol 2.5/3.0/64")
    probe.add_argument("pid")
    probe.add_argument("--timeout-ms", type=int, default=1000)
    probe.set_defaults(func=cmd_probe)

    read = sub.add_parser("read", help="read a typed feature")
    read.add_argument("pid")
    read.add_argument(
        "feature",
        choices=[
            "battery",
            "charging",
            "polling",
            "brightness",
            "dpi",
            "effect",
            "link",
            "sidetone",
            "thx",
            "anc",
            "gamechat",
        ],
    )
    read.add_argument("--path", default=None)
    read.add_argument("--timeout-ms", type=int, default=1000)
    read.set_defaults(func=cmd_read)

    raw = sub.add_parser("raw", help="send or inspect a raw command")
    raw.add_argument("pid")
    raw.add_argument("command_class", type=_byte)
    raw.add_argument("command_id", type=_byte)
    raw.add_argument("payload", nargs="?", default="", help="hex bytes, e.g. 00 01 FF")
    raw.add_argument("--data-size", type=_int, default=None)
    raw.add_argument(
        "--transport", choices=["hid25", "hid30", "hid64"], default=None
    )
    raw.add_argument("--report-id", type=_byte, default=None)
    raw.add_argument("--transaction-id", type=_byte, default=None)
    raw.add_argument("--header6", type=_byte, default=0)
    raw.add_argument("--header7", type=_byte, default=0)
    raw.add_argument("--path", default=None)
    raw.add_argument("--timeout-ms", type=int, default=1000)
    raw.add_argument("--allow-oversize", action="store_true")
    raw.add_argument("--allow-writes", action="store_true")
    raw.add_argument("--read", action="store_true", help="allow a read-only raw command")
    raw.add_argument("--dry-run", action="store_true")
    raw.add_argument("--no-lookup", dest="lookup", action="store_false", default=True)
    raw.set_defaults(func=cmd_raw)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (TransportError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
