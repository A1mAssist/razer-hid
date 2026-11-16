# Hardware validation

Date: **2026-11-16**  
Host: Windows 11, Python 3.12, hidapi 0.15.0  
Device: Razer Viper V3 HyperSpeed (`1532:00B8`)

## Transport probe

`razerctl probe 00B8` selected:

```text
transport: hid25
reportId: 0
path: \\?\HID#VID_1532&PID_00B8&MI_00#...
```

The working collection is usage page `0x0001`, usage `0x0002`, interface 0.
Sending a feature report to the other collections failed at the OS/HID layer.

## Verified read

Command:

```text
class 0x00, command 0xBF, dataSize 0x50, no arguments
```

The dongle answered with status `0x02` (success) and 80 argument bytes:

```text
02 00 00 B8 00 FF FF 00 ...
```

Transaction ids 0, 1, 2, 15 and 31 all echoed correctly and returned status
`0x02`, so the 00B8 path uses the rotating 0..31 sequence rather than a fixed
id.

## Not verified

While the mouse was asleep/off:

- battery (`07:80`)
- polling rate (`00:85`)
- DPI (`04:85`)
- firmware (`00:87`)

returned status `0x04`. That is a device response, not a framing failure. No
write command was sent during this validation.

No device or command path is therefore marked hardware-verified beyond the
`wireless-link-status` read above.
