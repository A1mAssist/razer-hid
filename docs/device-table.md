# Supported devices / 支持设备

Only transports with evidence are listed. A PID in the command database with
no transport row can still be addressed explicitly.

这里只列出有传输证据的设备；命令库里没有传输行的 PID 仍可显式指定传输。

| PID | Product / 产品 | Transport / 传输 | Report | Status / 状态 |
|---|---|---|---|---|
| `0046` | Razer Mamba Elite | HID 2.5 | 0 / 91 | supported / 已支持 |
| `00B8` | Razer Viper V3 HyperSpeed | HID 2.5 | 0 / 91, tx 0..31 | supported / 已支持 |
| `028D` | Blackwidow V4 Pro | HID 2.5 | 0 / 91 | supported / 已支持 |
| `00A4` | Razer Mouse Dock Pro | HID 2.5 | 0 / 91, tx `0xE0 + seq` | supported / 已支持 |
| `054A` | Razer Leviathan V2 X / Pokemon soundbar | HID 2.5 | 7 / 91 | supported / 已支持 |
| `0A45` | Razer Wolverine V3 TE | HID 2.5 | 4 / 91 | supported / 已支持 |
| `00E5` | Razer Viper V4 Pro | BLE 3.0 | GATT | experimental, async only / 实验性，仅异步 |
| `0576` | Razer BlackShark V3 Pro | 64-byte output | 2 / 64 | implemented, not hardware-verified / 已实现，未实机验证 |
| `0577` | Razer BlackShark V3 Pro receiver | 64-byte output | 2 / 64 | implemented, not hardware-verified / 已实现，未实机验证 |
| `101B` | BlackShark V3 Pro 2.4 GHz dongle | 64-byte output | 2 / 64 | implemented, not hardware-verified / 已实现，未实机验证 |
| `101C` | BlackShark V3 Pro USB | 64-byte output | 2 / 64 | implemented, not hardware-verified / 已实现，未实机验证 |

Evidence lives in `razer_hid/data/devices.json`; the 451-row transport table is
in [`transport-table.md`](transport-table.md). Do not infer a transport from a
bundle name; the report id and frame shape must match.

证据在 `razer_hid/data/devices.json`；451 行全量传输表见
[`transport-table.md`](transport-table.md)。不要根据 bundle 名称猜传输；
report id 和帧形状必须对得上。

`0565` and `056E` are BlackShark V2 HyperSpeed devices on `billie64`, not the
protocol 64 envelope above.

`0565` 和 `056E` 是 BlackShark V2 HyperSpeed，使用 `billie64`，
不是上面的协议 64 帧。

Hardware note: on 2026-11-16 the 00B8 dongle answered `00:BF` (`wireless link
status`, size `0x50`) with status `0x02`. Battery/DPI/polling returned `0x04`
while the mouse was asleep or off. No write was attempted.

实机说明：2026-11-16，00B8 dongle 的 `00:BF`（无线链路状态，长度 `0x50`）
返回 `status 0x02`；鼠标休眠/关闭时，电量、DPI 和轮询率读取返回 `0x04`。
没有发送写命令。精确记录见 [`hardware-validation.md`](hardware-validation.md)。
