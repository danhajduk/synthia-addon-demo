from __future__ import annotations

import os
import time
import signal
from setproctitle import setproctitle


# -------------------------------------------------
# Process identity (shows up in ps/top/htop/systemd)
# -------------------------------------------------

ADDON_ID = os.environ.get("SYNTHIA_ADDON_ID", "demo")
JOB_TYPE = os.environ.get("SYNTHIA_JOB_TYPE", "demo")
WORKER_ID = os.environ.get("SYNTHIA_WORKER_ID", f"{ADDON_ID}-worker-{os.getpid()}")

setproctitle(f"synthia-worker:{ADDON_ID}:{JOB_TYPE}")


# -------------------------------------------------
# Worker state
# -------------------------------------------------

class WorkerMode:
    IDLE = "IDLE"
    STOPPING = "STOPPING"


# -------------------------------------------------
# Main loop
# -------------------------------------------------

def main() -> int:
    mode = WorkerMode.IDLE
    stop = False

    def _handle_signal(signo, _frame):
        nonlocal stop, mode
        print(f"[worker] received signal {signo}, shutting down")
        mode = WorkerMode.STOPPING
        stop = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    print("[worker] starting standalone worker")
    print(f"[worker] ADDON_ID={ADDON_ID}")
    print(f"[worker] WORKER_ID={WORKER_ID}")
    print("[worker] startup delay: 30 seconds (debug window)")

    # ---- startup delay ----
    time.sleep(30)

    print("[worker] entering main loop")

    poll_interval_sec = int(os.environ.get("SYNTHIA_POLL_INTERVAL_SEC", "10"))
    last_tick = 0.0

    while not stop:
        try:
            now = time.monotonic()

            if mode == WorkerMode.IDLE and (now - last_tick) >= poll_interval_sec:
                last_tick = now

                # ---- main loop body (placeholder) ----
                print("[worker] tick (IDLE)")
                # later:
                # - poll scheduler
                # - claim job
                # - run job
                # - report result

            # short sleep keeps CPU low and signal handling responsive
            time.sleep(0.2)

        except Exception as e:
            # never die on transient errors
            print(f"[worker] ERROR: {type(e).__name__}: {e}")
            time.sleep(2)

    print("[worker] stopped cleanly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
