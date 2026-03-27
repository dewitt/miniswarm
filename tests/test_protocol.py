import unittest
import sys
import os

# Add scripts directory to path to import protocol
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
import protocol

class TestProtocol(unittest.TestCase):
    def test_parse_message_task(self):
        line = "TASK @all scope:test files:tests/test_protocol.py — Add tests for protocol helper."
        result = protocol.parse_message(line)
        self.assertEqual(result["prefix"], "TASK")
        self.assertEqual(result["mentions"], ["all"])
        self.assertEqual(result["scope"], "test")
        self.assertEqual(result["files"], ["tests/test_protocol.py"])
        self.assertEqual(result["body"], "Add tests for protocol helper.")

    def test_parse_message_claim(self):
        line = "CLAIM @claude scope:architecture files:AGENTS.md,scripts/protocol.py — Claiming review."
        result = protocol.parse_message(line)
        self.assertEqual(result["prefix"], "CLAIM")
        self.assertEqual(result["mentions"], ["claude"])
        self.assertEqual(result["scope"], "architecture")
        self.assertEqual(result["files"], ["AGENTS.md", "scripts/protocol.py"])
        self.assertEqual(result["body"], "Claiming review.")

    def test_format_task(self):
        scope = "impl"
        files = ["scripts/protocol.py", "scripts/runner.py"]
        body = "Implement helper."
        formatted = protocol.format_task(scope, files, body)
        self.assertEqual(formatted, "TASK @all scope:impl files:scripts/protocol.py,scripts/runner.py — Implement helper.")

if __name__ == '__main__':
    unittest.main()
