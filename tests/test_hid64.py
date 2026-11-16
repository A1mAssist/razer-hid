import unittest

from razer_hid.transport.base import TransportError
from razer_hid.transport.hid64 import (
    REPORT_LENGTH,
    Hid64Transport,
    build_request,
    parse_response,
    xor_checksum,
)


def make_response(
    request: bytes,
    status: int = 2,
    subtype: int = 1,
    arguments: bytes = b"\x64",
) -> bytes:
    response = bytearray(REPORT_LENGTH)
    response[0] = request[0]
    response[1] = status
    response[2] = request[2]
    response[10] = request[10]
    response[11] = subtype
    response[12] = len(arguments)
    response[13 : 13 + len(arguments)] = arguments
    response[62] = xor_checksum(response)
    return bytes(response)


class FakeHid:
    def __init__(self, statuses=(2,), subtype: int = 1, arguments: bytes = b"\x64"):
        self.writes = []
        self.statuses = list(statuses)
        self.subtype = subtype
        self.arguments = arguments

    def write(self, frame: bytes) -> int:
        self.writes.append(bytes(frame))
        return len(frame)

    def read(self, size: int, timeout_ms: int) -> bytes:
        if size != REPORT_LENGTH:
            raise AssertionError(f"unexpected read size {size}")
        status = self.statuses.pop(0) if self.statuses else 2
        return make_response(
            self.writes[-1], status=status, subtype=self.subtype, arguments=self.arguments
        )

    def close(self) -> None:
        pass


class Hid64FrameTests(unittest.TestCase):
    def test_layout_wired_and_wireless(self):
        wired = build_request(0x21, 0x00, b"\x01\x02", wireless=False)
        wireless = build_request(0x21, 0x00, b"\x01\x02", wireless=True)
        self.assertEqual(len(wired), REPORT_LENGTH)
        self.assertEqual(wired[0], 0x02)
        self.assertEqual(wired[2], 0x60)
        self.assertEqual(wired[6], 6)
        self.assertEqual(wired[9], 0x00)
        self.assertEqual(wired[10], 0x21)
        self.assertEqual(wired[11], 0x00)
        self.assertEqual(wired[12], 0x00)
        self.assertEqual(wired[13:15], b"\x01\x02")
        self.assertEqual(wireless[9], 0x80)
        self.assertEqual(wired[62], xor_checksum(wired))
        self.assertEqual(wired[63], 0)

    def test_argument_limit(self):
        build_request(0x21, 0x00, bytes(49))
        with self.assertRaises(ValueError):
            build_request(0x21, 0x00, bytes(50))

    def test_success_response(self):
        request = build_request(0x21, 0x00)
        response = parse_response(make_response(request, arguments=b"\x5A"), request)
        self.assertTrue(response.ok)
        self.assertEqual(response.status, 2)
        self.assertEqual(response.subtype, 1)
        self.assertEqual(response.command_class, 0x21)
        self.assertEqual(response.arguments, b"\x5A")

    def test_63_byte_read(self):
        request = build_request(0x21, 0x00)
        raw = make_response(request, arguments=b"\x5A")[1:]
        response = parse_response(raw, request)
        self.assertTrue(response.ok)
        self.assertEqual(response.raw[0], 0x02)

    def test_subtype_rejected(self):
        request = build_request(0x21, 0x00)
        response = parse_response(make_response(request, subtype=0), request)
        self.assertTrue(response.checksum_ok)
        self.assertFalse(response.ok)
        with self.assertRaises(TransportError):
            response.require_ok()

    def test_bad_checksum(self):
        request = build_request(0x21, 0x00)
        raw = bytearray(make_response(request))
        raw[62] ^= 0xFF
        response = parse_response(bytes(raw), request)
        self.assertFalse(response.checksum_ok)
        self.assertFalse(response.ok)

    def test_transaction_and_class_mismatch(self):
        request = build_request(0x21, 0x00)
        raw = bytearray(make_response(request))
        raw[2] = 0x61
        raw[62] = xor_checksum(raw)
        with self.assertRaises(TransportError):
            parse_response(bytes(raw), request)

        raw = bytearray(make_response(request))
        raw[10] = 0x2A
        raw[62] = xor_checksum(raw)
        with self.assertRaises(TransportError):
            parse_response(bytes(raw), request)

    def test_wake_sequence_and_exchange(self):
        fake = FakeHid(arguments=b"\x64")
        transport = Hid64Transport(fake, wireless=False)
        response = transport.exchange(0x21, 0x00)
        self.assertTrue(response.ok)
        self.assertEqual(len(fake.writes), 4)
        self.assertEqual(
            [(frame[10], frame[9]) for frame in fake.writes[:3]],
            [(0x02, 0x00), (0x2A, 0x00), (0x2A, 0x80)],
        )
        self.assertEqual((fake.writes[3][10], fake.writes[3][9]), (0x21, 0x00))

        # The wake sequence is sent once per transport instance.
        transport.exchange(0x2A, 0x00)
        self.assertEqual(len(fake.writes), 5)

    def test_resend_then_success(self):
        fake = FakeHid(statuses=(3, 2), arguments=b"\x64")
        transport = Hid64Transport(fake, wireless=True)
        response = transport.exchange(0x21, 0x00)
        self.assertTrue(response.ok)
        self.assertEqual(len(fake.writes), 5)


if __name__ == "__main__":
    unittest.main()
