# Safety

Writing HID commands can put a device into an unexpected state. Some commands
change persistent settings, reset the device, or enter firmware-update modes.

- Reads are the default. The CLI refuses raw writes unless `--allow-writes` is
  passed.
- There is no full hardware verification in this release. One 00B8
  wireless-link read is documented, but a command that is `declared` or
  `called` in the middleware is not proof that a specific firmware accepts it.
- Prefer a read-back before and after every write.
- Do not send firmware-update, bootloader, DFU, or reset commands unless you
  have a recovery path.
- The authors are not responsible for damaged devices or lost settings.
