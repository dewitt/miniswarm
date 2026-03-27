import unittest
import sys
import os
import json
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
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            runner.bootstrap_state(tmpdir)
            self.assertTrue(runner.acquire_lock("file1", "owner1", ttl_seconds=10, project_root=tmpdir))
            self.assertFalse(runner.acquire_lock("file1", "owner2", ttl_seconds=10, project_root=tmpdir))
            self.assertEqual(runner.check_lock("file1", project_root=tmpdir), "owner1")

            runner.release_lock("file1", "owner1", project_root=tmpdir)
            self.assertIsNone(runner.check_lock("file1", project_root=tmpdir))
            self.assertTrue(runner.acquire_lock("file1", "owner2", ttl_seconds=10, project_root=tmpdir))

    def test_state_bootstrap_schema(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            runner.bootstrap_state(tmpdir)
            state_dir = Path(tmpdir) / "state"
            self.assertTrue((state_dir / "claims.json").exists())
            self.assertTrue((state_dir / "tasks.json").exists())
            self.assertTrue((state_dir / "agents").is_dir())
            self.assertTrue((state_dir / "summaries").is_dir())

    def test_expire_stale_locks(self):
        import tempfile
        from datetime import datetime, timedelta
        with tempfile.TemporaryDirectory() as tmpdir:
            runner.bootstrap_state(tmpdir)
            claims_path = Path(tmpdir) / "state" / "claims.json"
            stale_claims = {
                "schema_version": 1,
                "updated_at": datetime.now().isoformat(),
                "claims": [
                    {
                        "path": "src/a.py",
                        "owner": "claude",
                        "acquired": (datetime.now() - timedelta(minutes=15)).isoformat(),
                        "expires": (datetime.now() - timedelta(minutes=5)).isoformat(),
                    }
                ],
            }
            claims_path.write_text(json.dumps(stale_claims))

            self.assertEqual(runner.expire_stale_locks(project_root=tmpdir), 1)
            self.assertIsNone(runner.check_lock("src/a.py", project_root=tmpdir))

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

    def test_context_drift_resilience(self):
        agent_config = {"nick": "gemini", "role": "Tester"}
        trigger = {"type": "PRIVMSG", "sender": "dewitt", "content": "fix this", "raw": "1"}
        recent = [{"type": "PRIVMSG", "sender": "user", "content": f"msg {i}", "raw": str(i)} for i in range(20)]
        context = runner.build_context(agent_config, recent, trigger, ".")
        self.assertIn("msg 19", context)
        self.assertNotIn("msg 0", context)
        self.assertNotIn("msg 4", context)
        self.assertIn("msg 5", context)

class TestIsRelevantEdgeCases(unittest.TestCase):
    def _config(self, my_nick="claude"):
        return {"agents": {my_nick: {"nick": my_nick}, "gemini": {"nick": "gemini"}, "codex": {"nick": "codex"}}}

    def test_at_all_relevant(self):
        msg = {"type": "PRIVMSG", "sender": "dewitt", "content": "Hey @all, what's the status?"}
        self.assertTrue(runner.is_relevant(msg, "claude", self._config()))

    def test_own_message_ignored(self):
        msg = {"type": "PRIVMSG", "sender": "claude", "content": "@claude ignore this"}
        self.assertFalse(runner.is_relevant(msg, "claude", self._config()))

    def test_task_directed_at_me(self):
        msg = {"type": "PRIVMSG", "sender": "dewitt", "content": "TASK @claude — Fix the tests"}
        self.assertTrue(runner.is_relevant(msg, "claude", self._config()))

    def test_handoff_directed_at_me(self):
        msg = {"type": "PRIVMSG", "sender": "codex", "content": "HANDOFF @claude — I'm done here"}
        self.assertTrue(runner.is_relevant(msg, "claude", self._config()))

    def test_directed_prefix_wrong_nick(self):
        msg = {"type": "PRIVMSG", "sender": "gemini", "content": "TASK @codex — Generate some docs"}
        self.assertFalse(runner.is_relevant(msg, "claude", self._config()))

    def test_human_no_mention_relevant(self):
        msg = {"type": "PRIVMSG", "sender": "dewitt", "content": "Hey team, how are things?"}
        self.assertTrue(runner.is_relevant(msg, "claude", self._config()))

    def test_human_mention_other_agent_not_relevant(self):
        msg = {"type": "PRIVMSG", "sender": "dewitt", "content": "Hey @gemini can you test this?"}
        self.assertFalse(runner.is_relevant(msg, "claude", self._config()))

    def test_non_privmsg_ignored(self):
        msg = {"type": "JOIN", "sender": "dewitt", "content": ""}
        self.assertFalse(runner.is_relevant(msg, "claude", self._config()))

if __name__ == '__main__':
    unittest.main()
