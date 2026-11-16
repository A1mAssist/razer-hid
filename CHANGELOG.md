# Changelog

## 0.2.0 - 2026-11-16

- Added the BlackShark V3 Pro protocol 64 transport: 64-byte report-id-2
  requests, wake sequence, transaction/checksum validation, busy/resend retry
  and typed battery, charging, sidetone, THX, ANC and game/chat helpers.
- Added the 451-row transport table with report id, report size, connection,
  confidence and evidence. The command export now carries
  `transportConfidence`.
- Added 130,673 payload templates and `PayloadDb`, covering constants,
  arguments, buffers, indexed fields, push sequences, ordered frames, zero
  buffers and no-payload commands.
- Added a small expression interpreter and bundle-export resolver. The 245
  shared-module export rows in the snapshot now resolve to literal frame bytes;
  no payload row is left `unknown`.
- Added `read` features `sidetone`, `thx`, `anc` and `gamechat`, plus
  `--transport hid64` and raw-frame dry runs.
- Added `docs/protocol-64.md`, `docs/transport-table.md` and
  `docs/payload-templates.md`.
- The public-tree audit now passes without local absolute paths in tooling.

## 0.1.0 - 2026-11-16

- Protocol 2.5 frame builder/parser with XOR checksum, transaction rotation,
  busy retry and declared-size override.
- Protocol 30 frame builder/parser for HID 3.0 and BLE, including 20/8-byte
  response header handling.
- Experimental asynchronous BLE transport.
- 158,975 public command identity facts across 336 PIDs.
- Eight curated device transports; six HID 2.5 devices, one BLE device and one
  64-byte headset transport marked unsupported.
- Typed battery, charging, polling, brightness, DPI, effect and wireless-link
  helpers.
- CLI with `list`, `probe`, `read`, `raw --dry-run` and write consent.
- Real 00B8 `wireless-link-status` read documented in
  `docs/hardware-validation.md`.
- Public-tree audit that rejects vendor binaries, assets, local paths and
  extracted payload expressions.
