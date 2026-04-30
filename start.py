"""
Launch backend (FastAPI/uvicorn) and frontend (Vite dev server) together.
Run from the project root:  python start.py
"""
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "web" / "frontend"


def run_backend():
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "web.backend.app:app",
         "--reload", "--host", "0.0.0.0", "--port", "8000"],
        cwd=ROOT,
    )


def run_frontend():
    time.sleep(1.5)  # let backend start first
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    subprocess.run([npm, "run", "dev"], cwd=FRONTEND)


if __name__ == "__main__":
    print("Starting OT Tutor...")
    print("  Backend  → http://localhost:8000")
    print("  Frontend → http://localhost:5173\n")

    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()

    run_frontend()  # runs in main thread; Ctrl+C kills everything
