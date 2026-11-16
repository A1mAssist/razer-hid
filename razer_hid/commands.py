"""Command identity database."""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


def _normalize(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


@dataclass(frozen=True)
class Command:
    pid: str
    product: Optional[str]
    transport: str
    direction: str
    command_class: int
    command_id: int
    data_size: int
    name: Optional[str]
    declared: bool
    called: bool
    confidence: str
    source_layer: str
    payload_schema: Optional[str]
    library_defined: bool
    call_reference: Optional[str]
    transport_confidence: Optional[str] = None


class CommandDb:
    def __init__(self, rows: Iterable[dict]):
        self._rows: List[Command] = []
        self._by_pid: Dict[str, List[Command]] = {}
        self._by_triple: Dict[Tuple[str, int, int], List[Command]] = {}
        self._by_name: Dict[Tuple[str, str], List[Command]] = {}
        for row in rows:
            command = Command(
                pid=row["pid"],
                product=row.get("product"),
                transport=row.get("transport", "unknown"),
                direction=row.get("direction", "unknown"),
                command_class=int(row["class"]),
                command_id=int(row["command"]),
                data_size=int(row.get("dataSize", 0)),
                name=row.get("name"),
                declared=bool(row.get("declared", False)),
                called=bool(row.get("called", False)),
                confidence=row.get("confidence", "unknown"),
                source_layer=row.get("sourceLayer", "unknown"),
                payload_schema=row.get("payloadSchema"),
                library_defined=bool(row.get("libraryDefined", False)),
                call_reference=row.get("callReference"),
                transport_confidence=row.get("transportConfidence"),
            )
            self._rows.append(command)
            self._by_pid.setdefault(command.pid, []).append(command)
            self._by_triple.setdefault(
                (command.pid, command.command_class, command.command_id), []
            ).append(command)
            if command.name:
                self._by_name.setdefault(
                    (command.pid, _normalize(command.name)), []
                ).append(command)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "CommandDb":
        if path is None:
            raw = files("razer_hid").joinpath("data/commands.jsonl.gz").read_bytes()
            text = gzip.decompress(raw).decode("utf-8")
        else:
            data = Path(path).read_bytes()
            text = (
                gzip.decompress(data).decode("utf-8")
                if str(path).endswith(".gz")
                else data.decode("utf-8")
            )
        return cls(json.loads(line) for line in text.splitlines() if line.strip())

    def __len__(self) -> int:
        return len(self._rows)

    def by_pid(self, pid: str) -> List[Command]:
        return list(self._by_pid.get(pid.upper(), []))

    def get(self, pid: str, command_class: int, command_id: int) -> List[Command]:
        return list(self._by_triple.get((pid.upper(), command_class, command_id), []))

    def find(
        self,
        pid: str,
        name: Optional[str] = None,
        *,
        command_class: Optional[int] = None,
        command_id: Optional[int] = None,
    ) -> List[Command]:
        rows = self.by_pid(pid)
        if name is not None:
            key = (pid.upper(), _normalize(name))
            rows = list(self._by_name.get(key, []))
        if command_class is not None:
            rows = [row for row in rows if row.command_class == command_class]
        if command_id is not None:
            rows = [row for row in rows if row.command_id == command_id]
        return rows
