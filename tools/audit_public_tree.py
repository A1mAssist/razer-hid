#!/usr/bin/env python3
"""Fail when the public tree contains material that should stay local."""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {
    ".git",
    "__pycache__",
    ".venv",
    "dist",
    "build",
    ".pytest_cache",
    ".egg-info",
    "razer_hid.egg-info",
}
FORBIDDEN_EXTENSIONS = {
    ".js",
    ".dll",
    ".exe",
    ".pdb",
    ".so",
    ".dylib",
    ".bin",
    ".zip",
    ".7z",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".pdf",
    ".woff",
    ".woff2",
    ".ttf",
}
TEXT_EXTENSIONS = {".md", ".py", ".json", ".toml", ".yml", ".yaml", ".txt"}
LOCAL_MARKERS = (
    "D:" + "\\Workspaces",
    "C:" + "\\Users",
    "artifacts/" + "upstream-reference",
)
MAX_BYTES = 5 * 1024 * 1024
FORBIDDEN_COMMAND_KEYS = {
    "payload",
    "jsonData",
    "evidence",
    "implemented",
    "methods",
    "referencedIn",
}


def main() -> int:
    failures = []
    for path in ROOT.rglob("*"):
        if any(part in SKIP_PARTS for part in path.parts) or path.is_dir():
            continue
        relative = path.relative_to(ROOT)
        if path.suffix.lower() in FORBIDDEN_EXTENSIONS:
            failures.append(f"binary/vendor asset: {relative}")
        if path.stat().st_size > MAX_BYTES:
            failures.append(f"file over 5 MiB: {relative}")
        if path.suffix.lower() in TEXT_EXTENSIONS:
            text = path.read_text(encoding="utf-8", errors="replace")
            for marker in LOCAL_MARKERS:
                if marker in text:
                    failures.append(f"local path marker {marker!r}: {relative}")

    for required in ("README.md", "LICENSE", "LICENSE-docs", "NOTICE.md"):
        if not (ROOT / required).is_file():
            failures.append(f"missing {required}")

    command_path = ROOT / "razer_hid/data/commands.jsonl.gz"
    if not command_path.is_file():
        failures.append("missing razer_hid/data/commands.jsonl.gz")
    else:
        with gzip.open(command_path, "rt", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                row = json.loads(line)
                extra = FORBIDDEN_COMMAND_KEYS.intersection(row)
                if extra:
                    failures.append(
                        f"forbidden command fields {sorted(extra)}: line {line_number}"
                    )
                    break

    if failures:
        print("public tree audit: FAIL")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("public tree audit: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
