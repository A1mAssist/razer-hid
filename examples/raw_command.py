"""Inspect a raw frame without opening a device."""

from razer_hid.transport.hid25 import build_request


def main() -> None:
    frame = build_request(
        transaction_id=0x1F,
        data_size=2,
        command_class=0x07,
        command_id=0x80,
        report_id=0,
    )
    print(len(frame), frame.hex(" "))


if __name__ == "__main__":
    main()
