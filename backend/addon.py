import logging
import os
import subprocess

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger("synthia.addons.demo")
router = APIRouter()

_worker_proc: subprocess.Popen | None = None


# -----------------------
# Models
# -----------------------

class AddonStatus(BaseModel):
    worker_running: bool
    worker_pid: int | None
    addon_id: str
    worker_id: str


# -----------------------
# API Endpoints
# -----------------------

@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "addon": "demo",
    }


@router.get("/status", response_model=AddonStatus)
def status() -> AddonStatus:
    running = _worker_proc is not None and _worker_proc.poll() is None
    pid = _worker_proc.pid if running else None

    return AddonStatus(
        worker_running=running,
        worker_pid=pid,
        addon_id=os.environ.get("ADDON_ID", "demo"),
        worker_id=os.environ.get("WORKER_ID", "visuals-worker-unknown"),
    )


# -----------------------
# Addon export
# -----------------------

class BackendAddon:
    def __init__(self, id: str, name: str, router: APIRouter) -> None:
        self.id = id
        self.name = name
        self.router = router


addon = BackendAddon(
    id="demo",
    name="Demo Addon",
    router=router,
)
