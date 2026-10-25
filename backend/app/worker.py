import time
from .db import init_db
from .ingestion import run_one


def main():
    init_db()
    print('{"event":"worker_started"}', flush=True)
    while True:
        if not run_one():
            time.sleep(2)


if __name__ == "__main__":
    main()
