import gzip
import json
import unittest

from razer_hid.commands import CommandDb


class CommandDbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = CommandDb.load()

    def test_database_is_large_and_indexed(self):
        self.assertGreater(len(self.db), 150000)
        self.assertTrue(self.db.by_pid("00B8"))

    def test_known_battery_command(self):
        rows = self.db.get("00B8", 0x07, 0x80)
        self.assertTrue(rows)
        self.assertGreater(rows[0].data_size, 0)

    def test_public_rows_have_no_extracted_expressions(self):
        with gzip.open(
            "razer_hid/data/commands.jsonl.gz", "rt", encoding="utf-8"
        ) as handle:
            row = json.loads(next(handle))
        for key in ("payload", "jsonData", "evidence", "implemented", "methods"):
            self.assertNotIn(key, row)


if __name__ == "__main__":
    unittest.main()
