import os
import sys
import subprocess

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from datetime import datetime


router = APIRouter()

# Keep runtime inside addon folder: addons/visuals/runtime/...
ADDON_ROOT = Path(__file__).resolve().parents[1]  # .../addons/visuals


_worker_proc: subprocess.Popen | None = None



@router.get("/health")
def health():
    return {"status": "ok", "addon": "demo"}


@router.get("/status")
def status():
    running = _worker_proc is not None and _worker_proc.poll() is None
    pid = _worker_proc.pid if running else None

    return {
        "status": "ok",
        "addon": "demo",
        "worker_running": running,
        "worker_pid": pid,
    }

@router.get("/start_worker")
def start_worker():
    global _worker_proc

    # idempotent: if already running, return existing pid
    if _worker_proc is not None and _worker_proc.poll() is None:
        return {
            "ok": True,
            "already_running": True,
            "pid": _worker_proc.pid,
        }

    worker_py = Path(__file__).with_name("worker.py")
    if not worker_py.exists():
        raise HTTPException(status_code=500, detail=f"worker.py not found: {worker_py}")

    env = os.environ.copy()
    env.setdefault("SYNTHIA_SCHEDULER_BASE_URL", "http://localhost:9001/api/scheduler")
    env.setdefault("SYNTHIA_ADDON_ID", "demo")
    env.setdefault("SYNTHIA_WORKER_ID", "visuals-worker-demo")  # override if you want
    env.setdefault("SYNTHIA_JOB_TYPE", "demo")

    # SAME VENV as the backend process:
    # sys.executable points at .../Synthia/.venv/bin/python if uvicorn is running in that venv.
    _worker_proc = subprocess.Popen(
        [sys.executable, str(worker_py)],
        cwd=str(worker_py.parent),
        env=env,
        stdout=None,  # inherit for dev visibility
        stderr=None,
    )

    return {
        "ok": True,
        "already_running": False,
        "pid": _worker_proc.pid,
        "python": sys.executable,
        "worker": str(worker_py),
    }

@router.post("/stop_worker")
def stop_worker():
    global _worker_proc

    if _worker_proc is None or _worker_proc.poll() is not None:
        return {
            "ok": True,
            "already_stopped": True,
        }

    pid = _worker_proc.pid

    # Graceful shutdown
    _worker_proc.terminate()  # SIGTERM

    try:
        _worker_proc.wait(timeout=10)
        stopped = True
    except subprocess.TimeoutExpired:
        # Last resort
        _worker_proc.kill()  # SIGKILL
        stopped = False

    _worker_proc = None

    return {
        "ok": True,
        "pid": pid,
        "stopped_gracefully": stopped,
    }



class BackendAddon:
    """
    Minimal object to satisfy the core loader.

    It only needs:
      - id: str
      - name: str
      - router: APIRouter
    """
    def __init__(self, id: str, name: str, router: APIRouter) -> None:
        self.id = id
        self.name = name
        self.router = router


addon = BackendAddon(
    id="demo",
    name="Demo Addon",
    router=router,
)
