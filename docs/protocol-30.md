# Protocol 30 frame (HID 3.0 / BLE)

Requests use an 8-byte header and no checksum:

| Offset | Field |
|---:|---|
| 0 | transaction id (0..31) |
| 1..3 | payload length, 24-bit little-endian |
| 4 | command class |
| 5 | command id |
| 6..7 | header selectors |
| 8.. | payload |

Replies normally use a 20-byte header. An 8-byte header is accepted when the
declared length matches the shorter form. The status byte is at offset 7;
`0x02` is success.

BLE uses the same frame over GATT:

```text
service 52401523-f97c-7f90-0e7f-6c6f4e36db1c
write   52401524-f97c-7f90-0e7f-6c6f4e36db1c
notify  52401525-f97c-7f90-0e7f-6c6f4e36db1c
```

The BLE request builder caps payloads at 254 bytes in the middleware path.
`rzDevice30Layla` is a different frame format and must not use this parser.

The Python implementation is `razer_hid/transport/hid30.py`; BLE is
`razer_hid/transport/ble30.py`; the golden tests are `tests/test_hid30.py`.
