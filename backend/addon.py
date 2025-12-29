import json
import os
import sys
import subprocess
import urllib.request
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

_worker_proc: subprocess.Popen | None = None


@router.get("/health")
def health():
    return {"status": "ok", "addon": "demo"}


@router.get("/status")
def status():
    running = _worker_proc is not None and _worker_proc.poll() is None
    pid = _worker_proc.pid if running else None
    return {"status": "ok", "addon": "demo", "worker_running": running, "worker_pid": pid}


@router.post("/start_worker")
def start_worker():
    """
    1) Spawn worker.py with same venv (sys.executable)
    2) Register worker in scheduler: POST {BASE_URL}/workers/register
    """
    global _worker_proc

    base_url = os.environ.get("SYNTHIA_SCHEDULER_BASE_URL", "http://localhost:9001/api/scheduler")
    addon_id = os.environ.get("SYNTHIA_ADDON_ID", "demo")
    worker_id = os.environ.get("SYNTHIA_WORKER_ID", f"visuals-worker-{os.getpid()}")
    job_type = os.environ.get("SYNTHIA_JOB_TYPE", "demo")

    # Capabilities: take from env if provided; otherwise omit (scheduler model treats Optional)
    job_types_env = os.environ.get("SYNTHIA_JOB_TYPES")  # "a,b,c"
    gpu_env = os.environ.get("SYNTHIA_GPU")              # "1"/"0"
    cpu_heavy_ok_env = os.environ.get("SYNTHIA_CPU_HEAVY_OK")  # "1"/"0"

    capabilities: dict = {}
    if job_types_env:
        capabilities["job_types"] = [s.strip() for s in job_types_env.split(",") if s.strip()]
    if gpu_env is not None:
        capabilities["gpu"] = (gpu_env == "1")
    if cpu_heavy_ok_env is not None:
        capabilities["cpu_heavy_ok"] = (cpu_heavy_ok_env == "1")

    # ---------- 1) start worker (idempotent) ----------
    already_running = _worker_proc is not None and _worker_proc.poll() is None

    if not already_running:
        worker_py = Path(__file__).with_name("worker.py")
        if not worker_py.exists():
            raise HTTPException(status_code=500, detail=f"worker.py not found: {worker_py}")

        env = os.environ.copy()
        env["SYNTHIA_SCHEDULER_BASE_URL"] = base_url
        env["SYNTHIA_ADDON_ID"] = addon_id
        env["SYNTHIA_WORKER_ID"] = worker_id
        env["SYNTHIA_JOB_TYPE"] = job_type

        _worker_proc = subprocess.Popen(
            [sys.executable, str(worker_py)],
            cwd=str(worker_py.parent),
            env=env,
            stdout=None,
            stderr=None,
        )

    running = _worker_proc is not None and _worker_proc.poll() is None
    pid = _worker_proc.pid if running else None

    if not running or pid is None:
        raise HTTPException(status_code=500, detail="worker failed to start")

    # ---------- 2) register worker ----------
    reg_payload: dict = {
        "addon_id": addon_id,
        "worker_id": worker_id,
        "pid": pid,
        "capabilities": capabilities if capabilities else {},
        "meta": {
            "job_type": job_type,
        },
    }

    reg_url = f"{base_url.rstrip('/')}/workers/register"
    data = json.dumps(reg_payload).encode("utf-8")

    req = urllib.request.Request(
        reg_url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            reg_resp = json.loads(body)
    except Exception as e:
        # Worker started but registration failed — return both facts.
        return {
            "ok": False,
            "addon": "demo",
            "started": True,
            "already_running": already_running,
            "pid": pid,
            "python": sys.executable,
            "register_ok": False,
            "register_error": f"{type(e).__name__}: {e}",
            "register_url": reg_url,
            "register_payload": reg_payload,
        }

    return {
        "ok": True,
        "addon": "demo",
        "started": True,
        "already_running": already_running,
        "pid": pid,
        "python": sys.executable,
        "register_ok": True,
        "register_response": reg_resp,
    }


@router.post("/stop_worker")
def stop_worker():
    global _worker_proc

    if _worker_proc is None or _worker_proc.poll() is not None:
        return {"ok": True, "already_stopped": True}

    pid = _worker_proc.pid
    _worker_proc.terminate()

    try:
        _worker_proc.wait(timeout=10)
        stopped = True
    except subprocess.TimeoutExpired:
        _worker_proc.kill()
        stopped = False

    _worker_proc = None
    return {"ok": True, "pid": pid, "stopped_gracefully": stopped}


class BackendAddon:
    def __init__(self, id: str, name: str, router: APIRouter) -> None:
        self.id = id
        self.name = name
        self.router = router


addon = BackendAddon(id="demo", name="Demo Addon", router=router)
