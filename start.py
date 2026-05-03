"""
Launch backend (FastAPI/uvicorn) and frontend (Vite dev server) together.
Run from the project root:  python start.py
"""
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "web" / "frontend"
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000


def run_backend():
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "web.backend.app:app",
         "--reload", "--host", "0.0.0.0", "--port", str(BACKEND_PORT)],
        cwd=ROOT,
    )


def wait_for_backend(timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((BACKEND_HOST, BACKEND_PORT), timeout=1):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def run_frontend():
    if not wait_for_backend():
        print(f"Warning: backend did not respond on {BACKEND_HOST}:{BACKEND_PORT} within timeout.")
        print("If you see ECONNREFUSED on /api, wait for the backend to start and reload the page.")
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    subprocess.run([npm, "run", "dev"], cwd=FRONTEND)


if __name__ == "__main__":
    print("Starting OT Tutor...")
    print("  Backend  → http://localhost:8000")
    print("  Frontend → http://localhost:5173\n")

    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()

    run_frontend()  # runs in main thread; Ctrl+C kills everything
