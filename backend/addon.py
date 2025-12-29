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



# -----------------------
# Helpers
# -----------------------


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



class BackendAddon:
    def __init__(self, id: str, name: str, router: APIRouter) -> None:
        self.id = id
        self.name = name
        self.router = router


addon = BackendAddon(id="demo", name="Demo Addon", router=router)
