# Payload templates

`razer_hid/data/payloads.jsonl.gz` contains one JSON row per command that has a
request-payload expression or a response field map. It is compiled from the
extracted middleware expressions by `tools/compile_payloads.py`; the compiler
does not execute the vendor bundles.

## Kinds

| Kind | Meaning | Use |
|---|---|---|
| `constant` | `bytes` is the complete request payload | send `bytes` directly |
| `zero` | `length` zero bytes | send `bytes(length)` |
| `argument` | the caller supplies the whole array named `argument` | send the caller's bytes |
| `buffer` | `argument` is a buffer identifier; `length` is the declared size | send the buffer |
| `indexed` | `fields` assign individual byte indices | start with `length` zero bytes and fill each field |
| `push` | `fields` append bytes in order | append each field |
| `frames` | `frames` is an ordered list of literal byte frames | send each frame in order |
| `none` | no request payload | send an empty payload |
| `unknown` | the expression could not be normalized | read `raw`; do not guess |

`fields` entries carry `index`, `expression`, `source` and, for literal values,
`value`. `source` is `literal`, `arg` (a bare argument name) or `computed`.
`jsonData` entries describe response fields with the same source tags.

The compiler also resolves literal shared-module exports. For example, an
extracted expression such as `i.pu` is looked up in the bundle tree and replaced
by its static `Uint8Array` frame bytes. The bundle is read as text; it is never
executed, and minified symbol names are not copied into the public data. In the
2026-11-16 snapshot this resolved 245 rows, leaving no `unknown` templates.

## Example

```python
from razer_hid.payload_db import PayloadDb

db = PayloadDb.load()
template = db.for_command("00B8", 0x07, 0x80)
if template.kind == "none":
    payload = b""
elif template.kind == "indexed":
    payload = template.build(t=0)
else:
    payload = template.build()

# Multi-frame commands expose the ordered frames explicitly.
for frame in template.build_frames():
    send(frame)
```

The expression language is intentionally small: numeric literals, `Number`,
`Math.min/max/abs/round/floor/ceil`, unary and binary arithmetic, bitwise
operators, member/index access and conditional expressions. Anything outside
that subset stays symbolic rather than pretending to be executable.

## Limits

- A `computed` expression is a protocol hint, not a guarantee that the caller
  has supplied the right argument names. The vendor handler's parameter names
  are preserved because renaming them would make the template harder to audit.
- A `length` from `dataSize` is the declared wire size, which can be larger than
  the bytes a particular call writes. Use `--allow-oversize` in the raw CLI only
  when the command is known to need it.
- Response field expressions are reference material. Typed helpers in
  `razer_hid/payloads/` implement the common read/write paths with validation.
- Ambiguous or non-literal module exports stay `unknown` instead of being
  guessed. The current snapshot has 130,673 rows and zero `unknown` rows.
