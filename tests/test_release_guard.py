import pathlib
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ReleaseGuardTests(unittest.TestCase):
    def test_release_guard_script_runs(self):
        result = subprocess.run(
            ["python3", str(ROOT / "tools" / "release_guard.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"status": "ok"', result.stdout)


if __name__ == "__main__":
    unittest.main()
