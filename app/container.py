"""Run the S3 API and web console as one supervised container process."""

from __future__ import annotations

import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request


API = [sys.executable, "-m", "hypercorn", "app.s3_server:app", "--bind", "0.0.0.0:9000"]
CONSOLE = [sys.executable, "-m", "hypercorn", "app.console_server:app", "--bind", "0.0.0.0:9001"]


def _healthy(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError):
        return False


def _wait_for(url: str, process: subprocess.Popen, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        if _healthy(url):
            return True
        time.sleep(0.2)
    return False


def _stop(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> int:
    api = console = None
    stopping = False

    def shutdown(_signum, _frame):
        nonlocal stopping
        stopping = True
        _stop(console)
        _stop(api)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        api = subprocess.Popen(API)
        if not _wait_for("http://127.0.0.1:9000/health/ready", api):
            return 1

        console = subprocess.Popen(CONSOLE)
        if not _wait_for("http://127.0.0.1:9001/health/live", console):
            return 1

        while not stopping:
            if api.poll() is not None or console.poll() is not None:
                return 1
            time.sleep(0.2)
        return 0
    finally:
        _stop(console)
        _stop(api)


if __name__ == "__main__":
    raise SystemExit(main())
