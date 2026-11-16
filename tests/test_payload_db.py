import unittest

from razer_hid.payload_db import PayloadDb


class PayloadDbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = PayloadDb.load()

    def test_database_is_large(self):
        self.assertGreater(len(self.db), 125000)

    def test_constant_and_zero(self):
        reset = self.db.for_command("0046", 1, 1)
        self.assertEqual(reset.kind, "constant")
        self.assertEqual(reset.build(), b"\x00")

        zero = self.db.for_command("0053", 0, 88)
        self.assertEqual(zero.kind, "zero")
        self.assertEqual(len(zero.build()), 80)

    def test_indexed_argument(self):
        template = self.db.for_command("0046", 0, 86)
        self.assertEqual(template.kind, "indexed")
        self.assertEqual(template.build(n=1), b"\x01")

    def test_indexed_number_and_member(self):
        template = self.db.for_command("0046", 0, 93)
        payload = template.build(
            t=1,
            u={"keyNum": 2, "id1": 3, "id2": 4},
            l={"keyNum": 5, "id1": 6, "id2": 7},
            d={"keyNum": 8, "id1": 9, "id2": 10},
        )
        self.assertEqual(payload[:4], bytes([1, 2, 3, 4]))
        self.assertEqual(payload[4:7], bytes([5, 6, 7]))

    def test_argument_padding(self):
        template = self.db.for_command("00A2", 0, 1)
        self.assertEqual(template.kind, "argument")
        payload = template.build(i=b"\x01")
        self.assertEqual(len(payload), template.length)
        self.assertEqual(payload[:1], b"\x01")

    def test_missing_argument_is_explicit(self):
        template = self.db.for_command("0046", 0, 86)
        with self.assertRaises(ValueError):
            template.build()

    def test_resolved_module_export(self):
        template = self.db.for_command("0309", 4, 0, "Get Link Status")
        self.assertEqual(template.kind, "constant")
        self.assertEqual(
            template.build(), bytes([254, 0, 4, 15, 5, 129, 170, 198])
        )


if __name__ == "__main__":
    unittest.main()
