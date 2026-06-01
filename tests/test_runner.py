"""Behavioral tests for the local conclave runner (covers the fixed bugs)."""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "conclave_runner.py"
LEDGER_A = ROOT / "demos" / "evidence-ledgers" / "architecture-notifications-platform-split.json"
LEDGER_B = ROOT / "demos" / "evidence-ledgers" / "war-game-launch-plan.json"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        capture_output=True,
        text=True,
    )


class RunnerTests(unittest.TestCase):
    def test_list_profiles(self):
        result = run("--list-profiles")
        self.assertEqual(result.returncode, 0)
        self.assertIn("architecture", result.stdout)

    def test_default_profile_is_config_driven(self):
        result = run("--dry-run", "no profile given")
        self.assertEqual(result.returncode, 0)
        self.assertIn("profile=architecture", result.stdout)

    def test_unknown_member_fails(self):
        result = run("--members", "nope-seat", "--dry-run", "x")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown seat", result.stderr)

    def test_merge_two_ledgers_renumbers_without_crashing(self):
        result = run(
            "--members", "feynman",
            "--ledger-file", str(LEDGER_A),
            "--ledger-file", str(LEDGER_B),
            "--stdout", "merge test",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Duplicate evidence ID", result.stderr)
        # 6 + 6 entries, renumbered into one contiguous E1..E12 sequence.
        self.assertIn("| E12 |", result.stdout)
        self.assertNotIn("| E13 |", result.stdout)

    def test_rapid_runs_never_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            for index in range(3):
                result = run("--profile", "risk", "--out-dir", tmp, f"run {index}")
                self.assertEqual(result.returncode, 0, result.stderr)
            files = list(pathlib.Path(tmp).glob("verdict-*.md"))
            self.assertEqual(len(files), 3, "every run must produce a distinct file")

    def test_write_ledger_is_ignored_under_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "out.json"
            result = run("--profile", "risk", "--write-ledger", str(target), "--dry-run", "x")
            self.assertEqual(result.returncode, 0)
            self.assertIn("ignored under --dry-run", result.stderr)
            self.assertFalse(target.exists())

    def test_justice_rows_render_as_checks(self):
        result = run("--profile", "risk", "--stdout", "x")
        self.assertEqual(result.returncode, 0)
        self.assertIn("conclave-lady-hale", result.stdout)
        self.assertIn("structural check; states a bound", result.stdout)


if __name__ == "__main__":
    unittest.main()
