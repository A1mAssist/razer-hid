# Provenance

Snapshot: **2026-11-16**.

## Inputs

- Razer Synapse 4 middleware bundle snapshot, `razer-mw-full-cdn`, out9 and
  out11 extractor layers, including the product bundle tree.
- OpenSynapse protocol notes for HID 2.5, HID 3.0/BLE, mapping and lighting.
- OpenSynapse implementation alignment for the 00B8, 0046, 028D, 054A, 00A4
  and 0A45 transports.

## What is published

- Normalized command identity facts: PID, class, command, declared size,
  direction, name, declared/called flags, confidence, source layer.
- Transport facts: PID, transport name, report id, report size, connection,
  confidence and short evidence labels.
- Normalized payload templates: short arithmetic expressions, field layouts and
  literal `Uint8Array` frame bytes. A shared-module export such as `i.pu` is
  replaced by the literal frames found in the bundle; the bundle is not
  executed and the minified name is not retained in the public row.
- Frame descriptions written for this package.
- A small set of typed payload schemas that are documented in code.

## What is not published

- Vendor JavaScript, minified bundles, decompiled code, installers, firmware,
  images, SVG layouts, screenshots, Chroma presets or other vendor assets.
- Raw `payload` expressions, minified symbols and raw `jsonData` source
  snippets. The normalized form is published instead.
- Local paths, serial numbers, logs or machine identifiers.
- The full OpenSynapse implementation map or C# protocol constants.

## Limits

- `declared` and `called` are static facts. Neither means the firmware accepted
  a write.
- No full hardware verification is included. No command path is marked
  hardware-verified; one 00B8 `wireless-link-status` read is documented.
- The transport table has 451 rows. Two PIDs retain `transport=unknown` because
  the snapshot has no product-specific transport evidence for them.
- The payload table has 130,673 rows and no `unknown` rows in this snapshot.
  Future ambiguous exports remain symbolic rather than guessed.
