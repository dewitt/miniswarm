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

if __name__ == '__main__':
    unittest.main()
