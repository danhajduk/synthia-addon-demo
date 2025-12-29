from enum import Enum


class Worker:
    # -----------------------
    # Enums (nested by design)
    # -----------------------

    class Priority(str, Enum):
        LOW = "LOW"
        NORMAL = "NORMAL"
        HIGH = "HIGH"
        URGENT = "URGENT"

    class JobState(str, Enum):
        QUEUED = "QUEUED"
        CLAIMED = "CLAIMED"
        PREPARING = "PREPARING"
        LEASE_PENDING = "LEASE_PENDING"
        RUNNING = "RUNNING"
        DONE = "DONE"
        FAILED = "FAILED"
        CANCELED = "CANCELED"
        TIMEOUT = "TIMEOUT"

    class LeaseState(str, Enum):
        # Keep names stable (as requested)
        active = "ACTIVE"
        expired = "EXPIRED"
        released = "RELEASED"

    class FinalStatus(str, Enum):
        SUCCEEDED = "SUCCEEDED"
        FAILED = "FAILED"
        CANCELED = "CANCELED"
        TIMEOUT = "TIMEOUT"

    class EntityType(str, Enum):
        JOB = "JOB"
        LEASE = "LEASE"

    # -----------------------
    # Worker core
    # -----------------------

    def __init__(self, worker_id: str) -> None:
        self.worker_id = worker_id
        self.current_state = self.JobState.QUEUED

    def is_idle(self) -> bool:
        return self.current_state in {
            self.JobState.QUEUED,
            self.JobState.DONE,
            self.JobState.FAILED,
            self.JobState.CANCELED,
            self.JobState.TIMEOUT,
        }

    def set_state(self, state: "Worker.JobState") -> None:
        self.current_state = state
