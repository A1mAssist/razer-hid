#!/usr/bin/env python3
"""Compile extracted payload expressions into public, normalized templates.

The input is the local OpenSynapse fact/out11 snapshot plus its bundle tree.
The output contains short protocol expressions or literal frames only: no
vendor JavaScript, bundle names or local paths. A small expression interpreter
folds constants, resolves literal module-export frames, and keeps unknown
arguments symbolic.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ASSIGN = re.compile(
    r"^([A-Za-z_$][\w$]*)\s*\[\s*(\d+)\s*\]\s*=\s*(.+)$", re.S
)
PUSH = re.compile(r"^([A-Za-z_$][\w$]*)\s*\.\s*push\s*\((.*)\)$", re.S)
NEW_ARRAY = re.compile(
    r"^new\s+Uint8Array\s*\(\s*\[(.*)\]\s*\)$", re.S
)
NEW_LENGTH = re.compile(r"^new\s+Uint8Array\s*\(\s*(\d+)\s*\)$", re.S)
NEW_NAME = re.compile(
    r"^new\s+Uint8Array\s*\(\s*([A-Za-z_$][\w$]*)\s*\)$", re.S
)
DOTTED_NAME = re.compile(
    r"^[A-Za-z_$][\w$]*\.[A-Za-z_$][\w$]*$"
)
ASSIGN_BUFFER = re.compile(
    r"^([A-Za-z_$][\w$]*)\s*=\s*new\s+Uint8Array\s*\(\s*(\d+)\s*\)$", re.S
)
ASSIGN_VALUES = re.compile(
    r"^([A-Za-z_$][\w$]*)\s*=\s*new\s+Uint8Array\s*\(\s*\[(.*)\]\s*\)$", re.S
)
LENGTH = re.compile(r"^([A-Za-z_$][\w$]*)\s*\.\s*length$", re.S)
NUMBER = re.compile(r"^(?:0x[0-9A-Fa-f]+|\d+)$")
NAME = re.compile(r"^[A-Za-z_$][\w$]*$")
FRAME_ARRAY = re.compile(
    r"(?:^|[;,\n])\s*(?:const\s+)?([A-Za-z_$][\w$]*)\s*=\s*\["
    r"((?:new\s+Uint8Array\s*\(\s*\[[0-9,\s]*\]\s*\)\s*,?)+)\]"
)
FRAME_VALUE = re.compile(
    r"new\s+Uint8Array\s*\(\s*\[([0-9,\s]*)\]\s*\)"
)
EXPORT_MAP = re.compile(
    r"([A-Za-z_$][\w$]*):\(\)=>([A-Za-z_$][\w$]*)"
)


@dataclass(frozen=True)
class Symbolic:
    text: str

    def __str__(self) -> str:
        return self.text


class ParseError(ValueError):
    pass


def tokenize(text: str) -> List[str]:
    tokens: List[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if text.startswith(">>>", index):
            tokens.append(">>>")
            index += 3
            continue
        if text.startswith(("===", "!=="), index):
            tokens.append(text[index : index + 3])
            index += 3
            continue
        if text.startswith(("**", "&&", "||", "??", "==", "!=", "<=", ">=", "<<", ">>"), index):
            tokens.append(text[index : index + 2])
            index += 2
            continue
        if char in "+-*/%&|^!~<>?:.,()[]{}=":
            tokens.append(char)
            index += 1
            continue
        if char in "\"'`":
            quote = char
            start = index
            index += 1
            while index < len(text):
                if text[index] == "\\":
                    index += 2
                    continue
                if text[index] == quote:
                    index += 1
                    break
                index += 1
            tokens.append(text[start:index])
            continue
        if char.isdigit():
            start = index
            index += 1
            while index < len(text) and (
                text[index].isalnum() or text[index] in "xX."
            ):
                index += 1
            tokens.append(text[start:index])
            continue
        if char.isalpha() or char in "_$":
            start = index
            index += 1
            while index < len(text) and (text[index].isalnum() or text[index] in "_$"):
                index += 1
            tokens.append(text[start:index])
            continue
        raise ParseError(f"unsupported character {char!r} in {text!r}")
    return tokens


class Parser:
    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.index = 0

    def peek(self) -> Optional[str]:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def take(self, expected: Optional[str] = None) -> str:
        token = self.peek()
        if token is None:
            raise ParseError("unexpected end of expression")
        if expected is not None and token != expected:
            raise ParseError(f"expected {expected!r}, got {token!r}")
        self.index += 1
        return token

    def parse(self) -> Any:
        value = self.expression(0)
        if self.peek() is not None:
            raise ParseError(f"trailing token {self.peek()!r}")
        return value

    def expression(self, min_precedence: int) -> Any:
        left = self.unary()
        while True:
            token = self.peek()
            if token == "?":
                if min_precedence > 0:
                    break
                self.take("?")
                consequent = self.expression(0)
                self.take(":")
                alternate = self.expression(0)
                left = ("cond", left, consequent, alternate)
                continue
            precedence = {
                "||": 1,
                "??": 1,
                "&&": 2,
                "|": 3,
                "^": 4,
                "&": 5,
                "==": 6,
                "!=": 6,
                "===": 6,
                "!==": 6,
                "<": 7,
                ">": 7,
                "<=": 7,
                ">=": 7,
                "<<": 8,
                ">>": 8,
                ">>>": 8,
                "+": 9,
                "-": 9,
                "*": 10,
                "/": 10,
                "%": 10,
                "**": 11,
            }.get(token or "")
            if precedence is None or precedence < min_precedence:
                break
            operator = self.take()
            right = self.expression(precedence + (0 if operator == "**" else 1))
            left = ("binary", operator, left, right)
        return left

    def unary(self) -> Any:
        token = self.peek()
        if token in {"+", "-", "!", "~"}:
            operator = self.take()
            return ("unary", operator, self.unary())
        return self.postfix(self.primary())

    def postfix(self, value: Any) -> Any:
        while True:
            token = self.peek()
            if token == ".":
                self.take(".")
                value = ("member", value, self.take())
            elif token == "[":
                self.take("[")
                index = self.expression(0)
                self.take("]")
                value = ("index", value, index)
            elif token == "(":
                self.take("(")
                args = []
                if self.peek() != ")":
                    while True:
                        args.append(self.expression(0))
                        if self.peek() != ",":
                            break
                        self.take(",")
                self.take(")")
                value = ("call", value, args)
            else:
                break
        return value

    def primary(self) -> Any:
        token = self.take()
        if token == "(":
            value = self.expression(0)
            self.take(")")
            return value
        if token == "[":
            items = []
            if self.peek() != "]":
                while True:
                    items.append(self.expression(0))
                    if self.peek() != ",":
                        break
                    self.take(",")
            self.take("]")
            return ("array", items)
        if token == "new":
            name = self.take()
            if name != "Uint8Array":
                raise ParseError(f"unsupported constructor {name!r}")
            self.take("(")
            argument = self.expression(0)
            self.take(")")
            return ("newarray", argument)
        if NUMBER.match(token):
            base = 16 if token.lower().startswith("0x") else 10
            return ("number", int(token, base))
        if token[0] in "\"'`" and token[-1:] == token[0]:
            return ("string", token[1:-1])
        if NAME.match(token):
            return ("name", token)
        raise ParseError(f"unexpected token {token!r}")


def eval_node(node: Any) -> Any:
    kind = node[0]
    if kind == "number":
        return node[1]
    if kind == "string":
        return node[1]
    if kind == "name":
        return Symbolic(node[1])
    if kind == "array":
        return [eval_node(item) for item in node[1]]
    if kind == "newarray":
        value = eval_node(node[1])
        if isinstance(value, list):
            return value
        if isinstance(value, int):
            return [0] * value
        return Symbolic(f"new Uint8Array({render(value)})")
    if kind == "member":
        obj = eval_node(node[1])
        prop = node[2]
        if isinstance(obj, list) and prop.isdigit():
            return obj[int(prop)]
        return Symbolic(f"{render(obj)}.{prop}")
    if kind == "index":
        obj = eval_node(node[1])
        index = eval_node(node[2])
        if isinstance(obj, list) and isinstance(index, int):
            return obj[index] if 0 <= index < len(obj) else 0
        return Symbolic(f"{render(obj)}[{render(index)}]")
    if kind == "call":
        callee = node[1]
        args = [eval_node(arg) for arg in node[2]]
        name = callee[1] if callee[0] == "name" else render(eval_node(callee))
        return eval_call(name, args)
    if kind == "unary":
        operator = node[1]
        value = eval_node(node[2])
        if isinstance(value, int):
            return {
                "+": lambda x: x,
                "-": lambda x: -x,
                "!": lambda x: int(not x),
                "~": lambda x: ~x,
            }[operator](value)
        return Symbolic(f"{operator}{render(value)}")
    if kind == "binary":
        operator = node[1]
        left = eval_node(node[2])
        right = eval_node(node[3])
        if isinstance(left, int) and isinstance(right, int):
            result = eval_binary(operator, left, right)
            if result is not None:
                return result
        return Symbolic(f"({render(left)} {operator} {render(right)})")
    if kind == "cond":
        test = eval_node(node[1])
        if isinstance(test, int):
            return eval_node(node[2] if test else node[3])
        return Symbolic(
            f"({render(test)} ? {render(eval_node(node[2]))} : "
            f"{render(eval_node(node[3]))})"
        )
    raise ParseError(f"unknown node {kind}")


def eval_binary(operator: str, left: int, right: int) -> Optional[int]:
    try:
        if operator == "+":
            return left + right
        if operator == "-":
            return left - right
        if operator == "*":
            return left * right
        if operator == "/":
            return int(left / right)
        if operator == "%":
            return left % right
        if operator == "**":
            return left**right
        if operator == "&":
            return left & right
        if operator == "|":
            return left | right
        if operator == "^":
            return left ^ right
        if operator == "<<":
            return left << right
        if operator == ">>":
            return left >> right
        if operator == ">>>":
            return (left & 0xFFFFFFFF) >> right
        if operator == "==":
            return int(left == right)
        if operator == "!=":
            return int(left != right)
        if operator == "===":
            return int(left == right)
        if operator == "!==":
            return int(left != right)
        if operator == "<":
            return int(left < right)
        if operator == ">":
            return int(left > right)
        if operator == "<=":
            return int(left <= right)
        if operator == ">=":
            return int(left >= right)
        if operator == "&&":
            return int(bool(left) and bool(right))
        if operator == "||":
            return int(bool(left) or bool(right))
        if operator == "??":
            return left
    except (ZeroDivisionError, OverflowError, ValueError):
        return None
    return None


def eval_call(name: str, args: List[Any]) -> Any:
    if name in {"Number", "parseInt"} and args:
        value = args[0]
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value, 0)
            except ValueError:
                return Symbolic(f"{name}({render(value)})")
        return Symbolic(f"{name}({render(value)})")
    if name == "Boolean" and args:
        return int(bool(args[0]))
    if name in {
        "Math.min",
        "Math.max",
        "Math.abs",
        "Math.round",
        "Math.floor",
        "Math.ceil",
    } and args:
        if all(isinstance(value, int) for value in args):
            if name == "Math.min":
                return min(args)
            if name == "Math.max":
                return max(args)
            if name == "Math.abs":
                return abs(args[0])
            if name == "Math.round":
                return int(round(args[0]))
            if name == "Math.floor":
                return args[0]
            if name == "Math.ceil":
                return args[0]
        return Symbolic(f"{name}({', '.join(render(value) for value in args)})")
    return Symbolic(f"{name}({', '.join(render(value) for value in args)})")


def render(value: Any) -> str:
    if isinstance(value, Symbolic):
        return value.text
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    if isinstance(value, list):
        return "[" + ", ".join(render(item) for item in value) + "]"
    return str(value)


def evaluate(expression: str) -> Any:
    text = expression.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    return eval_node(Parser(tokenize(text)).parse())


def field_source(value: Any) -> str:
    if isinstance(value, int):
        return "literal"
    if isinstance(value, Symbolic) and NAME.match(value.text):
        return "arg"
    return "computed"


def normalize_expression(expression: str) -> Tuple[str, str, Optional[int]]:
    try:
        value = evaluate(expression)
    except ParseError:
        return expression.strip(), "computed", None
    if isinstance(value, int):
        return str(value), "literal", value
    return render(value), field_source(value), None


def split_items(text: str) -> List[str]:
    items: List[str] = []
    depth = 0
    start = 0
    quote: Optional[str] = None
    index = 0
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in "\"'`":
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            items.append(text[start:index].strip())
            start = index + 1
        index += 1
    tail = text[start:].strip()
    if tail:
        items.append(tail)
    return items


def compile_payload(
    expressions: Iterable[str],
    data_size: int,
    exports: Optional[Dict[str, Tuple[Tuple[int, ...], ...]]] = None,
) -> Dict[str, Any]:
    expressions = [str(item).strip() for item in expressions if str(item).strip()]
    if not expressions:
        return {"kind": "none", "length": 0}

    if len(expressions) == 1:
        text = expressions[0]
        length = LENGTH.match(text)
        if length:
            return {
                "kind": "argument",
                "argument": length.group(1),
                "length": data_size,
            }
        buffer_assign = ASSIGN_BUFFER.match(text)
        if buffer_assign:
            return {"kind": "zero", "length": int(buffer_assign.group(2))}
        values_assign = ASSIGN_VALUES.match(text)
        if values_assign:
            values = [evaluate(item) for item in split_items(values_assign.group(2))]
            if all(isinstance(value, int) for value in values):
                return {"kind": "constant", "bytes": values}
            fields = []
            for index, value in enumerate(values):
                field = {
                    "index": index,
                    "expression": render(value),
                    "source": field_source(value),
                }
                if isinstance(value, int):
                    field["value"] = value
                fields.append(field)
            return {"kind": "indexed", "length": len(fields), "fields": fields}
        new_array = NEW_ARRAY.match(text)
        if new_array:
            values = [evaluate(item) for item in split_items(new_array.group(1))]
            if all(isinstance(value, int) for value in values):
                return {"kind": "constant", "bytes": values}
            return {
                "kind": "unknown",
                "raw": expressions,
                "reason": "non-constant Uint8Array literal",
            }
        new_length = NEW_LENGTH.match(text)
        if new_length:
            return {"kind": "constant", "bytes": [0] * int(new_length.group(1))}
        new_name = NEW_NAME.match(text)
        if new_name:
            return {
                "kind": "buffer",
                "argument": new_name.group(1),
                "length": data_size,
            }
        if exports and DOTTED_NAME.match(text):
            frames = exports.get(text.split(".", 1)[1])
            if frames:
                if len(frames) == 1:
                    return {"kind": "constant", "bytes": list(frames[0])}
                return {
                    "kind": "frames",
                    "frames": [list(frame) for frame in frames],
                }
        if NUMBER.match(text):
            return {"kind": "constant", "bytes": [int(text, 0)]}
        if NAME.match(text):
            return {"kind": "argument", "argument": text, "length": data_size}

    # Buffer allocation followed by indexed writes, e.g.
    # a=new Uint8Array(5); a[1]=n>>8&255; ...
    base_name = None
    base_length = None
    base_fields: List[Dict[str, Any]] = []
    rest = expressions
    first = expressions[0]
    buffer_assign = ASSIGN_BUFFER.match(first)
    values_assign = ASSIGN_VALUES.match(first)
    if buffer_assign:
        base_name = buffer_assign.group(1)
        base_length = int(buffer_assign.group(2))
        rest = expressions[1:]
    elif values_assign:
        base_name = values_assign.group(1)
        values = [evaluate(item) for item in split_items(values_assign.group(2))]
        base_length = len(values)
        for index, value in enumerate(values):
            field = {
                "index": index,
                "expression": render(value),
                "source": field_source(value),
            }
            if isinstance(value, int):
                field["value"] = value
            base_fields.append(field)
        rest = expressions[1:]

    if base_name is not None:
        by_index: Dict[int, Dict[str, Any]] = {
            field["index"]: field for field in base_fields
        }
        for item in rest:
            assignment = ASSIGN.match(item)
            if not assignment or assignment.group(1) != base_name:
                by_index = {}
                break
            index = int(assignment.group(2))
            expression, source, value = normalize_expression(assignment.group(3))
            field = {
                "index": index,
                "expression": expression,
                "source": source,
            }
            if value is not None:
                field["value"] = value
            by_index[index] = field
        if by_index:
            fields = [by_index[index] for index in sorted(by_index)]
            length = base_length or (max(by_index) + 1)
            return {"kind": "indexed", "length": length, "fields": fields}

    if all(NUMBER.match(item) for item in expressions):
        return {"kind": "constant", "bytes": [int(item, 0) for item in expressions]}

    fields = []
    for item in expressions:
        assignment = ASSIGN.match(item)
        if not assignment:
            fields = []
            break
        index = int(assignment.group(2))
        expression, source, value = normalize_expression(assignment.group(3))
        field: Dict[str, Any] = {
            "index": index,
            "expression": expression,
            "source": source,
        }
        if value is not None:
            field["value"] = value
        fields.append(field)
    if fields:
        fields.sort(key=lambda field: field["index"])
        length = max(data_size, fields[-1]["index"] + 1)
        return {"kind": "indexed", "length": length, "fields": fields}

    pushes = []
    for index, item in enumerate(expressions):
        push = PUSH.match(item)
        if not push:
            pushes = []
            break
        expression, source, value = normalize_expression(push.group(2))
        field = {"index": index, "expression": expression, "source": source}
        if value is not None:
            field["value"] = value
        pushes.append(field)
    if pushes:
        return {"kind": "push", "length": len(pushes), "fields": pushes}

    return {
        "kind": "unknown",
        "raw": expressions,
        "reason": "unsupported payload expression form",
    }


def normalize_json_data(items: Any) -> List[Dict[str, Any]]:
    out = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        expression = str(item.get("expression", "")).strip()
        if not expression:
            continue
        normalized, source, value = normalize_expression(expression)
        entry: Dict[str, Any] = {
            "field": item.get("field"),
            "expression": normalized,
            "source": source,
        }
        if value is not None:
            entry["value"] = value
        out.append(entry)
    return out


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_commands(path: Path) -> Dict[Tuple[str, int, int, str], int]:
    rows: Dict[Tuple[str, int, int, str], int] = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            key = (
                str(row["pid"]).upper(),
                int(row["class"]),
                int(row["command"]),
                str(row.get("name") or ""),
            )
            rows[key] = int(row.get("dataSize") or 0)
    return rows


def load_facts(path: Path) -> Dict[Tuple[str, int, int, str], Dict[str, Any]]:
    rows: Dict[Tuple[str, int, int, str], Dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            key = (
                str(row["pid"]).upper(),
                int(row["class"]),
                int(row["command"]),
                str(row.get("name") or ""),
            )
            rows[key] = row
    return rows


def scan_module_exports(
    paths: Iterable[Path],
) -> Dict[str, Tuple[Tuple[int, ...], ...]]:
    """Resolve short webpack export names to literal Uint8Array frame arrays.

    A shared module exposes names such as ``i.pu``. The public data should not
    contain that minified name or the bundle, but the bytes are still a static
    protocol fact. Ambiguous symbol names are left unresolved rather than
    guessed.
    """

    candidates: Dict[str, set] = {}
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        symbol_defs: Dict[str, set] = {}
        for match in FRAME_ARRAY.finditer(text):
            frames = tuple(
                tuple(int(value) for value in frame.split(",") if value.strip())
                for frame in (
                    item.strip() for item in FRAME_VALUE.findall(match.group(2))
                )
            )
            if frames:
                symbol_defs.setdefault(match.group(1), set()).add(frames)
        symbols = {
            symbol: next(iter(values))
            for symbol, values in symbol_defs.items()
            if len(values) == 1
        }
        for match in EXPORT_MAP.finditer(text):
            frames = symbols.get(match.group(2))
            if frames:
                candidates.setdefault(match.group(1), set()).add(frames)

    return {
        name: next(iter(values))
        for name, values in candidates.items()
        if len(values) == 1
    }


def load_module_exports(
    bundles: Path, pid: str
) -> Dict[str, Tuple[Tuple[int, ...], ...]]:
    directory = bundles / pid
    if not directory.is_dir():
        return {}
    return scan_module_exports(directory.glob("*.js"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--facts",
        type=Path,
        required=True,
        help="OpenSynapse protocol_facts.jsonl",
    )
    parser.add_argument(
        "--out11",
        type=Path,
        required=True,
        help="extractor out11/protocols.json",
    )
    parser.add_argument(
        "--bundles",
        type=Path,
        required=True,
        help="extractor bundle directory containing one folder per PID",
    )
    parser.add_argument(
        "--commands",
        type=Path,
        default=Path("razer_hid/data/commands.jsonl.gz"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("razer_hid/data/payloads.jsonl.gz"),
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("razer_hid/data/schemas/payload.schema.json"),
    )
    args = parser.parse_args()

    commands = load_commands(args.commands)
    facts = load_facts(args.facts)
    data = load_json(args.out11)
    exports_cache: Dict[str, Dict[str, Tuple[Tuple[int, ...], ...]]] = {}

    def exports_for(pid: str) -> Dict[str, Tuple[Tuple[int, ...], ...]]:
        if pid not in exports_cache:
            exports_cache[pid] = load_module_exports(args.bundles, pid)
        return exports_cache[pid]

    out11: Dict[Tuple[str, int, int, str], Dict[str, Any]] = {}
    for product in data.get("products", []):
        pid = str(product.get("pid")).upper()
        for command in product.get("usedCommands") or []:
            key = (
                pid,
                int(command["commandClass"]),
                int(command["commandId"]),
                str(command.get("name") or ""),
            )
            out11[key] = command

    keys = set(commands) | set(facts) | set(out11)
    rows = []
    for key in sorted(keys):
        pid, command_class, command_id, name = key
        fact = facts.get(key, {})
        command = out11.get(key, {})
        payload = fact.get("payload") or command.get("payload")
        json_data = normalize_json_data(command.get("jsonData"))
        if not payload and not json_data:
            continue
        data_size = int(
            fact.get("dataSize")
            or command.get("dataSize")
            or commands.get(key)
            or 0
        )
        exports = None
        if payload and len(payload) == 1 and DOTTED_NAME.match(str(payload[0])):
            exports = exports_for(pid)
        compiled = (
            compile_payload(payload, data_size, exports)
            if payload
            else {"kind": "none", "length": 0}
        )
        row: Dict[str, Any] = {
            "pid": pid,
            "class": command_class,
            "command": command_id,
            "name": name or None,
            "dataSize": data_size,
            "source": "facts" if fact.get("payload") else "out11",
        }
        row.update(compiled)
        if json_data:
            row["jsonData"] = json_data
        rows.append(row)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.out, "wt", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["pid", "class", "command", "dataSize", "kind", "source"],
        "properties": {
            "pid": {"type": "string", "pattern": "^[0-9A-F]{4}$"},
            "class": {"type": "integer", "minimum": 0, "maximum": 255},
            "command": {"type": "integer", "minimum": 0, "maximum": 255},
            "name": {"type": ["string", "null"]},
            "dataSize": {"type": "integer", "minimum": 0},
            "kind": {
                "enum": [
                    "constant",
                    "argument",
                    "buffer",
                    "indexed",
                    "push",
                    "frames",
                    "zero",
                    "none",
                    "unknown",
                ]
            },
            "bytes": {
                "type": "array",
                "items": {"type": "integer", "minimum": 0, "maximum": 255},
            },
            "length": {"type": "integer", "minimum": 0},
            "argument": {"type": "string"},
            "frames": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0, "maximum": 255},
                },
            },
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["index", "expression", "source"],
                    "properties": {
                        "index": {"type": "integer", "minimum": 0},
                        "expression": {"type": "string"},
                        "source": {"enum": ["literal", "arg", "computed"]},
                        "value": {"type": "integer"},
                    },
                },
            },
            "jsonData": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["field", "expression", "source"],
                    "properties": {
                        "field": {"type": ["string", "null"]},
                        "expression": {"type": "string"},
                        "source": {"enum": ["literal", "arg", "computed"]},
                        "value": {"type": "integer"},
                    },
                },
            },
            "raw": {"type": "array", "items": {"type": "string"}},
            "reason": {"type": "string"},
            "source": {"enum": ["facts", "out11"]},
        },
    }
    args.schema.parent.mkdir(parents=True, exist_ok=True)
    args.schema.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    by_kind: Dict[str, int] = {}
    for row in rows:
        by_kind[row["kind"]] = by_kind.get(row["kind"], 0) + 1
    print(
        f"{len(rows)} rows, {args.out.stat().st_size / (1024 * 1024):.2f} MiB, "
        f"{dict(sorted(by_kind.items()))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
