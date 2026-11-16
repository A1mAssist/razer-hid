# Notice and provenance

This project is an independent interoperability reference. It is not
affiliated with, endorsed by, or sponsored by Razer Inc.

## Sources

- Protocol facts were derived from locally installed Razer Synapse 4
  middleware bundles and the Chroma Studio snapshot described in
  `docs/provenance.md`.
- Frame layouts were cross-checked against the OpenSynapse protocol notes and
  the public `razer-hid` command table.
- No vendor JavaScript, decompiled source, installer, firmware, image, SVG, or
  other vendor asset is included in this repository.

## Data boundary

- The published command table contains protocol identity facts only:
  product id, command class, command id, declared size, name, direction,
  declared/called flags, confidence and source layer.
- The transport table contains PID, transport name, report id, report size,
  connection, confidence and short evidence labels.
- The payload template table contains normalized short expressions, field
  layouts and literal frame bytes. Shared-module exports are resolved to their
  literal frames; the vendor bundle is read as text and is not executed or
  copied.
- Vendor JavaScript, minified bundles, raw `jsonData` source snippets and
  installers are not published.
- No command path is marked hardware-verified. Static facts are not hardware
  validation. One 00B8 wireless-link read is documented separately.

## Takedown

If you believe this repository contains material that should not be
distributed, open an issue or contact the maintainer. The command table is
generated data; it can be removed without removing the tooling.
