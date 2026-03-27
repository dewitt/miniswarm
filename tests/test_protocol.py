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

    def test_parse_message_brackets(self):
        line = "TASK @all scope:[sdk|impl|test] files:[scripts/runner.py, AGENTS.md, tests/] — Add tests for protocol helper."
        result = protocol.parse_message(line)
        self.assertEqual(result["prefix"], "TASK")
        self.assertEqual(result["mentions"], ["all"])
        self.assertEqual(result["scope"], "sdk|impl|test")
        self.assertEqual(result["files"], ["scripts/runner.py", "AGENTS.md", "tests/"])
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

    def test_parse_message_no_body(self):
        line = "STATUS @all scope:test files:tests/test_protocol.py"
        result = protocol.parse_message(line)
        self.assertEqual(result["prefix"], "STATUS")
        self.assertEqual(result["body"], "")

    def test_parse_message_empty_body_with_separator(self):
        line = "DONE @all — "
        result = protocol.parse_message(line)
        self.assertEqual(result["prefix"], "DONE")
        self.assertEqual(result["body"], "")

    def test_parse_message_invalid_prefix(self):
        line = "task @all — lowercase"
        result = protocol.parse_message(line)
        self.assertEqual(result["prefix"], "")

    def test_parse_message_multiple_dashes(self):
        line = "TASK @all — body part 1 — body part 2"
        result = protocol.parse_message(line)
        self.assertEqual(result["prefix"], "TASK")
        self.assertEqual(result["body"], "body part 1 — body part 2")

    def test_parse_message_mentions_only(self):
        line = "QUESTION @dewitt @claude — Should we continue?"
        result = protocol.parse_message(line)
        self.assertEqual(result["prefix"], "QUESTION")
        self.assertEqual(result["mentions"], ["dewitt", "claude"])
        self.assertEqual(result["body"], "Should we continue?")

    def test_parse_message_no_metadata(self):
        line = "HELLO — Joining swarm"
        result = protocol.parse_message(line)
        self.assertEqual(result["prefix"], "HELLO")
        self.assertEqual(result["mentions"], [])
        self.assertEqual(result["scope"], "")
        self.assertEqual(result["files"], [])
        self.assertEqual(result["body"], "Joining swarm")

if __name__ == '__main__':
    unittest.main()
