# Device table

Only transports with evidence are listed as supported. A PID in the command
database with no transport row can still be addressed explicitly.

| PID | Product | Transport | Report | Notes |
|---|---|---|---|---|
| `0046` | Razer Mamba Elite | HID 2.5 | 0 / 91 | protocol 2.5 default |
| `00B8` | Razer Viper V3 HyperSpeed | HID 2.5 | 0 / 91 | rotating transaction `0..31` |
| `028D` | Blackwidow V4 Pro | HID 2.5 | 0 / 91 | lighting uses class `0x0F` |
| `00A4` | Razer Mouse Dock Pro | HID 2.5 | 0 / 91 | transaction `0xE0 | sequence` |
| `054A` | Razer Leviathan V2 X / Pokemon soundbar | HID 2.5 | 7 / 91 | transaction checksum variant |
| `0A45` | Razer Wolverine V3 TE | HID 2.5 | 4 / 91 | gamepad report id |
| `00E5` | Razer Viper V4 Pro | BLE 3.0 | GATT | experimental; async only |
| `0576` | Razer BlackShark V3 Pro | 64-byte output | 2 / 64 | implemented, not hardware-verified |
| `0577` | Razer BlackShark V3 Pro receiver | 64-byte output | 2 / 64 | implemented, not hardware-verified |
| `101B` | BlackShark V3 Pro 2.4 GHz dongle | 64-byte output | 2 / 64 | implemented, not hardware-verified |
| `101C` | BlackShark V3 Pro USB | 64-byte output | 2 / 64 | implemented, not hardware-verified |

Evidence lives in `razer_hid/data/devices.json`. Do not infer a transport from
a bundle name; the report id and frame shape must match.

`0565` and `056E` are BlackShark V2 HyperSpeed devices on `billie64`, not the
protocol 64 envelope above.

Hardware note: on 2026-11-16 the 00B8 dongle answered `00:BF` (`wireless link
status`, size `0x50`) with status `0x02`. Battery/DPI/polling returned `0x04`
while the mouse was asleep or off. No write was attempted.
