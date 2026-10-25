import time
import logging
from threading import Event, Thread
from .db import init_db, session_scope
from .ingestion import run_one
from .analysis_jobs import run_analysis_one
from .models import WorkerState, now
from .config import get_settings


def keep_alive(stop):
    while not stop.wait(10):
        try:
            with session_scope() as db:
                state = db.get(WorkerState, "main")
                if state:
                    state.last_seen = now()
        except Exception:
            logging.getLogger("filinglens").warning("worker_heartbeat_delayed")


def main():
    get_settings().validate_deployment()
    init_db()
    print('{"event":"worker_started"}', flush=True)
    stop = Event()
    heartbeat = Thread(target=keep_alive, args=(stop,), daemon=True)
    heartbeat.start()
    try:
        while True:
            if not run_analysis_one(priority_only=True) and not run_one() and not run_analysis_one():
                time.sleep(2)
    finally:
        stop.set()
        heartbeat.join(timeout=12)


if __name__ == "__main__":
    main()
