# Contributing

Contributions are welcome when they keep the public data defensible.

## Do

- Add protocol facts with a source: bundle name, command table, or a documented
  hardware trace.
- Add transport rows only when the report id, report size and frame shape are
  evidenced.
- Add typed payload schemas with byte offsets, ranges, defaults and a test.
- Mark hardware claims separately; a static fact is not `verified`.

## Do not

- Do not commit vendor bundles, installers, firmware, decompiled code, images,
  Chroma assets, logs or serial numbers.
- Do not paste extracted JavaScript expressions (`payload`, `jsonData`) into
  the command table.
- Do not collapse `declared`, `called`, `implemented` and `verified` into one
  boolean.
- Do not claim a device supports a command because it appears in a shared
  library chunk.

## Checks

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python tools/audit_public_tree.py
```
