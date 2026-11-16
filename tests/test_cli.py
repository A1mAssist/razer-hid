import contextlib
import io
import unittest

from razer_hid.cli import main


class CliTests(unittest.TestCase):
    def test_hid25_dry_run(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["raw", "00B8", "07", "80", "--dry-run"])
        self.assertEqual(code, 0)
        text = output.getvalue()
        self.assertIn("91 bytes", text)
        self.assertIn("85", text)

    def test_hid30_dry_run(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(
                [
                    "raw",
                    "00B8",
                    "0B",
                    "01",
                    "0102",
                    "--transport",
                    "hid30",
                    "--transaction-id",
                    "3",
                    "--dry-run",
                ]
            )
        self.assertEqual(code, 0)
        self.assertIn("10 bytes", output.getvalue())

    def test_hid64_dry_run(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(
                ["raw", "0576", "21", "00", "--transport", "hid64", "--dry-run"]
            )
        self.assertEqual(code, 0)
        text = output.getvalue()
        self.assertIn("64 bytes", text)
        self.assertIn("02 00 60", text)

    def test_raw_requires_allow_writes(self):
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            code = main(["raw", "00B8", "07", "80"])
        self.assertEqual(code, 2)
        self.assertIn("--allow-writes", error.getvalue())


if __name__ == "__main__":
    unittest.main()
