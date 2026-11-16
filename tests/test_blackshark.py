import unittest

from razer_hid.payloads import blackshark
from razer_hid.transport.base import Response


class FakeDevice:
    def __init__(self, arguments: bytes):
        self.arguments = arguments
        self.calls = []

    def send_raw(self, command_class, command_id, payload=b"", **kwargs):
        self.calls.append((command_class, command_id, payload))
        return Response(
            raw=b"",
            status=2,
            transaction_id=0,
            command_class=command_class,
            command_id=command_id,
            data_size=len(self.arguments),
            arguments=self.arguments,
        )


class BlackSharkPayloadTests(unittest.TestCase):
    def test_battery_uses_first_argument_as_percent(self):
        status = blackshark.read_battery(FakeDevice(b"\x57"))
        self.assertEqual(status.percent, 87)

    def test_charging(self):
        self.assertTrue(blackshark.read_charging(FakeDevice(b"\x01")))
        self.assertFalse(blackshark.read_charging(FakeDevice(b"\x00")))

    def test_sidetone(self):
        device = FakeDevice(b"\x07")
        self.assertEqual(blackshark.get_sidetone(device), 7)
        blackshark.set_sidetone(device, 7)
        self.assertEqual(device.calls[-1], (0x99, 0x01, b"\x07"))
        with self.assertRaises(ValueError):
            blackshark.set_sidetone(device, 16)

    def test_thx(self):
        device = FakeDevice(b"\x01")
        self.assertTrue(blackshark.get_thx(device))
        blackshark.set_thx(device, False)
        self.assertEqual(device.calls[-1], (0x9E, 0x01, b"\x00"))

    def test_anc(self):
        device = FakeDevice(b"\x01\x03")
        status = blackshark.get_anc(device)
        self.assertEqual(status.mode, blackshark.AncMode.ANC)
        self.assertEqual(status.level, 3)

        blackshark.set_anc(device, blackshark.AncMode.ANC, 9)
        self.assertEqual(device.calls[-1], (0x92, 0x02, b"\x01\x04"))
        blackshark.set_anc(device, blackshark.AncMode.AMBIENT, 4)
        self.assertEqual(device.calls[-1], (0x92, 0x02, b"\x50\x01"))
        blackshark.set_anc(device, blackshark.AncMode.OFF, 4)
        self.assertEqual(device.calls[-1], (0x92, 0x02, b"\x00\x00"))

    def test_game_chat_balance_is_inverted(self):
        device = FakeDevice(b"\x05")
        self.assertEqual(blackshark.get_game_chat(device), 15)
        blackshark.set_game_chat(device, 20)
        self.assertEqual(device.calls[-1], (0xDC, 0x01, b"\x00"))
        with self.assertRaises(ValueError):
            blackshark.set_game_chat(device, 21)


if __name__ == "__main__":
    unittest.main()
