import unittest
import sys
import os
from pathlib import Path

# Add scripts directory to path so we can import runner
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
import runner

class TestRunner(unittest.TestCase):
    def test_load_config_default(self):
        # This might fail if swarm.toml is missing, but it should exist in the repo
        config = runner.load_config("swarm.toml")
        self.assertIn("server", config)
        self.assertIn("agents", config)
        self.assertEqual(config["server"]["port"], 6667)

    def test_is_relevant_mention(self):
        config = {"agents": {"gemini": {"nick": "gemini"}}}
        msg = {
            "type": "PRIVMSG",
            "sender": "dewitt",
            "content": "@gemini what's up?"
        }
        self.assertTrue(runner.is_relevant(msg, "gemini", config))

    def test_is_relevant_lifecycle_ignored(self):
        config = {"agents": {"gemini": {"nick": "gemini"}}}
        msg = {
            "type": "PRIVMSG",
            "sender": "claude",
            "content": "HELLO — claude is here"
        }
        self.assertFalse(runner.is_relevant(msg, "gemini", config))

    def test_format_response_short(self):
        resp = "Hello\nWorld"
        formatted = runner.format_response_for_irc(resp)
        self.assertEqual(formatted, ["Hello", "World"])

    def test_format_response_noise_filtering(self):
        resp = "Hello\n$ ls\nWorld\n```python\nprint('hi')\n```"
        formatted = runner.format_response_for_irc(resp)
        self.assertEqual(formatted, ["Hello", "World", "print('hi')"])

    def test_parse_toml_minimal(self):
        import tempfile
        content = """
[section]
key = "value"
num = 123
flag = true

[agent.test]
nick = "tester"
command = ["test", "-v"]
"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            config = runner._parse_toml_minimal(tmp_path)
            self.assertEqual(config["section"]["key"], "value")
            self.assertEqual(config["section"]["num"], 123)
            self.assertTrue(config["section"]["flag"])
            self.assertEqual(config["agent"]["test"]["nick"], "tester")
            self.assertEqual(config["agent"]["test"]["command"], ["test", "-v"])
        finally:
            os.unlink(tmp_path)

    def test_file_locking(self):
        import shutil
        test_lock_dir = Path("/tmp/swarm-locks-test")
        if test_lock_dir.exists():
            shutil.rmtree(test_lock_dir)
        
        # Patch runner.LOCK_DIR
        old_lock_dir = runner.LOCK_DIR
        runner.LOCK_DIR = test_lock_dir
        try:
            self.assertTrue(runner.acquire_lock("file1", "owner1", ttl_seconds=10))
            self.assertFalse(runner.acquire_lock("file1", "owner2", ttl_seconds=10))
            self.assertEqual(runner.check_lock("file1"), "owner1")
            
            runner.release_lock("file1", "owner1")
            self.assertIsNone(runner.check_lock("file1"))
            self.assertTrue(runner.acquire_lock("file1", "owner2", ttl_seconds=10))
        finally:
            runner.LOCK_DIR = old_lock_dir
            if test_lock_dir.exists():
                shutil.rmtree(test_lock_dir)

    def test_guardrails_rate_limit(self):
        config = {"defaults": {"min_invoke_interval_seconds": 10, "max_invocations_per_hour": 30}}
        gr = runner.Guardrails(config)
        
        allowed, reason = gr.check_rate_limit()
        self.assertTrue(allowed)
        
        gr.record_invocation()
        allowed, reason = gr.check_rate_limit()
        self.assertFalse(allowed)
        self.assertIn("cooldown", reason)

    def test_guardrails_loop_detection(self):
        config = {"defaults": {"loop_detection_threshold": 2}}
        gr = runner.Guardrails(config)
        
        messages = [
            {"sender": "claude", "content": "hi", "type": "PRIVMSG"},
            {"sender": "gemini", "content": "hello", "type": "PRIVMSG"},
            {"sender": "claude", "content": "hi", "type": "PRIVMSG"},
            {"sender": "gemini", "content": "hello", "type": "PRIVMSG"},
        ]
        
        is_loop, reason = gr.check_loop(messages, "gemini")
        self.assertTrue(is_loop)
        self.assertIn("loop detected", reason)

if __name__ == '__main__':
    unittest.main()
