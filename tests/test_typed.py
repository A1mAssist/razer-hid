import unittest

from razer_hid.payloads import battery, brightness, dpi, effect, link, polling
from razer_hid.transport.base import Response


class FakeDevice:
    def __init__(self, response: Response):
        self.response = response
        self.calls = []

    def send_raw(self, command_class, command_id, payload=b"", **kwargs):
        self.calls.append((command_class, command_id, payload, kwargs))
        return self.response


def success(arguments: bytes = b"") -> Response:
    return Response(
        raw=b"",
        status=2,
        transaction_id=0,
        command_class=0,
        command_id=0,
        data_size=len(arguments),
        arguments=arguments,
    )


class TypedPayloadTests(unittest.TestCase):
    def test_battery(self):
        device = FakeDevice(success(b"\x01\x80"))
        self.assertEqual(battery.read(device).percent, 50)
        self.assertTrue(battery.read_charging(FakeDevice(success(b"\x00\x01"))))

    def test_polling(self):
        device = FakeDevice(success(b"\x02"))
        self.assertEqual(polling.read(device), 500)
        polling.set(device, 1000)
        self.assertEqual(device.calls[-1][2], b"\x01")

    def test_brightness(self):
        device = FakeDevice(success(b"\x80"))
        self.assertEqual(brightness.read(device), 50)
        brightness.set(device, 50)
        self.assertEqual(device.calls[-1][2], bytes([128]))

    def test_dpi(self):
        device = FakeDevice(success(b"\x00\x03\x20\x03\x20"))
        self.assertEqual(dpi.read(device), dpi.Dpi(800, 800))
        dpi.set(device, 800, 800)
        self.assertEqual(device.calls[-1][2], b"\x00\x03\x20\x03\x20")

    def test_effect(self):
        device = FakeDevice(success(b"\x01\x00\x00\x01\xFF\x00\x00"))
        state = effect.get(device)
        self.assertEqual(state.effect, 1)
        self.assertEqual(state.colors, ((255, 0, 0),))
        effect.set(device, 1, [(255, 0, 0)])
        self.assertEqual(device.calls[-1][2], b"\x01\x00\x00\x01\xff\x00\x00")

    def test_wireless_link(self):
        device = FakeDevice(success(b"\x02\x00\x00\xB8"))
        status = link.read(device)
        self.assertEqual(status.raw, b"\x02\x00\x00\xB8")


if __name__ == "__main__":
    unittest.main()
