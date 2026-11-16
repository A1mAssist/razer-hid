import json
import unittest
from pathlib import Path


DATA = Path(__file__).resolve().parents[1] / "razer_hid/data/transports.json"
ALLOWED_TRANSPORT = {
    "hid25",
    "hid25-64",
    "hid25-65",
    "hid30",
    "hid64",
    "ble30",
    "ble-audio",
    "mxic64",
    "valkyrie64",
    "valkyrie-t3-64",
    "billie64",
    "jolie64",
    "kraken37",
    "avnera65",
    "mixer053e",
    "protocol40",
    "external",
    "native",
    "unknown",
    "multi",
}
ALLOWED_CONFIDENCE = {"verified", "evidenced", "family-inferred", "unknown"}
ALLOWED_CONNECTION = {"usb", "wireless", "ble", "unknown"}


class TransportTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(DATA.read_text(encoding="utf-8"))
        cls.rows = {row["pid"]: row for row in cls.data["devices"]}

    def test_counts_and_values(self):
        self.assertGreaterEqual(len(self.rows), 338)
        for row in self.rows.values():
            self.assertIn(row["transport"], ALLOWED_TRANSPORT)
            self.assertIn(row["confidence"], ALLOWED_CONFIDENCE)
            self.assertIn(row["connection"], ALLOWED_CONNECTION)
            if row["transport"] != "unknown":
                self.assertTrue(row["evidence"], row["pid"])

    def test_only_00b8_is_verified(self):
        verified = [row["pid"] for row in self.rows.values() if row["confidence"] == "verified"]
        self.assertEqual(verified, ["00B8"])

    def test_named_rows(self):
        self.assertEqual(self.rows["0576"]["transport"], "hid64")
        self.assertEqual(self.rows["101C"]["transport"], "hid64")
        self.assertEqual(self.rows["00E5"]["transport"], "ble30")
        for pid in ("0046", "00B8", "028D", "00A4", "054A", "0A45"):
            self.assertEqual(self.rows[pid]["transport"], "hid25")
        self.assertEqual(self.rows["0301"]["transport"], "external")
        self.assertEqual(self.rows["0A22"]["transport"], "native")

    def test_no_local_paths(self):
        text = DATA.read_text(encoding="utf-8")
        self.assertNotIn("D:\\", text)
        self.assertNotIn("C:\\", text)


if __name__ == "__main__":
    unittest.main()
