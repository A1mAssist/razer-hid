#!/usr/bin/env python3
"""Export the public command identity table from out11.

Only protocol facts are written: no payload expressions, no jsonData
accessors, no local evidence paths, no implementation status.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


def infer_direction(name: str | None) -> str:
    if not name:
        return "unknown"
    lowered = name.lower()
    if lowered.startswith("get "):
        return "read"
    if lowered.startswith("set "):
        return "write"
    return "unknown"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_devices(path: Path | None) -> dict:
    if not path:
        return {}
    data = load_json(path)
    return {row["pid"].upper(): row for row in data.get("devices", [])}


def load_transports(path: Path | None) -> dict:
    return load_devices(path)


def load_payload_schemas(path: Path | None) -> dict:
    schemas = {}
    if not path:
        return schemas
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            key = (row["pid"], row["class"], row["command"], row.get("name"))
            if row.get("payloadSchema"):
                schemas[key] = row["payloadSchema"]
    return schemas


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out11", type=Path, required=True)
    parser.add_argument("--facts", type=Path, default=None)
    parser.add_argument("--devices", type=Path, default=Path("razer_hid/data/devices.json"))
    parser.add_argument(
        "--transports",
        type=Path,
        default=Path("razer_hid/data/transports.json"),
    )
    parser.add_argument("--out-dir", type=Path, default=Path("razer_hid/data"))
    args = parser.parse_args()

    data = load_json(args.out11)
    devices = load_devices(args.devices if args.devices.exists() else None)
    transports = load_transports(
        args.transports if args.transports.exists() else None
    )
    payload_schemas = load_payload_schemas(
        args.facts if args.facts and args.facts.exists() else None
    )

    rows: dict[tuple, dict] = {}
    data_sizes: dict[tuple, set] = defaultdict(set)

    def ensure(pid: str, product: str | None, command: dict) -> dict:
        key = (
            pid,
            int(command["commandClass"]),
            int(command["commandId"]),
            command.get("name"),
        )
        row = rows.get(key)
        if row is None:
            row = {
                "pid": pid,
                "product": product,
                "transport": (
                    transports.get(pid, {}).get("transport")
                    or devices.get(pid, {}).get("transport", "unknown")
                ),
                "transportConfidence": transports.get(pid, {}).get(
                    "confidence", "unknown"
                ),
                "direction": infer_direction(command.get("name")),
                "class": int(command["commandClass"]),
                "command": int(command["commandId"]),
                "dataSize": int(command.get("dataSize") or 0),
                "name": command.get("name"),
                "declared": False,
                "called": False,
                "confidence": "inferred",
                "sourceLayer": "out11",
                "payloadSchema": payload_schemas.get(key),
                "libraryDefined": False,
                "callReference": None,
                "sourceBundle": None,
            }
            rows[key] = row
        data_sizes[key].add(int(command.get("dataSize") or 0))
        return row

    for product in data.get("products", []):
        pid = str(product.get("pid"))
        product_name = product.get("name")
        for command in product.get("definedCommands") or []:
            row = ensure(pid, product_name, command)
            row["declared"] = True
            row["confidence"] = "source-backed"
            if command.get("source"):
                row["sourceBundle"] = command["source"]
        for command in product.get("usedCommands") or []:
            row = ensure(pid, product_name, command)
            row["called"] = True
            row["libraryDefined"] = bool(command.get("definedInLibrary"))
            reference = command.get("reference")
            row["callReference"] = reference
            if reference in ("interpreter-sendCommand", "direct-sendCommand"):
                row["confidence"] = "source-backed"
            elif row["confidence"] != "source-backed":
                row["confidence"] = "inferred"

    output = []
    for key, row in rows.items():
        variants = sorted(value for value in data_sizes[key] if value > 0)
        if len(variants) > 1:
            row["dataSizeVariants"] = variants
        output.append(row)
    output.sort(
        key=lambda row: (
            row["pid"],
            row["class"],
            row["command"],
            row["name"] or "",
        )
    )

    forbidden = {"payload", "jsonData", "evidence", "implemented", "methods", "referencedIn"}
    for row in output:
        extra = forbidden.intersection(row)
        if extra:
            raise SystemExit(f"refusing to publish forbidden fields: {sorted(extra)}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    target = args.out_dir / "commands.jsonl.gz"
    with gzip.open(target, "wt", encoding="utf-8", newline="\n") as handle:
        for row in output:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    by_pid = Counter(row["pid"] for row in output)
    by_transport = Counter(row["transport"] for row in output)
    by_direction = Counter(row["direction"] for row in output)
    index = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "snapshot": "2026-11-16",
            "out11": "razer-mw-full-cdn/out11/protocols.json",
            "facts": "protocol_facts.jsonl" if args.facts and args.facts.exists() else None,
        },
        "total": len(output),
        "declared": sum(1 for row in output if row["declared"]),
        "called": sum(1 for row in output if row["called"]),
        "byPid": dict(sorted(by_pid.items())),
        "byTransport": dict(sorted(by_transport.items())),
        "byDirection": dict(sorted(by_direction.items())),
    }
    (args.out_dir / "commands.index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"{len(output)} facts, {len(by_pid)} PIDs, "
        f"{target.stat().st_size / (1024 * 1024):.2f} MiB -> {target}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
