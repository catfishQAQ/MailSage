from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
HOST = "127.0.0.1"
PORT = 8000
HEALTH_URL = f"http://{HOST}:{PORT}/api/health"
PID_PATH = BACKEND_DIR / "mailsage-backend.pid"


def fail(message: str, exit_code: int = 1) -> None:
    print(f"[MailSage] {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def process_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout.strip()
        if not output or "No tasks are running" in output:
            return False
        return f'"{pid}"' in output or f",{pid}," in output
    try:
        os.kill(pid, 0)
    except (OSError, SystemError):
        return False
    return True


def health_status(timeout: float = 1.0) -> str | None:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError):
        return None


def read_pid_file() -> int | None:
    if not PID_PATH.exists():
        return None
    try:
        return int(PID_PATH.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def remove_pid_file() -> None:
    if PID_PATH.exists():
        PID_PATH.unlink()


def wait_for_exit(pid: int, timeout_seconds: int = 10) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not process_is_running(pid):
            return True
        time.sleep(0.3)
    return not process_is_running(pid)


def kill_by_pid(pid: int) -> bool:
    if not process_is_running(pid):
        return True
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0 or not process_is_running(pid)

    os.kill(pid, signal.SIGTERM)
    if wait_for_exit(pid, timeout_seconds=8):
        return True
    os.kill(pid, signal.SIGKILL)
    return wait_for_exit(pid, timeout_seconds=2)


def pid_from_port() -> int | None:
    if os.name == "nt":
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            check=False,
        )
        target = f"{HOST}:{PORT}"
        for line in result.stdout.splitlines():
            if target in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    try:
                        return int(parts[-1])
                    except ValueError:
                        continue
        return None

    lsof_cmd = shutil.which("lsof")
    if not lsof_cmd:
        return None
    result = subprocess.run(
        [lsof_cmd, "-ti", f"tcp:{PORT}"],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in result.stdout.splitlines():
        try:
            return int(line.strip())
        except ValueError:
            continue
    return None


def main() -> None:
    print("[MailSage] Stopping MailSage...")
    pid = read_pid_file()

    if pid is not None:
        if kill_by_pid(pid):
            remove_pid_file()
            print("[MailSage] MailSage stopped.")
            return
        fail(f"Failed to stop backend process {pid}.")

    fallback_pid = pid_from_port()
    if fallback_pid is not None and health_status():
        print("[MailSage] Found a running MailSage-compatible service on port 8000 without a PID file.")
        if kill_by_pid(fallback_pid):
            remove_pid_file()
            print("[MailSage] MailSage stopped.")
            return
        fail(f"Failed to stop process {fallback_pid} on port 8000.")

    remove_pid_file()
    print("[MailSage] No running MailSage instance was found.")


if __name__ == "__main__":
    main()
