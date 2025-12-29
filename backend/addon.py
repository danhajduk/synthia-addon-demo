import json
import logging
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Optional

logger = logging.getLogger("synthia.addons.demo")
router = APIRouter()

_worker_proc: subprocess.Popen | None = None


# -----------------------
# Models (NO Optional[], NO future annotations)
# -----------------------

class WorkerStartResult(BaseModel):
    started: bool
    already_running: bool
    worker_id: str
    pid: int | None = None
    registered: bool = False
    message: str


class AddonStatus(BaseModel):
    status: str = "ok"
    addon: str = "demo"
    worker_running: bool
    worker_pid: int | None = None
    scheduler_base_url: str
    addon_id: str
    worker_id: str


# -----------------------
# Helpers
# -----------------------

def _http_post_json(url: str, payload: dict[str, Any], timeout_sec: int = 10) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"_non_json": body}


def _proc_running(p: subprocess.Popen | None) -> bool:
    return p is not None and p.poll() is None


def _scheduler_base_url() -> str:
    return os.environ.get("SYNTHIA_SCHEDULER_BASE_URL", "http://localhost:9001/api/scheduler")


def _addon_id() -> str:
    return os.environ.get("SYNTHIA_ADDON_ID", "demo")


def _worker_id() -> str:
    return os.environ.get("SYNTHIA_WORKER_ID", "demo-worker-01")


# -----------------------
# API Endpoints
# -----------------------

@router.get("/health")
def health() -> dict:
    return {"status": "ok", "addon": "demo"}


@router.get("/status", response_model=AddonStatus)
def status() -> AddonStatus:
    base_url = _scheduler_base_url()
    addon_id = _addon_id()
    worker_id = _worker_id()

    running = _proc_running(_worker_proc)
    pid = _worker_proc.pid if running else None

    return AddonStatus(
        worker_running=running,
        worker_pid=pid,
        scheduler_base_url=base_url,
        addon_id=addon_id,
        worker_id=worker_id,
    )


@router.post("/start_worker", response_model=WorkerStartResult)
def start_worker() -> WorkerStartResult:
    global _worker_proc

    try:
        base_url = _scheduler_base_url()
        addon_id = _addon_id()
        worker_id = _worker_id()

        worker_py = Path(__file__).with_name("worker.py")
        if not worker_py.exists():
            raise RuntimeError(f"worker.py not found at {worker_py}")

        if _proc_running(_worker_proc):
            pid = _worker_proc.pid
            register_url = f"{base_url.rstrip('/')}/workers/register"
            payload = {
                "addon_id": addon_id,
                "worker_id": worker_id,
                "pid": pid,
                "capabilities": {"job_types": ["demo"]},
                "meta": {"spawned_by": "demo_addon_api", "python": sys.executable},
            }
            _http_post_json(register_url, payload, timeout_sec=10)

            return WorkerStartResult(
                started=False,
                already_running=True,
                worker_id=worker_id,
                pid=pid,
                registered=True,
                message="Worker already running; re-registered with scheduler.",
            )

        env = os.environ.copy()
        env["SYNTHIA_SCHEDULER_BASE_URL"] = base_url
        env["SYNTHIA_ADDON_ID"] = addon_id
        env["SYNTHIA_WORKER_ID"] = worker_id
        env.setdefault("SYNTHIA_ACCEPT_JOB_TYPES", "demo")
        env.setdefault("SYNTHIA_POLL_INTERVAL_SEC", "2")

        _worker_proc = subprocess.Popen(
            [sys.executable, str(worker_py)],
            env=env,
            cwd=str(worker_py.parent),
            stdout=None,
            stderr=None,
        )
        pid = _worker_proc.pid

        register_url = f"{base_url.rstrip('/')}/workers/register"
        payload = {
            "addon_id": addon_id,
            "worker_id": worker_id,
            "pid": pid,
            "capabilities": {"job_types": ["demo"]},
            "meta": {"spawned_by": "demo_addon_api", "python": sys.executable},
        }
        _http_post_json(register_url, payload, timeout_sec=10)

        return WorkerStartResult(
            started=True,
            already_running=False,
            worker_id=worker_id,
            pid=pid,
            registered=True,
            message="Worker spawned and registered with scheduler.",
        )

    except Exception as e:
        logger.exception("start_worker failed")
        raise HTTPException(status_code=500, detail=f"start_worker failed: {e}") from e


# -----------------------
# Minimal addon object (visuals-style)
# -----------------------

class BackendAddon:
    def __init__(self, id: str, name: str, router: APIRouter) -> None:
        self.id = id
        self.name = name
        self.router = router


addon = BackendAddon(id="demo", name="Demo Addon", router=router)
