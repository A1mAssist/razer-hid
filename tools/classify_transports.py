#!/usr/bin/env python3
"""Build the public transport table from static OpenSynapse evidence.

The output is intentionally conservative. A shared-library chunk name is not
evidence that a product uses that transport; every non-unknown row points at a
product-specific bundle, an OpenSynapse protocol class, or a documented profile.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

SNAPSHOT = "2026-11-16"
ARTIFACTS_DIR = "artifacts"
UPSTREAM_DIR = "upstream-reference"
MIDDLEWARE_DIR = "razer-mw-full-cdn"

CHANNEL_TRANSPORT = {
    "Feature91": ("hid25", 0, 91),
    "AvneraFeature65": ("avnera65", 255, 65),
    "Protocol25Feature65": ("hid25-65", 0, 65),
    "Protocol25Feature64": ("hid25-64", 0, 64),
    "Mxic64": ("mxic64", 2, 64),
    "Valkyrie64": ("valkyrie64", 2, 64),
    "Billie64": ("billie64", 2, 64),
    "Mixer053E": ("mixer053e", 9, 64),
    "DedicatedBlackShark": ("hid64", 2, 64),
    "Unsupported": ("unknown", None, None),
    "NativeDll": ("native", None, None),
    "ValkyrieT3Feature64": ("valkyrie-t3-64", 7, 64),
    "Jolie64": ("jolie64", 7, 64),
    "KrakenBase37": ("kraken37", None, 37),
}


def transport_for_device_type(device_type: str) -> str:
    if device_type in {
        "rzCamKiyo",
        "rzCamKiyoPro",
        "rzCamKiyoX",
        "rzCamKiyoProUltra",
        "rzCamKimberly",
        "AudioCamyT1",
        "AudioCamyT2",
        "rzASRock",
    }:
        return "native"
    if device_type in {
        "AudioAWKittyBLE",
        "AudioNXPDevice",
        "AudioValkyrieBle",
        "rzDevice25ValkyrieT3Ble",
    }:
        return "ble-audio"
    if device_type == "PhilipsHueMgr":
        return "external"
    if device_type.startswith("rzDevice25ValkyrieT3"):
        return "valkyrie-t3-64"
    if device_type == "rzDeviceJolie":
        return "jolie64"
    if device_type.startswith("rzDevice40HeadsetAiroha"):
        return "protocol40"
    if device_type.startswith("rzDevice40BillieT3H"):
        return "mxic64"
    if device_type.startswith("rzDevice40"):
        return "protocol40"
    if device_type.startswith("rzDevice30"):
        return "hid30"
    if device_type.startswith("AudioValkyrie"):
        return "valkyrie64"
    if device_type.startswith("AudioMxic"):
        return "mxic64"
    if (
        device_type.startswith("AudioBillie")
        or device_type.startswith("AudioBastet")
        or device_type.startswith("AudioOdessaT2Wireless")
        or device_type.startswith("AudioMabelT3C")
    ):
        return "billie64"
    if device_type.startswith("AudioAvnera"):
        return "avnera65"
    if (
        device_type.startswith("AudioKraken")
        or device_type.startswith("AudioKrystal")
        or device_type in {"AudioKittyV2Pro", "AudioLindaT3"}
    ):
        return "kraken37"
    if device_type == "AudioMixer":
        return "mixer053e"
    if device_type == "AudioCamyT3Device":
        return "hid25"
    if device_type.startswith("rzDevice25AudioCamy") or device_type.startswith(
        "rzDevice25AudioMarie"
    ):
        return "hid25-65"
    if device_type.startswith("rzDevice25Noa"):
        return "hid25-65"
    if device_type.startswith("rzDevice25"):
        return "hid25"
    if device_type in {"rzDeviceKateT2", "rzDeviceChelsea", "rzDevice25Carol"}:
        return "hid25"
    return "unknown"


def read_device_types(bundles: Path, pid: str) -> list[str]:
    directory = bundles / pid
    found: list[str] = []
    if not directory.is_dir():
        return found
    pattern = re.compile(r'useFeature\("rzDeviceType"\s*,\s*"([^"]+)"')
    for path in directory.glob("*.js"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in pattern.finditer(text):
            if match.group(1) not in found:
                found.append(match.group(1))
    return found

CURATED = {
    "0046": ("Razer Mamba Elite", "hid25", "usb", 0, 91, "protocol 2.5 default"),
    "00B8": ("Razer Viper V3 HyperSpeed", "hid25", "usb", 0, 91, "rotating transaction 0..31"),
    "028D": ("Blackwidow V4 Pro", "hid25", "usb", 0, 91, "lighting uses class 0x0F"),
    "00A4": ("Razer Mouse Dock Pro", "hid25", "usb", 0, 91, "transaction 0xE0 | sequence"),
    "054A": ("Razer Leviathan V2 X / Pokemon soundbar", "hid25", "usb", 7, 91, "transaction checksum variant"),
    "0A45": ("Razer Wolverine V3 TE", "hid25", "usb", 4, 91, "gamepad family"),
    "00E5": ("Razer Viper V4 Pro", "ble30", "ble", None, None, "BLE protocol 30; experimental"),
    "0576": ("Razer BlackShark V3 Pro", "hid64", "usb", 2, 64, "BlackShark 64-byte envelope"),
}

BLACKSHARK = {
    "0576": ("Razer BlackShark V3 Pro", "usb"),
    "0577": ("Razer BlackShark V3 Pro (2.4 GHz receiver)", "wireless"),
    "101B": ("Razer BlackShark V3 Pro (2.4 GHz dongle)", "wireless"),
    "101C": ("Razer BlackShark V3 Pro (USB)", "usb"),
}

GAMEPADS = {
    "0A45": ("Razer Wolverine V3 Tournament Edition", 4),
    "0A4C": ("Razer Wolverine V3 Pro", 4),
    "0A57": ("Razer Wolverine V3 Pro PC", 10),
    "0A5A": ("Razer Wolverine V3 TE PC", 4),
    "0A74": ("Razer Wolverine V4 Pro", 10),
    "0A7C": ("Razer Wolverine V4 Tournament Edition", 10),
}

WIRELESS_PIDS = {
    "0577",
    "101B",
    "0565",
    "0568",
    "056C",
    "0575",
    "0578",
    "0588",
    "0589",
    "0A4F",
    "0A52",
    "0A55",
    "0A56",
    "0A58",
    "101D",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_profiles(path: Path) -> dict[str, str]:
    profiles: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(
            r"\|\s*`1532:([0-9A-Fa-f]{4})`\s*\|.*\|\s*(P\d+)\s*\|\s*$",
            line,
        )
        if match:
            profiles[match.group(1).upper()] = match.group(2)
    return profiles


def parse_headset_channels(path: Path) -> dict[str, tuple[str, str]]:
    channels: dict[str, tuple[str, str]] = {}
    pattern = re.compile(
        r"\[0x([0-9A-Fa-f]{4})\]\s*=\s*new\(\"([^\"]+)\",\s*"
        r"RazerHeadsetChannel\.(\w+)\)"
    )
    for pid, device_type, channel in pattern.findall(path.read_text(encoding="utf-8")):
        channels[pid.upper()] = (device_type, channel)
    return channels


def parse_gamepads(path: Path) -> dict[str, str]:
    gamepads: dict[str, str] = {}
    pattern = re.compile(
        r"\[0x([0-9A-Fa-f]{4})\]\s*=\s*\"([^\"]+)\""
    )
    for pid, name in pattern.findall(path.read_text(encoding="utf-8")):
        gamepads[pid.upper()] = name
    return gamepads


def device_status(transport: str, confidence: str) -> str:
    if confidence == "verified":
        return "verified / 已实机验证"
    if transport in {"hid25", "hid30", "hid64"}:
        return "implemented / 已实现"
    if transport == "ble30":
        return "experimental / 实验性"
    if transport == "unknown":
        return "unknown / 未知"
    return "catalogued / 已登记"


def report_layout(row: dict) -> str:
    report_id = row.get("reportId")
    report_size = row.get("reportSize")
    if report_id is None and report_size is None:
        return "-"
    return (
        f"{report_id if report_id is not None else '-'} / "
        f"{report_size if report_size is not None else '-'}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="OpenSynapse snapshot root",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("razer_hid/data/transports.json"),
    )
    parser.add_argument(
        "--doc",
        type=Path,
        default=Path("docs/transport-table.md"),
    )
    parser.add_argument(
        "--device-doc",
        type=Path,
        default=Path("docs/device-table.md"),
    )
    args = parser.parse_args()

    root = args.root
    out11 = load_json(
        root / ARTIFACTS_DIR / UPSTREAM_DIR / MIDDLEWARE_DIR / "out11/protocols.json"
    )
    products = {str(row["pid"]).upper(): row for row in out11["products"]}

    catalog: dict[str, tuple[str, str]] = {}
    for name in ("mice", "keyboards", "laptops", "accessories"):
        path = root / f"src/OpenSynapse.Windows/Devices/RazerHid/{name}.json"
        if not path.is_file():
            continue
        for device in load_json(path).get("devices", []):
            pid = str(device.get("productId", "")).upper()
            if pid:
                catalog[pid] = (
                    name,
                    device.get("displayName") or device.get("name") or "",
                )

    profiles = parse_profiles(root / "docs/MIDDLEWARE_DEVICE_PROTOCOLS.md")
    channels = parse_headset_channels(
        root / "src/OpenSynapse.Windows/Devices/RazerHeadsetChannelCatalog.cs"
    )
    gamepads = parse_gamepads(
        root / "src/OpenSynapse.Windows/Devices/RazerGamepadService.cs"
    )
    bundles = root / ARTIFACTS_DIR / UPSTREAM_DIR / MIDDLEWARE_DIR / "bundles"
    device_types = {
        pid: read_device_types(bundles, pid) for pid in sorted(products)
    }

    rows: dict[str, dict] = {}

    def add(
        pid: str,
        name: str,
        transport: str,
        connection: str,
        confidence: str,
        evidence: list[str],
        notes: str,
        report_id: int | None = None,
        report_size: int | None = None,
        force: bool = False,
    ) -> None:
        pid = pid.upper()
        row = rows.get(pid)
        if row is not None and row["transport"] != "unknown" and not force:
            return
        rows[pid] = {
            "pid": pid,
            "name": name or (products.get(pid, {}).get("name") or ""),
            "transport": transport,
            "connection": connection,
            "confidence": confidence,
            "reportId": report_id,
            "reportSize": report_size,
            "evidence": evidence,
            "notes": notes,
        }

    # The only hardware-verified row.
    add(
        "00B8",
        products.get("00B8", {}).get("name", ""),
        "hid25",
        "usb",
        "verified",
        ["docs/hardware-validation.md", "src/OpenSynapse.Windows/Devices/Manifests/viper-184.json"],
        "00:BF wireless-link read returned status 0x02 on 2026-11-16",
        0,
        91,
    )

    for pid, (name, transport, connection, report_id, report_size, note) in CURATED.items():
        add(
            pid,
            name,
            transport,
            connection,
            "evidenced",
            ["razer_hid/data/devices.json"],
            note,
            report_id,
            report_size,
        )

    for pid, (name, connection) in BLACKSHARK.items():
        add(
            pid,
            name,
            "hid64",
            connection,
            "evidenced",
            [
                "src/OpenSynapse.Windows/Protocols/BlackSharkV3ProProtocol.cs",
                "src/OpenSynapse.Windows/Devices/RazerHeadsetChannelCatalog.cs",
            ],
            "BlackShark V3 Pro 64-byte report id 2",
            2,
            64,
            True,
        )

    add(
        "00E5",
        products.get("00E5", {}).get("name", ""),
        "ble30",
        "ble",
        "evidenced",
        ["docs/PROTOCOL30_BLE.zh-CN.md", "src/OpenSynapse.Windows/Devices/RazerHeadsetChannelCatalog.cs"],
        "BLE protocol 30; experimental async transport",
        None,
        None,
        True,
    )
    add(
        "0301",
        products.get("0301", {}).get("name", ""),
        "external",
        "unknown",
        "evidenced",
        ["docs/MIDDLEWARE_DEVICE_PROTOCOLS.md#P31"],
        "Philips Hue bridge over HTTPS, not HID",
        None,
        None,
        True,
    )
    add(
        "0A22",
        products.get("0A22", {}).get("name", ""),
        "native",
        "unknown",
        "evidenced",
        ["docs/reverse/generated/js-bundle-completeness.md"],
        "native FFI actions only; no HID sendCommand path",
        None,
        None,
        True,
    )

    # OpenRazer-backed RazerHid catalog: 91-byte feature reports unless a more
    # specific protocol below overrides the row.
    for pid, (file_name, name) in sorted(catalog.items()):
        add(
            pid,
            name,
            "hid25",
            "usb",
            "evidenced",
            [f"src/OpenSynapse.Windows/Devices/RazerHid/{file_name}.json"],
            "OpenRazer/RazerHid catalog; 91-byte feature report",
            0,
            91,
        )

    # P1-P33 documents the product-specific handler command set. It is a
    # transport hint only; the headset catalog below overrides audio channels.
    for pid, profile in sorted(profiles.items()):
        transport = "ble30" if profile == "P22" else "external" if profile == "P31" else "hid25"
        add(
            pid,
            products.get(pid, {}).get("name", ""),
            transport,
            "usb",
            "evidenced",
            [f"docs/MIDDLEWARE_DEVICE_PROTOCOLS.md#{profile}"],
            f"command profile {profile}",
            0 if transport == "hid25" else None,
            91 if transport == "hid25" else None,
        )

    # The headset catalog is the authoritative channel selector for audio PIDs.
    for pid, (device_type, channel) in sorted(channels.items()):
        transport, report_id, report_size = CHANNEL_TRANSPORT[channel]
        if pid in {"0592", "0593"}:
            transport, report_id, report_size = "protocol40", 2, 64
        if channel == "Unsupported" and "ble" in device_type.lower():
            transport = "ble-audio"
        if pid == "052D":
            transport = "ble-audio"
        connection = (
            "ble"
            if channel in {"Unsupported"} and pid in WIRELESS_PIDS
            else "wireless"
            if pid in WIRELESS_PIDS
            else "usb"
        )
        add(
            pid,
            products.get(pid, {}).get("name", ""),
            transport,
            connection,
            "evidenced",
            ["src/OpenSynapse.Windows/Devices/RazerHeadsetChannelCatalog.cs"],
            f"{device_type} channel {channel}",
            report_id,
            report_size,
            True,
        )

    # Gamepads use protocol 2.5 with report id 4, or 10 for the three 8 kHz models.
    for pid, name in sorted(gamepads.items()):
        report_id = 10 if pid in {"0A57", "0A74", "0A7C"} else 4
        add(
            pid,
            name,
            "hid25",
            "usb",
            "evidenced",
            ["src/OpenSynapse.Windows/Devices/RazerGamepadService.cs"],
            f"protocol 2.5 gamepad; report id {report_id}",
            report_id,
            91,
            True,
        )

    # Bundle self-declaration: useFeature("rzDeviceType", ...). This fills rows
    # that are not in the headset/catalog/profile tables.
    for pid, types in sorted(device_types.items()):
        if not types:
            continue
        row = rows.get(pid)
        if row is not None and row["transport"] != "unknown":
            continue
        transport = transport_for_device_type(types[0])
        if transport == "unknown":
            continue
        connection = (
            "ble"
            if transport == "ble-audio"
            else "unknown"
            if transport in {"native", "external"}
            else "wireless"
            if pid in WIRELESS_PIDS or "Wireless" in types[0]
            else "usb"
        )
        add(
            pid,
            products.get(pid, {}).get("name", ""),
            transport,
            connection,
            "family-inferred",
            [f"bundle useFeature rzDeviceType={types[0]}"],
            f"bundle declares {types[0]}",
            None,
            None,
            True,
        )

    # Every out11 product gets a row, even when no transport evidence exists.
    for pid, product in sorted(products.items()):
        if pid in rows:
            continue
        add(
            pid,
            product.get("name", ""),
            "unknown",
            "unknown",
            "unknown",
            [],
            "no product-specific transport evidence in the snapshot",
        )

    ordered = [rows[pid] for pid in sorted(rows)]
    for row in ordered:
        types = device_types.get(row["pid"], [])
        row["rzDeviceType"] = types[0] if types else None
    by_transport = Counter(row["transport"] for row in ordered)
    by_confidence = Counter(row["confidence"] for row in ordered)

    payload = {
        "schemaVersion": 1,
        "generatedFrom": {
            "snapshot": SNAPSHOT,
            "out11": "razer-mw-full-cdn/out11/protocols.json",
            "catalog": "src/OpenSynapse.Windows/Devices/RazerHid/*.json",
            "profiles": "docs/MIDDLEWARE_DEVICE_PROTOCOLS.md",
            "headsets": "src/OpenSynapse.Windows/Devices/RazerHeadsetChannelCatalog.cs",
            "gamepads": "src/OpenSynapse.Windows/Devices/RazerGamepadService.cs",
        },
        "counts": {
            "total": len(ordered),
            "byTransport": dict(sorted(by_transport.items())),
            "byConfidence": dict(sorted(by_confidence.items())),
        },
        "devices": ordered,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Transport table",
        "",
        f"Snapshot: **{SNAPSHOT}**. Rows: **{len(ordered)}**.",
        "",
        "Only `00B8` is hardware-verified. `evidenced` means an OpenSynapse",
        "protocol class, manifest, catalog entry or documented command profile",
        "names the transport. A shared-library chunk name is not evidence.",
        "",
        "## Counts",
        "",
        "| Transport | Rows |",
        "|---|---:|",
    ]
    for transport, count in sorted(by_transport.items()):
        lines.append(f"| `{transport}` | {count} |")
    lines += ["", "| Confidence | Rows |", "|---|---:|"]
    for confidence, count in sorted(by_confidence.items()):
        lines.append(f"| `{confidence}` | {count} |")
    lines += [
        "",
        "## Rows",
        "",
        "| PID | Product | Transport | Connection | Confidence | Evidence |",
        "|---|---|---|---|---|---|",
    ]
    for row in ordered:
        evidence = "; ".join(row["evidence"]).replace("|", "\\|")
        lines.append(
            f"| `{row['pid']}` | {row['name']} | `{row['transport']}` | "
            f"{row['connection']} | {row['confidence']} | {evidence} |"
        )
    lines += [
        "",
        "## Limitations",
        "",
        "- `hid64` is the BlackShark V3 Pro 64-byte report-id-2 envelope only.",
        "  `valkyrie64`, `mxic64`, `billie64`, `jolie64`, `valkyrie-t3-64`,",
        "  `kraken37`, `avnera65`, `hid25-64/65`, `mixer053e` and `protocol40`",
        "  are separate wire formats; they are named here but not implemented.",
        "- `unknown` rows have no product-specific transport evidence. They are",
        "  not silently assigned to HID 2.5 because most bundles ship the shared",
        "  `rzDevice25` library.",
        "- The command database can still be queried for every PID; transport",
        "  support and transport evidence are separate fields.",
    ]
    args.doc.parent.mkdir(parents=True, exist_ok=True)
    args.doc.write_text("\n".join(lines) + "\n", encoding="utf-8")

    device_lines = [
        "# All devices / 全部设备",
        "",
        f"Snapshot: **{SNAPSHOT}**. Rows: **{len(ordered)}**.",
        "",
        "Status is this package's implementation status; confidence is",
        "transport-evidence confidence.",
        "",
        "状态表示本包实现状态；置信度表示传输证据强度。",
        "",
        "| PID | Product / 产品 | Transport / 传输 | Connection / 连接 | Report | Status / 状态 | Confidence / 置信度 |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in ordered:
        name = (row["name"] or "-").replace("|", "\\|")
        device_lines.append(
            f"| `{row['pid']}` | {name} | `{row['transport']}` | "
            f"{row['connection']} | {report_layout(row)} | "
            f"{device_status(row['transport'], row['confidence'])} | "
            f"{row['confidence']} |"
        )
    device_lines += [
        "",
        "Evidence is in [`transport-table.md`](transport-table.md); machine-readable",
        "data is in `razer_hid/data/transports.json`.",
        "",
        "证据见 [`transport-table.md`](transport-table.md)；机器可读数据在",
        "`razer_hid/data/transports.json`。",
        "",
        "`0565` and `056E` are BlackShark V2 HyperSpeed devices on `billie64`,",
        "not the protocol 64 envelope used by `0576`, `0577`, `101B` and `101C`.",
        "",
        "`0565` 和 `056E` 是 BlackShark V2 HyperSpeed，使用 `billie64`，",
        "不是 `0576`、`0577`、`101B`、`101C` 使用的协议 64 帧。",
        "",
        "Only `00B8` has a documented hardware-verified command path; see",
        "[`hardware-validation.md`](hardware-validation.md).",
        "",
        "只有 `00B8` 有已记录的实机验证命令路径；见",
        "[`hardware-validation.md`](hardware-validation.md)。",
    ]
    args.device_doc.parent.mkdir(parents=True, exist_ok=True)
    args.device_doc.write_text("\n".join(device_lines) + "\n", encoding="utf-8")

    print(
        f"{len(ordered)} rows -> {args.out} + {args.device_doc}; "
        f"{dict(sorted(by_transport.items()))}; "
        f"{dict(sorted(by_confidence.items()))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
