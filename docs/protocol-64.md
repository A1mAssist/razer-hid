# Protocol 64 (BlackShark V3 Pro headset)

One 64-byte HID output report. This is not protocol 2.5 with a larger payload;
the header offsets and the success test are different.

| Offset | Request | Success reply |
|---:|---|---|
| 0 | report id `0x02` | report id `0x02` |
| 1 | status `0x00` | status `0x02` |
| 2 | transaction id `0x60` | echoed transaction id |
| 3..5 | zero | vendor bytes |
| 6 | `4 + len(arguments)` | vendor bytes |
| 7..8 | zero | vendor bytes |
| 9 | direction (`0x80` wireless, `0x00` wired) | vendor byte |
| 10 | command class | command class |
| 11 | `0x00` | subtype (`0x01` on success) |
| 12 | command id | argument count |
| 13..61 | arguments (up to 49 bytes) | arguments |
| 62 | XOR of bytes 0..61 | XOR of bytes 0..61 |
| 63 | zero | zero |

A reply is accepted only when the checksum is valid, the transaction id and
class match the request, status is `0x02`, and subtype is `0x01`. Status `0x01`
or `0x03` is treated as a resend request. A 63-byte read that omits the report
id is accepted.

## Wake sequence

Before the first query the transport sends three frames, 2 ms apart:

```text
02:00 direction 0x00
2A:00 direction 0x00
2A:00 direction 0x80
```

The class is `0x02` for the first frame and `0x2A` for the other two.

## Commands implemented

| Feature | Read | Write | Arguments |
|---|---|---|---|
| battery | `21:00` | - | response byte 0 is percent |
| charging | `2A:00` | - | `0` = not charging |
| sidetone | `19:00` | `99:01` | level `0..15` |
| THX | `1E:00` | `9E:01` | `0` / `1` |
| ANC | `12:00` | `92:02` | mode, level |
| game/chat | `5C:00` | `DC:01` | wire value `20 - balance` |

ANC modes are `0x00` off, `0x01` ANC and `0x50` ambient. ANC level is clamped
to `1..4` for ANC, `1` for ambient and `0` for off. The game/chat read inverts
the wire byte with `20 - value`.

## Device IDs

These PIDs use the protocol 64 envelope below:

| PID | Variant | Direction |
|---|---|---|
| `0576` | BlackShark V3 Pro USB | wired |
| `0577` | BlackShark V3 Pro receiver | wireless |
| `101B` | observed 2.4 GHz dongle | wireless |
| `101C` | observed USB cable | wired |

`0565` and `056E` are BlackShark V2 HyperSpeed devices that use the separate
`billie64` wire format. They are listed for family context only; do not send
this frame to them.

The implementation is `razer_hid/transport/hid64.py`; typed commands are in
`razer_hid/payloads/blackshark.py`; golden tests are `tests/test_hid64.py` and
`tests/test_blackshark.py`.

`0576` is implemented through the synchronous CLI and `RazerDevice` path, but
no 64-byte device has been hardware-verified in this release. The layout comes
from `src/OpenSynapse.Windows/Protocols/BlackSharkV3ProProtocol.cs` and the
read path from `BlackSharkHeadsetService.ReadValueAsync`.
