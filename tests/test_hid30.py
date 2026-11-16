import unittest

from razer_hid.transport.base import TransportError
from razer_hid.transport.hid30 import build_request, parse_response


class Hid30FrameTests(unittest.TestCase):
    def test_request_layout(self):
        request = build_request(3, 0x0B, 0x01, b"\x01\x02")
        self.assertEqual(
            request,
            bytes([3, 2, 0, 0, 0x0B, 0x01, 0, 0, 0x01, 0x02]),
        )

    def test_20_byte_header_response(self):
        request = build_request(3, 0x0B, 0x01, b"\x01\x02")
        response = bytearray(20 + 2)
        response[0] = 3
        response[1] = 2
        response[4] = 0x0B
        response[5] = 0x01
        response[7] = 0x02
        response[20:] = b"\xAA\xBB"
        parsed = parse_response(request, bytes(response))
        self.assertTrue(parsed.ok)
        self.assertEqual(parsed.arguments, b"\xAA\xBB")

    def test_8_byte_header_response(self):
        request = build_request(5, 0x10, 0x85, b"")
        response = bytearray(8 + 1)
        response[0] = 5
        response[1] = 1
        response[4] = 0x10
        response[5] = 0x85
        response[7] = 0x02
        response[8] = 0x80
        parsed = parse_response(request, bytes(response))
        self.assertTrue(parsed.ok)
        self.assertEqual(parsed.arguments, b"\x80")

    def test_bad_status_and_command(self):
        request = build_request(3, 0x0B, 0x01, b"")
        response = bytearray(20)
        response[0] = 3
        response[4] = 0x0B
        response[5] = 0x01
        response[7] = 0x01
        self.assertFalse(parse_response(request, bytes(response)).ok)

        response[5] = 0x02
        with self.assertRaises(TransportError):
            parse_response(request, bytes(response))

    def test_transaction_limit(self):
        with self.assertRaises(ValueError):
            build_request(32, 0x0B, 0x01, b"")


if __name__ == "__main__":
    unittest.main()
