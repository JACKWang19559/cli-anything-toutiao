"""Run pure Node assertions against the actual packaged browser driver."""

from pathlib import Path
import shutil
import subprocess


def test_browser_driver_normalization_and_lifecycle():
    node = shutil.which("node")
    assert node is not None, "Node.js is required for the browser-driver development tests; install Node.js and put node on PATH."
    suite = Path(__file__).with_name("test_browser_driver.mjs")
    result = subprocess.run(
        [node, "--test", str(suite)], capture_output=True,
        text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
