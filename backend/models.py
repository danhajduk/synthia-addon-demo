from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict
from typing import List

class WorkerCapabilities(BaseModel):
    """
    Keep flexible: allow addon-specific fields without breaking changes.
    Examples:
      job_types: ["load30", "render"]
      gpu: true
      model: "sdxl"
    """
    model_config = ConfigDict(extra="allow")

    job_types: Optional[List[str]] = None
    gpu: Optional[bool] = None
    cpu_heavy_ok: Optional[bool] = None

class RegisterWorkerRequest(BaseModel):
    addon_id: str
    worker_id: str

    pid: Optional[int] = Field(
        default=None,
        description="OS process ID of the worker process"
    )

    capabilities: WorkerCapabilities = Field(default_factory=WorkerCapabilities)

    # Optional extra metadata (host, container, version, etc.)
    meta: Dict[str, Any] = Field(default_factory=dict)
