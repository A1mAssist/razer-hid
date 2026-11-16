# razer-hid

[English](README.md) | [简体中文](README.zh-CN.md)

Razer HID 2.5/3.0/64 字节协议参考客户端、传输表与命令/载荷数据库。

这是一个以互操作性为优先的静态协议包。它把帧布局、设备传输表、命令身份表
和参考客户端放在一起，让你不必为同一组字节再做一次逆向。

> 状态：v0.2。没有完整的实机验证；目前只记录了 00B8 的一次无线链路读取。
> 所有设备行仍是 `verified: false`。写命令可能改变设备状态，请先读
> [`SAFETY.md`](SAFETY.md)。

## 包含什么

- 协议 2.5：91 字节 feature report、XOR 校验、事务号、busy/retry，
  以及 DPI 阶段等需要超长参数的命令。
- 协议 3.0：8 字节请求头、24 位小端长度、20/8 字节响应解析，以及可选的
  BLE GATT 传输。
- 协议 64：BlackShark V3 Pro 的 64 字节 report-id-2 帧、唤醒序列、
  事务/校验验证、busy/resend 重试，以及耳机侧的 typed helpers。
- **158,975 条命令身份事实**，覆盖 **336 个 PID**：class、command、
  声明长度、名称、方向、declared/called 标记、置信度、来源层和传输置信度。
- **451 行传输表**：记录 report id、report size、连接方式、证据和置信度，
  覆盖 HID 2.5、HID 3.0、64 字节耳机变体、BLE、原生和外部设备。
  其中 2 个 PID 仍明确标为 `unknown`。
- **130,673 条载荷模板**：常量、调用参数、缓冲区、索引字段、push 序列、
  有序帧、全零缓冲区和无载荷命令。当前快照没有无法解析的模板。
- typed helpers：电量、充电、轮询率、亮度、DPI、Chroma 效果、无线链路，
  以及 BlackShark 的 sidetone、THX、ANC 和游戏/聊天平衡。
- CLI：`list`、`probe`、`read`、`raw --dry-run`。
- 文档：`docs/protocol-25.md`、`docs/protocol-30.md`、
  `docs/protocol-64.md`、`docs/transport-table.md`、
  `docs/payload-templates.md`、`docs/device-table.md`。

公开数据只包含协议事实、规范化后的短表达式和固定帧字节。不包含厂商
JavaScript、压缩 bundle、安装包、固件、图片或 Chroma 资产。

## 安装

```powershell
git clone https://github.com/A1mAssist/razer-hid.git
cd razer-hid
python -m pip install -e .

# 可选：安装 BLE 依赖
python -m pip install -e ".[ble]"
```

也可以从 [Releases](https://github.com/A1mAssist/razer-hid/releases/latest)
下载 wheel。`hidapi` 是核心依赖，`bleak` 只在 BLE 场景需要。
如果 `razerctl` 不在 `PATH`，可以用 `python -m razer_hid.cli`。

## 快速开始

```python
from razer_hid import RazerDevice

with RazerDevice.open("00B8") as device:
    print(device.read_battery())      # BatteryStatus(percent=..., raw=...)
    print(device.read_dpi())          # Dpi(x=..., y=...)
    device.set_dpi(800, 800)
    print(device.read_polling())      # 1000 / 500 / ...
```

没有 typed helper 的命令可以用 `send_raw` / `read_raw` 发送。命令库能查到
class、command 和声明长度：

```python
from razer_hid import CommandDb, PayloadDb

commands = CommandDb.load()
for command in commands.find("00B8", "Get Battery Level"):
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

# 不打开设备，只检查生成的帧
razerctl raw 00B8 07 80 --dry-run

# 协议 30
razerctl raw 00B8 0B 01 0102 --transport hid30 --transaction-id 3 --dry-run

# 原始写命令必须显式确认
razerctl raw 00B8 04 05 0003200320 --allow-writes
```

class 和 command 参数按十六进制解析（`07`、`0B`、`0x80`）；
payload 可以带空格，也可以连续写。

## 设备支持情况

完整设备列表（PID、产品、传输、Report、状态）见
[`docs/device-table.md`](docs/device-table.md)。451 行全量证据表见
[`docs/transport-table.md`](docs/transport-table.md)；机器可读数据在
`razer_hid/data/transports.json` 和 `razer_hid/data/devices.json`。

`0565` 和 `056E` 是 BlackShark V2 HyperSpeed，使用 `billie64`，
不是上面的协议 64 帧。

未列出的 PID 仍可以用
`RazerDevice.open(pid, transport="hid25", report_id=...)` 或
`razerctl probe` 尝试。00B8 的实机读取记录见
[`docs/hardware-validation.md`](docs/hardware-validation.md)。

## 命令数据库

`razer_hid/data/commands.jsonl.gz` 是 gzip JSONL。每行包含：

```text
pid product transport direction class command dataSize dataSizeVariants
name declared called confidence sourceLayer payloadSchema libraryDefined
callReference sourceBundle transportConfidence
```

- `declared`：该三元组出现在产品命令表中。
- `called`：处理器实际调用了它；`libraryDefined` 表示定义来自共享库，
  不是产品自己的表。
- `confidence`：`source-backed` 或 `inferred`，不会写成 `verified`。
- `payloadSchema`：来源中带有规范化标签时才有值。
- `transportConfidence`：来自独立传输表的 `verified`、`evidenced`、
  `family-inferred` 或 `unknown`。

生成的统计在 `razer_hid/data/commands.index.json`。

## 载荷模板

`razer_hid/data/payloads.jsonl.gz` 是请求/响应模板数据库，按 PID、class、
command 和可选名称索引：

```python
from razer_hid import PayloadDb

db = PayloadDb.load()
template = db.for_command("0309", 4, 0, "Get Link Status")
print(template.kind)                 # constant
print(template.build().hex())        # fe00040f0581aac6

for frame in template.build_frames():
    print(frame.hex())
```

单帧模板用 `build()` 取字节；多帧命令用 `build_frames()` 取有序帧列表。
编译器会从 bundle 中解析 `i.pu` 这类共享模块导出的固定 `Uint8Array` 帧，
但不会执行 bundle，也不会把压缩符号名写进公开数据。详细 schema 和边界见
`docs/payload-templates.md`。

## 不包含什么

- 没有完整实机验证；所有设备行仍是 `verified: false`。已记录的 00B8
  无线链路读取不等于整机验证。
- BLE 仍然是异步实验路径；同步 `RazerDevice` 不会打开 BLE 设备，
  需要直接用 `razer_hid.transport.ble30` 和地址连接。
- BlackShark V3 Pro 的协议 64 已实现；其他 64 字节耳机格式
  （`billie64`、`valkyrie64`、`valkyrie-t3-64`、`mxic64`、`jolie64`、
  `avnera65`、`kraken37`、`hid25-64/65`、`mixer053e`、`protocol40`）
  只登记在传输表中，没有 typed transport。
- 传输表中 `0A23` 和 `053C` 缺少产品级传输证据，因此保留为 `unknown`，
  没有强行归到 HID 2.5。
- 不发布原始厂商表达式或厂商代码。需要某个命令的 typed payload 时，
  在 `razer_hid/data/schemas/` 下补一个经过审查的 schema。

## 许可证与来源

- 代码：MIT（`LICENSE`）。
- 文档和协议数据：CC BY 4.0（`LICENSE-docs`）。
- 来源与排除材料：`NOTICE.md`、`docs/provenance.md`。
- Razer、Chroma 及相关商标归 Razer Inc. 所有；本项目与 Razer 无隶属关系。

## 开发

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python tools/audit_public_tree.py
```

从本地 OpenSynapse 快照重新生成数据：

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
