"""Decision stays responsive while a yielding scan is running."""
import os
import subprocess
import sys
import unittest
from pathlib import Path


class LoopLagTests(unittest.TestCase):
    def test_decision_stays_under_twelve_seconds_during_a_scan(self):
        root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root)
        done = subprocess.run(
            [sys.executable, str(root / "scripts" / "verify_decision_during_scan.py")],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("PASS", done.stdout)
        self.assertIn("loop-lag", done.stdout)
