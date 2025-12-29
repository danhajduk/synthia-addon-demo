import os
import subprocess
import logging
from fastapi import APIRouter

logger = logging.getLogger("synthia.addons.demo")
router = APIRouter()



@router.get("/health")
def health():
    return {"status": "ok", "addon": "demo"}


@router.get("/status")
def status():

    return {
        "status": "ok",
        "addon": "demo",
        "addon_id": os.environ.get("ADDON_ID", "demo"),
        "worker_id": os.environ.get("WORKER_ID", "visuals-worker-unknown"),
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
