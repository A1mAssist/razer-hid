import unittest

from razer_hid.transport.base import TransportError
from razer_hid.transport.hid25 import (
    REPORT_LENGTH,
    build_request,
    parse_response,
    xor_checksum,
)


def make_response(request: bytes, status: int = 2, arguments: bytes = b"\x00\x80") -> bytes:
    response = bytearray(request)
    response[1] = status
    response[6] = len(arguments)
    response[9 : 9 + len(arguments)] = arguments
    response[89] = xor_checksum(response)
    return bytes(response)


class Hid25FrameTests(unittest.TestCase):
    def test_layout_and_checksum(self):
        request = build_request(0x1F, 2, 0x07, 0x80)
        self.assertEqual(len(request), REPORT_LENGTH)
        self.assertEqual(request[0], 0)
        self.assertEqual(request[2], 0x1F)
        self.assertEqual(request[6], 2)
        self.assertEqual(request[7], 0x07)
        self.assertEqual(request[8], 0x80)
        self.assertEqual(request[89], 0x02 ^ 0x07 ^ 0x80)
        self.assertEqual(request[90], 0)

    def test_arguments_and_oversize(self):
        request = build_request(1, 5, 0x04, 0x05, b"\x00\x03\x20\x03\x20")
        self.assertEqual(request[6], 5)
        self.assertEqual(request[9:14], b"\x00\x03\x20\x03\x20")
        with self.assertRaises(ValueError):
            build_request(1, 2, 0x04, 0x05, b"\x00\x03\x20\x03\x20")
        build_request(1, 2, 0x04, 0x05, b"\x00\x03\x20\x03\x20", allow_oversize=True)

    def test_success_response(self):
        request = build_request(0x1F, 2, 0x07, 0x80)
        response = parse_response(make_response(request), request)
        self.assertTrue(response.ok)
        self.assertEqual(response.arguments, b"\x00\x80")
        self.assertEqual(response.command_class, 0x07)
        self.assertEqual(response.command_id, 0x80)

    def test_busy_and_bad_checksum(self):
        request = build_request(0x1F, 2, 0x07, 0x80)
        busy = parse_response(make_response(request, status=1), request)
        self.assertFalse(busy.ok)
        corrupt = bytearray(make_response(request))
        corrupt[89] ^= 0xFF
        bad = parse_response(bytes(corrupt), request)
        self.assertFalse(bad.ok)
        self.assertFalse(bad.checksum_ok)

    def test_transaction_mismatch(self):
        request = build_request(0x1F, 2, 0x07, 0x80)
        response = bytearray(make_response(request))
        response[2] = 0x1E
        response[89] = xor_checksum(response)
        with self.assertRaises(TransportError):
            parse_response(bytes(response), request)

    def test_wildcard_transaction(self):
        request = build_request(0xFF, 2, 0x07, 0x80)
        response = bytearray(make_response(request))
        response[2] = 0x1F
        response[89] = xor_checksum(response)
        parsed = parse_response(bytes(response), request)
        self.assertTrue(parsed.ok)

    def test_transaction_checksum_variant(self):
        request = build_request(0x07, 2, 0x07, 0x80)
        response = bytearray(make_response(request))
        response[89] = xor_checksum(response, include_transaction=True)
        parsed = parse_response(
            bytes(response), request, accept_transaction_checksum=True
        )
        self.assertTrue(parsed.ok)


if __name__ == "__main__":
    unittest.main()
