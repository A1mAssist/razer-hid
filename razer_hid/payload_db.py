"""Payload template lookup and byte rendering."""

from __future__ import annotations

import gzip
import json
import re
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class PayloadField:
    index: int
    expression: str
    source: str
    value: Optional[int] = None


@dataclass(frozen=True)
class PayloadTemplate:
    pid: str
    command_class: int
    command_id: int
    name: Optional[str]
    data_size: int
    kind: str
    bytes: Tuple[int, ...] = ()
    length: Optional[int] = None
    argument: Optional[str] = None
    fields: Tuple[PayloadField, ...] = ()
    frames: Tuple[Tuple[int, ...], ...] = ()
    json_data: Tuple[dict, ...] = ()
    raw: Tuple[str, ...] = ()
    reason: Optional[str] = None

    def build(self, **kwargs) -> bytes:
        if self.kind == "constant":
            return bytes(self.bytes)
        if self.kind == "zero":
            return bytes(self.length or 0)
        if self.kind == "none":
            return b""
        if self.kind in {"argument", "buffer"}:
            return _as_bytes(kwargs.get(self.argument), self.length or self.data_size)
        if self.kind == "frames":
            frames = self.build_frames(**kwargs)
            if len(frames) == 1:
                return frames[0]
            raise ValueError(
                "payload is a multi-frame command; use build_frames()"
            )
        if self.kind == "push":
            return bytes(_resolve(field, kwargs) for field in self.fields)
        if self.kind == "indexed":
            length = self.length or self.data_size
            if self.fields:
                length = max(length, max(field.index for field in self.fields) + 1)
            out = bytearray(length)
            for item in self.fields:
                out[item.index] = _resolve(item, kwargs)
            return bytes(out)
        raise ValueError(f"payload kind {self.kind!r} cannot be built")

    def build_frames(self, **kwargs) -> Tuple[bytes, ...]:
        if self.kind == "frames":
            return tuple(bytes(frame) for frame in self.frames)
        return (self.build(**kwargs),)


def _as_bytes(value, length: int) -> bytes:
    if value is None:
        raise ValueError("the payload argument is required")
    if isinstance(value, int):
        return value.to_bytes(max(1, length), "little")
    data = bytes(value)
    if length and len(data) < length:
        data += bytes(length - len(data))
    return data[:length] if length else data


def _resolve(item: PayloadField, kwargs: Dict[str, object]) -> int:
    if item.value is not None:
        return item.value & 0xFF
    expression = item.expression
    if expression in kwargs:
        return int(kwargs[expression]) & 0xFF
    number = re.fullmatch(r"Number\((\w+)\)", expression)
    if number and number.group(1) in kwargs:
        return int(kwargs[number.group(1)]) & 0xFF
    member = re.fullmatch(r"(\w+)\.(\w+)\[(\d+)\]", expression)
    if member:
        base = kwargs.get(member.group(1))
        if isinstance(base, dict):
            value = base.get(member.group(2))
            if isinstance(value, (list, tuple)):
                return int(value[int(member.group(3))]) & 0xFF
    member = re.fullmatch(r"(\w+)\.(\w+)", expression)
    if member:
        base = kwargs.get(member.group(1))
        if isinstance(base, dict) and member.group(2) in base:
            return int(base[member.group(2)]) & 0xFF
    index = re.fullmatch(r"(\w+)\[(\d+)\]", expression)
    if index:
        base = kwargs.get(index.group(1))
        if isinstance(base, (list, tuple)):
            return int(base[int(index.group(2))]) & 0xFF
    # shortcut: only arithmetic/bitwise expressions are evaluated; complex JS
    # calls (Math.*, slice, ternary) must be supplied by the caller.
    return _eval_numeric(expression, kwargs) & 0xFF


def _eval_numeric(expression: str, kwargs: Dict[str, object]) -> int:
    if not re.search(r"[A-Za-z_$]", expression):
        return int(eval(expression, {"__builtins__": {}}, {}))

    def replace(match: re.Match) -> str:
        name = match.group(0)
        if name not in kwargs:
            raise ValueError(
                f"payload field {expression!r} needs argument {name!r}"
            )
        return str(int(kwargs[name]))

    substituted = re.sub(r"[A-Za-z_$][\w$]*", replace, expression)
    if not re.fullmatch(r"[0-9xXa-fA-F+\-*/%&|^()<>\s]+", substituted):
        raise ValueError(f"payload field {expression!r} is not a simple expression")
    return int(eval(substituted, {"__builtins__": {}}, {}))


class PayloadDb:
    def __init__(self, rows: Iterable[dict]):
        self._by_key: Dict[Tuple[str, int, int, str], PayloadTemplate] = {}
        self._by_triple: Dict[Tuple[str, int, int], List[PayloadTemplate]] = {}
        for row in rows:
            template = PayloadTemplate(
                pid=str(row["pid"]).upper(),
                command_class=int(row["class"]),
                command_id=int(row["command"]),
                name=row.get("name"),
                data_size=int(row.get("dataSize") or 0),
                kind=row["kind"],
                bytes=tuple(row.get("bytes") or ()),
                length=row.get("length"),
                argument=row.get("argument"),
                fields=tuple(
                    PayloadField(
                        index=int(item["index"]),
                        expression=str(item["expression"]),
                        source=str(item["source"]),
                        value=item.get("value"),
                    )
                    for item in row.get("fields") or ()
                ),
                frames=tuple(
                    tuple(int(value) for value in frame)
                    for frame in row.get("frames") or ()
                ),
                json_data=tuple(row.get("jsonData") or ()),
                raw=tuple(row.get("raw") or ()),
                reason=row.get("reason"),
            )
            key = (
                template.pid,
                template.command_class,
                template.command_id,
                template.name or "",
            )
            self._by_key.setdefault(key, template)
            self._by_triple.setdefault(
                (template.pid, template.command_class, template.command_id), []
            ).append(template)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "PayloadDb":
        if path is None:
            raw = files("razer_hid").joinpath("data/payloads.jsonl.gz").read_bytes()
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
        return sum(len(rows) for rows in self._by_triple.values())

    def for_command(
        self,
        pid: str,
        command_class: int,
        command_id: int,
        name: Optional[str] = None,
    ) -> Optional[PayloadTemplate]:
        pid = pid.upper()
        if name is not None:
            return self._by_key.get((pid, command_class, command_id, name))
        rows = self._by_triple.get((pid, command_class, command_id))
        return rows[0] if rows else None
