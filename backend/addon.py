from __future__ import annotations

import logging
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .worker import (
    DemoWorker,
    WorkerStartResult,
    SetJobRequest,
    SetJobResult,
    AddonStatus,
    JobStatus,
)

import os
import sys
import json
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("synthia.addons.demo")

router = APIRouter()

# Single in-process worker instance for the demo addon.
# Later you can swap this to a per-addon runtime root, process worker, queue worker, etc.
_worker = DemoWorker()


# ---- Addon wrapper models (match your existing addon loader shape) ----

class AddonMeta(BaseModel):
    id: str
    name: str
    version: str
    description: str = ""


class BackendAddon(BaseModel):
    meta: AddonMeta
    router: APIRouter

from pydantic import BaseModel, Field

class WorkerStartResult(BaseModel):
    started: bool
    already_running: bool
    worker_id: str
    pid: Optional[int] = None
    registered: bool = False
    message: str

_worker_proc: subprocess.Popen | None = None

#-----------------------
# Helpers
#-----------------------

def _http_post_json(url: str, payload: Dict[str, Any], timeout_sec: int = 10) -> Dict[str, Any]:
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



#-----------------------
# API Endpoints
#-----------------------   
@router.get("/status")
def status():
    paths = ensure_dirs()
    cfg = DEFAULT_CONFIG.model_dump()

    # Ensure we have something published
    current_path = paths["published"] / cfg["weather_scene"]["publish_filename"]
    if not current_path.exists():
        publish_placeholder(current_path, subtitle="Step 0: addon online")

    return {
        "status": "ok",
        "enabled_renderers": cfg["enabled_renderers"],
        "paths": {k: str(v) for k, v in paths.items()},
        "published_current": str(current_path),
    }

@router.post("/start_worker", response_model=WorkerStartResult)
def start_worker() -> WorkerStartResult:
    """
    1) Start the worker as a separate process (same venv as the API via sys.executable)
    2) Register the worker with scheduler at POST /workers/register
    Idempotent: if worker already running, returns existing PID (and re-registers if you want).
    """
    global _worker_proc

    try:
        # --- Config (env-driven; safe defaults) ---
        base_url = os.environ.get("SYNTHIA_SCHEDULER_BASE_URL", "http://localhost:9001/api/scheduler")
        addon_id = os.environ.get("SYNTHIA_ADDON_ID", "demo")

        # "visuals-worker-" + %n doesn't exist here; use env override or pid suffix.
        worker_id = os.environ.get("SYNTHIA_WORKER_ID", f"visuals-worker-{os.getpid()}")

        # --- Idempotent: already running ---
        if _worker_proc is not None and _worker_proc.poll() is None:
            pid = _worker_proc.pid

            # Optional: re-register on every call (useful if scheduler restarted)
            register_url = f"{base_url.rstrip('/')}/workers/register"
            register_payload = {
                "addon_id": addon_id,
                "worker_id": worker_id,
                "pid": pid,
                "capabilities": {},  # fill when you define WorkerCapabilities
                "meta": {
                    "spawned_by": "addon_api",
                    "python": sys.executable,
                },
            }
            _http_post_json(register_url, register_payload, timeout_sec=10)

            return WorkerStartResult(
                started=False,
                already_running=True,
                worker_id=worker_id,
                pid=pid,
                registered=True,
                message="Worker already running; (re)registered with scheduler.",
            )

        # --- Spawn worker process using SAME VENV python ---
        python = sys.executable
        worker_py = Path(__file__).with_name("worker.py")
        if not worker_py.exists():
            raise RuntimeError(f"worker.py not found at {worker_py}")

        env = os.environ.copy()
        env.setdefault("SYNTHIA_SCHEDULER_BASE_URL", base_url)
        env.setdefault("SYNTHIA_ADDON_ID", addon_id)
        env.setdefault("SYNTHIA_WORKER_ID", worker_id)
        env.setdefault("SYNTHIA_JOB_TYPE", env.get("SYNTHIA_JOB_TYPE", "demo"))
        env.setdefault("SYNTHIA_POLL_INTERVAL_SEC", env.get("SYNTHIA_POLL_INTERVAL_SEC", "10"))

        _worker_proc = subprocess.Popen(
            [python, str(worker_py)],
            env=env,
            cwd=str(worker_py.parent),
            stdout=None,  # inherit API logs for now (good for dev)
            stderr=None,
        )

        pid = _worker_proc.pid

        # --- Register worker with scheduler ---
        register_url = f"{base_url.rstrip('/')}/workers/register"

        # You provided RegisterWorkerRequest fields; capabilities model not shown,
        # so we send {} by default and you can expand later.
        register_payload = {
            "addon_id": addon_id,
            "worker_id": worker_id,
            "pid": pid,
            "capabilities": {},  # TODO: supply real WorkerCapabilities content
            "meta": {
                "spawned_by": "addon_api",
                "python": python,
                "job_type": env.get("SYNTHIA_JOB_TYPE", "demo"),
            },
        }

        _http_post_json(register_url, register_payload, timeout_sec=10)

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


@router.post("/set_job", response_model=SetJobResult)
def set_job(req: SetJobRequest) -> SetJobResult:
    """
    Submit a job to the worker.

    Required:
      - job_name
      - job_cost (integer 'cost units' so your scheduler can reason about load)

    Extras included because you *will* want them:
      - priority: LOW | NORMAL | HIGH
      - run_mode: sync | async (demo default could be async once worker.py exists)
      - timeout_sec
      - dedupe_key: prevent double-submits
      - payload: arbitrary dict for addon-specific job params
    """
    try:
        # Guardrails (addon-level). Worker also validates.
        if req.job_cost < 0:
            raise HTTPException(status_code=400, detail="job_cost must be >= 0")
        if not req.job_name.strip():
            raise HTTPException(status_code=400, detail="job_name cannot be empty")

        # Optional: force-start worker on first job submit (nice UX)
        if not _worker.is_running:
            _worker.start()

        return _worker.set_job(req)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("set_job failed")
        raise HTTPException(status_code=500, detail=f"set_job failed: {e}") from e


@router.get("/status", response_model=AddonStatus)
def status() -> AddonStatus:
    """
    Health endpoint: proves the addon is mounted + worker is reachable.
    """
    try:
        return _worker.addon_status()
    except Exception as e:
        logger.exception("status failed")
        raise HTTPException(status_code=500, detail=f"status failed: {e}") from e


@router.get("/job_status", response_model=JobStatus)
def job_status(job_id: Optional[str] = None) -> JobStatus:
    """
    Return status for:
      - a specific job_id (if provided)
      - otherwise the current/last job
    """
    try:
        return _worker.job_status(job_id=job_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception("job_status failed")
        raise HTTPException(status_code=500, detail=f"job_status failed: {e}") from e


# ---- Export addon object (matches your backend registry pattern) ----

addon = BackendAddon(
    meta=AddonMeta(
        id="demo",
        name="Demo Addon",
        version="0.1.0",
        description="Demo addon: worker control + job submission endpoints.",
    ),
    router=router,
)
