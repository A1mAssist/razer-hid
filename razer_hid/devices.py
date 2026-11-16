"""Curated device transport table."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Dict, Optional, Tuple

VENDOR_ID = 0x1532


@dataclass(frozen=True)
class DeviceInfo:
    pid: str
    product: str
    transport: str
    report_id: Optional[int]
    report_size: Optional[int]
    connection: str
    transaction_id: Optional[int] = None
    transaction_base: int = 0
    transaction_modulo: int = 32
    transaction_checksum: bool = False
    supported: bool = True
    verified: bool = False
    notes: Optional[str] = None
    evidence: Tuple[str, ...] = ()
    confidence: str = "unknown"
    device_type: Optional[str] = None


def load_transports() -> Dict[str, dict]:
    path = files("razer_hid").joinpath("data/transports.json")
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text("utf-8"))
    return {row["pid"].upper(): row for row in raw.get("devices", [])}


def load_devices() -> Dict[str, DeviceInfo]:
    raw = json.loads(files("razer_hid").joinpath("data/devices.json").read_text("utf-8"))
    transports = load_transports()
    out: Dict[str, DeviceInfo] = {}
    for row in raw.get("devices", []):
        pid = row["pid"].upper()
        transport = transports.get(pid, {})
        out[pid] = DeviceInfo(
            pid=pid,
            product=row.get("product", ""),
            transport=row.get("transport") or transport.get("transport", "unknown"),
            report_id=row.get("reportId", transport.get("reportId")),
            report_size=row.get("reportSize", transport.get("reportSize")),
            connection=row.get("connection") or transport.get("connection", "unknown"),
            transaction_id=row.get("transactionId"),
            transaction_base=row.get("transactionBase", 0),
            transaction_modulo=row.get("transactionModulo", 32),
            transaction_checksum=row.get("transactionChecksum", False),
            supported=row.get("supported", True),
            verified=row.get("verified", False),
            notes=row.get("notes"),
            evidence=tuple(row.get("evidence", transport.get("evidence", []))),
            confidence=transport.get(
                "confidence", "verified" if row.get("verified") else "evidenced"
            ),
            device_type=transport.get("rzDeviceType"),
        )
    for pid, row in transports.items():
        if pid in out:
            continue
        transport = row.get("transport", "unknown")
        out[pid] = DeviceInfo(
            pid=pid,
            product=row.get("name", ""),
            transport=transport,
            report_id=row.get("reportId"),
            report_size=row.get("reportSize"),
            connection=row.get("connection", "unknown"),
            supported=(
                transport in {"hid25", "hid30", "hid64"}
                and row.get("confidence") in {"verified", "evidenced"}
            ),
            verified=row.get("confidence") == "verified",
            notes=row.get("notes"),
            evidence=tuple(row.get("evidence", [])),
            confidence=row.get("confidence", "unknown"),
            device_type=row.get("rzDeviceType"),
        )
    return out
