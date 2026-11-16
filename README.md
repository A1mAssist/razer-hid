# razer-hid

[English](README.md) | [简体中文](README.zh-CN.md)

Razer HID protocol 2.5/3.0/64 reference client, transport table and
command/payload database.

This is a **static, interoperability-first** package. It gives you the frame
layout, transport map, command identity table and reference client so you can
query a device without reverse-engineering the same bytes again.

> Status: v0.2. No full hardware verification; one 00B8 wireless-link read is
> documented below. `verified` is false for every device row.
> Writes can change or damage a device; read `SAFETY.md` first.

## What is included

- Protocol 2.5: 91-byte feature reports, XOR checksum, transaction ids,
  busy/retry handling, oversized arguments for commands such as DPI stages.
- Protocol 3.0: 8-byte request header, 24-bit little-endian length, 20/8-byte
  response parsing, optional BLE GATT transport.
- Protocol 64: the BlackShark V3 Pro 64-byte report-id-2 envelope, wake
  sequence, transaction checks, busy/resend retry and typed headset helpers.
- **158,975 command identity facts** across **336 PIDs**: class, command,
  declared size, name, direction, declared/called flags, confidence, source
  and transport confidence.
- **A 451-row transport table** with report id, report size, connection and
  evidence for HID 2.5, HID 3.0, 64-byte headset variants, BLE, native and
  external devices. Two rows remain explicitly unknown.
- **130,673 payload templates**: constants, arguments, buffers, indexed fields,
  push sequences, ordered frames, zero buffers and no-payload commands. The
  current snapshot has no unresolved templates.
- Typed helpers for battery, charging, polling rate, brightness, DPI, Chroma
  effects, wireless link, BlackShark sidetone, THX, ANC and game/chat balance.
- A CLI: `list`, `probe`, `read`, `raw --dry-run`.
- Protocol and data docs: `docs/protocol-25.md`, `docs/protocol-30.md`,
  `docs/protocol-64.md`, `docs/transport-table.md`,
  `docs/payload-templates.md` and `docs/device-table.md`.

The public data contains protocol facts, normalized short expressions and
literal frame bytes only. It does not contain vendor JavaScript, minified
bundles, installers, firmware, images or Chroma assets.

## Install

```powershell
cd razer-hid
pip install -e .

# Optional BLE transport
pip install -e ".[ble]"
```

`hidapi` is a core dependency; `bleak` is only needed for BLE.
If `razerctl` is not on `PATH`, use `python -m razer_hid.cli` instead.

## Quickstart

```python
from razer_hid import RazerDevice

with RazerDevice.open("00B8") as device:
    print(device.read_battery())      # BatteryStatus(percent=..., raw=...)
    print(device.read_dpi())          # Dpi(x=..., y=...)
    device.set_dpi(800, 800)
    print(device.read_polling())      # 1000 / 500 / ...
```

The same device object exposes `send_raw` and `read_raw` for commands that do
not have a typed helper. The command database tells you the class/id and
declared size:

```python
from razer_hid import CommandDb
from razer_hid import PayloadDb

db = CommandDb.load()
for command in db.find("00B8", "Get Battery Level"):
    print(command.command_class, command.command_id, command.data_size)

payloads = PayloadDb.load()
template = payloads.for_command("0309", 4, 0, "Get Link Status")
print(template.build().hex())
```

## CLI

```powershell
razerctl list
razerctl probe 00B8
razerctl read 00B8 battery
razerctl read 00B8 dpi

# Inspect a frame without opening a device
razerctl raw 00B8 07 80 --dry-run

# Protocol 30 frame
razerctl raw 00B8 0B 01 0102 --transport hid30 --transaction-id 3 --dry-run

# Raw writes need explicit consent
razerctl raw 00B8 04 05 0003200320 --allow-writes
```

Class and command arguments are hexadecimal (`07`, `0B`, `0x80`). Payload is
hex bytes separated by spaces or no separator.

## Supported devices

The full device list, including transport, report layout and status, is in
[`docs/device-table.md`](docs/device-table.md). The generated 451-row evidence
table is in [`docs/transport-table.md`](docs/transport-table.md); machine-readable
data is in `razer_hid/data/transports.json` and
`razer_hid/data/devices.json`.

`0565` and `056E` are BlackShark V2 HyperSpeed devices on `billie64`; they are
not the protocol 64 envelope above.

Unlisted PIDs can still be addressed with
`RazerDevice.open(pid, transport="hid25", report_id=...)` or probed with
`razerctl probe`. The 00B8 wireless-link read is documented in
[`docs/hardware-validation.md`](docs/hardware-validation.md).

## Command database

`razer_hid/data/commands.jsonl.gz` is a gzip JSONL file. Each row contains:

```text
pid product transport direction class command dataSize dataSizeVariants
name declared called confidence sourceLayer payloadSchema libraryDefined
callReference sourceBundle transportConfidence
```

- `declared`: the triple exists in the product's command table.
- `called`: a handler actually calls it. `libraryDefined` means the definition
  came from a shared library, not the product's own table.
- `confidence`: `source-backed` or `inferred`; never `verified`.
- `payloadSchema`: a normalized label when the source carried one; otherwise
  `null`.
- `transportConfidence`: `verified`, `evidenced`, `family-inferred` or
  `unknown`, taken from the separate transport table.

The generated counts are in `razer_hid/data/commands.index.json`.

## Payload templates

`razer_hid/data/payloads.jsonl.gz` is the companion request/response template
database. It is indexed by PID, class, command and optional name:

```python
from razer_hid import PayloadDb

db = PayloadDb.load()
template = db.for_command("0309", 4, 0, "Get Link Status")
print(template.kind)                 # constant
print(template.build().hex())        # fe00040f0581aac6

# Some templates describe an ordered list of frames.
for frame in template.build_frames():
    print(frame.hex())
```

`build()` returns the bytes for a single-frame template. `build_frames()`
always returns the ordered frame list and is the safe choice for multi-frame
commands. See `docs/payload-templates.md` for the schema and limits.

## What is not included

- No full hardware validation; every device row is `verified: false`. The one
  documented 00B8 wireless-link read is not a full device validation.
- BLE is asynchronous and experimental; the synchronous `RazerDevice` does not
  open BLE devices. Use `razer_hid.transport.ble30` with a device address.
- BlackShark V3 Pro protocol 64 is implemented. Other 64-byte headset formats
  (`billie64`, `valkyrie64`, `valkyrie-t3-64`, `mxic64`, `jolie64`,
  `avnera65`, `kraken37`, `hid25-64/65`, `mixer053e` and `protocol40`) are
  catalogued in the transport table but do not have typed transports here.
- Two PIDs (`0A23` and `053C`) in the transport table have no product-specific
  transport evidence. They are not silently assigned to HID 2.5.
- No raw vendor expressions or vendor code are published. If you need a typed
  payload for a command, add a reviewed schema under
  `razer_hid/data/schemas/`.

## License and provenance

- Code: MIT (`LICENSE`).
- Documentation and protocol data: CC BY 4.0 (`LICENSE-docs`).
- Sources and excluded material: `NOTICE.md` and `docs/provenance.md`.
- Razer, Chroma and related marks belong to Razer Inc. This project is not
  affiliated with Razer.

## Development

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python tools/audit_public_tree.py
```

To regenerate the command table from a local OpenSynapse snapshot:

```powershell
python tools/export_commands.py `
  --out11 <...>/out11/protocols.json `
  --facts <...>/protocol_facts.jsonl `
  --devices razer_hid/data/devices.json

python tools/compile_payloads.py `
  --facts <...>/protocol_facts.jsonl `
  --out11 <...>/out11/protocols.json `
  --bundles <...>/razer-mw-full-cdn/bundles

python tools/classify_transports.py --root <...>/OpenSynapse
```
