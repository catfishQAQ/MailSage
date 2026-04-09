from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"
HOST = "127.0.0.1"
PORT = 8000
APP_URL = f"http://{HOST}:{PORT}"
HEALTH_URL = f"{APP_URL}/api/health"
LOG_PATH = BACKEND_DIR / "mailsage-backend.log"
PID_PATH = BACKEND_DIR / "mailsage-backend.pid"


def fail(message: str, exit_code: int = 1) -> None:
    print(f"[MailSage] {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def backend_python() -> str:
    candidates = [
        BACKEND_DIR / ".venv" / "Scripts" / "python.exe",
        BACKEND_DIR / ".venv" / "bin" / "python",
        Path(sys.executable),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    for command in ("python", "python3", "py"):
        if command_exists(command):
            return command
    fail("Python was not found. Please install Python 3.11+ and backend dependencies first.")


def frontend_needs_build() -> bool:
    if not FRONTEND_INDEX.exists():
        return True
    latest_source_mtime = 0.0
    for path in FRONTEND_DIR.rglob("*"):
        if path.is_dir():
            continue
        if "node_modules" in path.parts or "dist" in path.parts:
            continue
        latest_source_mtime = max(latest_source_mtime, path.stat().st_mtime)
    return latest_source_mtime > FRONTEND_INDEX.stat().st_mtime


def run_frontend_build() -> None:
    npm_cmd = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm_cmd:
        fail("Node.js / npm was not found. Please install Node.js 18+ and run `npm install` in frontend/.")
    print("[MailSage] Building frontend...")
    try:
        subprocess.run([npm_cmd, "run", "build"], cwd=FRONTEND_DIR, check=True)
    except subprocess.CalledProcessError as exc:
        fail(f"Frontend build failed with exit code {exc.returncode}.")


def health_status(timeout: float = 1.0) -> str | None:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="ignore")
        return body
    except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError):
        return None


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def write_pid_file(pid: int) -> None:
    PID_PATH.write_text(str(pid), encoding="utf-8")


def remove_pid_file() -> None:
    if PID_PATH.exists():
        PID_PATH.unlink()


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


def pid_file_matches_running_process() -> bool:
    if not PID_PATH.exists():
        return False
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        remove_pid_file()
        return False
    if process_is_running(pid):
        return True
    remove_pid_file()
    return False


def open_browser() -> None:
    print(f"[MailSage] Opening {APP_URL}")
    webbrowser.open(APP_URL)


def start_backend_process() -> int:
    python_cmd = backend_python()
    env = os.environ.copy()
    env["MAILSAGE_SERVE_FRONTEND"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as log_file:
        kwargs: dict[str, object] = {
            "cwd": str(BACKEND_DIR),
            "env": env,
            "stdout": log_file,
            "stderr": log_file,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(
            [python_cmd, "-m", "uvicorn", "main:app", "--host", HOST, "--port", str(PORT)],
            **kwargs,
        )
        return process.pid


def wait_for_backend(timeout_seconds: int = 30) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if health_status():
            return True
        time.sleep(0.5)
    return False


def main() -> None:
    print("[MailSage] Starting one-click launcher...")

    current_health = health_status()
    if current_health:
        print("[MailSage] Existing MailSage instance detected.")
        if not pid_file_matches_running_process():
            print("[MailSage] Warning: running instance was not started by the current launcher, so one-click stop may not find it.")
        open_browser()
        return

    if port_in_use(HOST, PORT):
        fail(f"Port {PORT} is already in use by another process. Please free the port and try again.")

    if frontend_needs_build():
        run_frontend_build()
    else:
        print("[MailSage] Frontend build is up to date.")

    pid = start_backend_process()
    write_pid_file(pid)

    if not wait_for_backend():
        remove_pid_file()
        fail(
            "Backend failed to become ready within 30 seconds. "
            f"Check the log at {LOG_PATH}."
        )

    open_browser()
    print(f"[MailSage] MailSage is ready. Backend PID: {pid}")


if __name__ == "__main__":
    main()
