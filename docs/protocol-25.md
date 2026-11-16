# Protocol 2.5 frame

One 91-byte HID feature report.

| Offset | Field |
|---:|---|
| 0 | HID report id |
| 1 | status (request: 0) |
| 2 | transaction id |
| 3..5 | echoed packet fields (request: 0) |
| 6 | declared data size (0..80) |
| 7 | command class |
| 8 | command id |
| 9..88 | arguments (80 bytes) |
| 89 | XOR checksum over bytes 3..88 |
| 90 | zero |

Some firmware includes byte 2 (the transaction id) in the checksum. Pass
`accept_transaction_checksum=True` for those devices. The Leviathan V2 X is one
example.

`data_size` is not always `len(arguments)`. DPI stages are the canonical
example: the command table declares 80 bytes while the call writes
`7 * stage_count + 3`. Use `allow_oversize=True` for that form.

A successful reply has status `0x02`; `0x01` means busy and is retried. The
reply must echo the transaction id, class, command id and pass the checksum.
`0xFF` is a wildcard transaction id.

The Python implementation is `razer_hid/transport/hid25.py`; the golden tests
are `tests/test_hid25.py`.
