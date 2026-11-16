"""Offline privacy checks for Ho-Smart diagnostics."""
import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "custom_components/hosmart/debug.py"
TREE = ast.parse(SOURCE.read_text(encoding="utf-8"))
FUNCTION = next(node for node in TREE.body if isinstance(node, ast.FunctionDef) and node.name == "redact")
NAMESPACE = {"Any": object, "_SENSITIVE_KEYS": {"password", "access_token", "pop", "user_id"}}
exec(compile(ast.Module(body=[FUNCTION], type_ignores=[]), str(SOURCE), "exec"), NAMESPACE)
redact = NAMESPACE["redact"]

class DebugPrivacyTests(unittest.TestCase):
    def test_binary_payload_never_exported_as_hex(self):
        result = redact({"frame": b"PRIVATE_DATA", "nested": [{"password": "secret"}]})
        self.assertEqual(result["frame"], {"length": 12, "redacted": "binary_payload"})
        self.assertNotIn("PRIVATE_DATA", repr(result))
        self.assertEqual(result["nested"][0]["password"], "<redacted>")

if __name__ == "__main__":
    unittest.main()
