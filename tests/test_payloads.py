import gzip
import json
import tempfile
import unittest
from pathlib import Path

from tools.compile_payloads import (
    compile_payload,
    evaluate,
    normalize_expression,
    normalize_json_data,
    scan_module_exports,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "razer_hid/data/payloads.jsonl.gz"
SCHEMA = ROOT / "razer_hid/data/schemas/payload.schema.json"


class PayloadCompilerTests(unittest.TestCase):
    def test_constant(self):
        self.assertEqual(compile_payload(["0"], 1)["bytes"], [0])
        self.assertEqual(
            compile_payload(["1", "2", "0xFF"], 3)["bytes"], [1, 2, 255]
        )

    def test_constant_fold(self):
        value, source, literal = normalize_expression("1+2*3")
        self.assertEqual((value, source, literal), ("7", "literal", 7))
        value, source, literal = normalize_expression("n>>8&255")
        self.assertEqual(source, "computed")
        self.assertIsNone(literal)
        self.assertIn("n", value)

    def test_number_and_member_access(self):
        value, source, literal = normalize_expression("Number(t)")
        self.assertEqual((value, source, literal), ("Number(t)", "computed", None))
        value, source, _ = normalize_expression("u.keyNum")
        self.assertEqual((value, source), ("u.keyNum", "computed"))
        value, source, _ = normalize_expression("t")
        self.assertEqual((value, source), ("t", "arg"))

    def test_indexed(self):
        row = compile_payload(["p[0]=Number(t)", "p[1]=u.keyNum"], 2)
        self.assertEqual(row["kind"], "indexed")
        self.assertEqual(row["length"], 2)
        self.assertEqual(row["fields"][0]["index"], 0)
        self.assertEqual(row["fields"][0]["source"], "computed")
        self.assertEqual(row["fields"][1]["expression"], "u.keyNum")

    def test_argument_and_buffer(self):
        self.assertEqual(compile_payload(["t"], 4)["kind"], "argument")
        row = compile_payload(["new Uint8Array(l)"], 9)
        self.assertEqual(row["kind"], "buffer")
        self.assertEqual(row["argument"], "l")
        self.assertEqual(row["length"], 9)

    def test_zero_and_none(self):
        self.assertEqual(compile_payload(["n=new Uint8Array(80)"], 80)["kind"], "zero")
        self.assertEqual(compile_payload([], 0)["kind"], "none")

    def test_alloc_then_writes(self):
        row = compile_payload(
            ["a=new Uint8Array(5)", "a[1]=n>>8&255", "a[2]=255&n"], 5
        )
        self.assertEqual(row["kind"], "indexed")
        self.assertEqual(row["length"], 5)
        self.assertEqual(row["fields"][0]["index"], 1)
        self.assertEqual(row["fields"][1]["index"], 2)

    def test_length_accessor(self):
        row = compile_payload(["i.length"], 0)
        self.assertEqual(row["kind"], "argument")
        self.assertEqual(row["argument"], "i")
        self.assertEqual(row["length"], 0)

    def test_json_data(self):
        rows = normalize_json_data(
            [{"field": "major", "expression": "t.data[0]"}]
        )
        self.assertEqual(rows[0]["field"], "major")
        self.assertEqual(rows[0]["expression"], "t.data[0]")
        self.assertEqual(rows[0]["source"], "computed")

    def test_module_export_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "module.js"
            path.write_text(
                "r.d(t,{pu:()=>C});"
                "const C=[new Uint8Array([1,2]),new Uint8Array([3])]",
                encoding="utf-8",
            )
            exports = scan_module_exports([path])
        row = compile_payload(["i.pu"], 4, exports)
        self.assertEqual(row["kind"], "frames")
        self.assertEqual(row["frames"], [[1, 2], [3]])

    def test_ambiguous_module_symbol_is_not_resolved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "module.js"
            path.write_text(
                "r.d(t,{pu:()=>C});"
                "const C=[new Uint8Array([1])];"
                "C=[new Uint8Array([2])]",
                encoding="utf-8",
            )
            exports = scan_module_exports([path])
        self.assertNotIn("pu", exports)


class PayloadDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = []
        with gzip.open(DATA, "rt", encoding="utf-8") as handle:
            for line in handle:
                cls.rows.append(json.loads(line))

    def test_coverage_and_kinds(self):
        self.assertGreater(len(self.rows), 125000)
        kinds = {row["kind"] for row in self.rows}
        self.assertTrue(
            {"constant", "argument", "buffer", "indexed", "none", "zero"} <= kinds
        )
        self.assertEqual(
            sum(1 for row in self.rows if row["kind"] == "unknown"), 0
        )

    def test_public_data_has_no_vendor_paths(self):
        text = DATA.read_bytes()
        decompressed = gzip.decompress(text).decode("utf-8")
        self.assertNotIn("D:\\", decompressed)
        self.assertNotIn("C:\\", decompressed)
        self.assertNotIn(".js", decompressed)
        self.assertNotIn("bundle", decompressed.lower())

    def test_schema_sample(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        sample = self.rows[0]
        try:
            import jsonschema  # type: ignore
        except ImportError:
            for key in schema["required"]:
                self.assertIn(key, sample)
            return
        jsonschema.validate(sample, schema)


if __name__ == "__main__":
    unittest.main()
