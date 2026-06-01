"""Tests for the opt-in provider-backed runner (no network; uses a local stub)."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import provider_runner as pr  # noqa: E402

RUNNER = ROOT / "scripts" / "conclave_runner.py"
EXAMPLE_CONFIG = (ROOT / "configs" / "provider-model-slots.example.yaml").read_text(encoding="utf-8")
STUB = "import sys\nsys.stdin.read()\nprint('[STUB position] grounded in [E1]; advice only.')\n"


class ProviderConfigTests(unittest.TestCase):
    def setUp(self):
        self.cfg = pr.parse_provider_config(EXAMPLE_CONFIG)

    def test_slots_and_defaults_parsed(self):
        self.assertIn("balanced", self.cfg.slots)
        self.assertEqual(self.cfg.slots["deep"]["model_family"], "deep-reasoning")
        self.assertEqual(self.cfg.fallback_slot, "balanced")
        self.assertEqual(self.cfg.key_source, "environment")

    def test_seat_slots_parsed(self):
        self.assertEqual(self.cfg.seat_slots["conclave-marshall"], "verifier")

    def test_route_known_and_fallback(self):
        known = pr.route_for_seat("conclave-aurelius", self.cfg)
        self.assertEqual(known.slot, "deep")
        self.assertEqual(known.provider, "provider-gamma")
        fallback = pr.route_for_seat("conclave-does-not-exist", self.cfg)
        self.assertEqual(fallback.slot, self.cfg.fallback_slot)


class ClientSelectionTests(unittest.TestCase):
    def test_command_client_selected(self):
        client = pr.get_client({"CONCLAVE_PROVIDER_CMD": "cat"})
        self.assertIsInstance(client, pr.CommandClient)

    def test_anthropic_client_selected(self):
        client = pr.get_client({"ANTHROPIC_API_KEY": "sk-test"})
        self.assertIsInstance(client, pr.AnthropicClient)

    def test_no_client_when_env_empty(self):
        self.assertIsNone(pr.get_client({}))

    def test_command_client_runs(self):
        template = f'{sys.executable} -c "import sys;print(sys.stdin.read().strip()[:4])"'
        client = pr.CommandClient(template=template)
        out = client.complete("HELLO world", pr.Route("s", "balanced", "p", "m"), timeout=10)
        self.assertEqual(out, "HELL")


def _run(args, env):
    return subprocess.run([sys.executable, str(RUNNER), *args], capture_output=True, text=True, env=env)


class ProviderRunIntegrationTests(unittest.TestCase):
    def test_stubbed_run_fills_the_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            stub = pathlib.Path(tmp) / "stub.py"
            stub.write_text(STUB)
            env = {**os.environ, "CONCLAVE_PROVIDER_CMD": f"{sys.executable} {stub}"}
            result = _run(["--provider-run", "--profile", "risk", "--stdout", "Ship X?"], env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Mode:** provider-backed", result.stdout)
            self.assertIn("[STUB position]", result.stdout)
            self.assertIn("## 7. Recommendation", result.stdout)
            self.assertIn("the human decides", result.stdout)

    def test_transcript_is_captured(self):
        with tempfile.TemporaryDirectory() as tmp:
            stub = pathlib.Path(tmp) / "stub.py"
            stub.write_text(STUB)
            out = pathlib.Path(tmp) / "out"
            env = {**os.environ, "CONCLAVE_PROVIDER_CMD": f"{sys.executable} {stub}"}
            result = _run(["--provider-run", "--profile", "risk", "--out-dir", str(out), "Ship X?"], env)
            self.assertEqual(result.returncode, 0, result.stderr)
            transcripts = list(out.glob("*.transcript.json"))
            self.assertEqual(len(transcripts), 1)
            data = json.loads(transcripts[0].read_text())
            self.assertEqual(data["errors"], 0)
            # 3 advocates + 1 justice + 1 verifier + 1 synthesis for the risk profile.
            self.assertEqual(len(data["calls"]), 6)

    def test_falls_back_without_a_client(self):
        env = {k: v for k, v in os.environ.items() if k not in ("CONCLAVE_PROVIDER_CMD", "ANTHROPIC_API_KEY")}
        result = _run(["--provider-run", "--profile", "risk", "--dry-run", "Ship X?"], env)
        self.assertEqual(result.returncode, 0)
        self.assertIn("falling back", result.stderr)
        self.assertIn("profile=risk", result.stdout)


if __name__ == "__main__":
    unittest.main()
