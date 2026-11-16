"""Read battery and DPI from a supported mouse."""

from razer_hid import RazerDevice


def main() -> None:
    with RazerDevice.open("00B8") as device:
        print(device.read_battery())
        print(device.read_dpi())
        print(device.read_polling())


if __name__ == "__main__":
    main()
