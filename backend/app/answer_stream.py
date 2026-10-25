"""Bounded SSE bridge; each stream owns its database session and commits only on success."""

import asyncio
import json
import logging
from threading import Event

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from .answer_progress import StreamCancelled, check_cancelled
from .db import session_scope
from .providers import ProviderError


def stream_answer(operation, owner):
    async def events():
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue(maxsize=64)
        stopped = Event()

        def emit(event, data):
            check_cancelled(stopped.is_set)
            future = asyncio.run_coroutine_threadsafe(queue.put((event, data)), loop)
            while True:
                try:
                    future.result(timeout=0.2)
                    return
                except TimeoutError:
                    if stopped.is_set():
                        future.cancel()
                        raise StreamCancelled()

        def run():
            try:
                with session_scope() as db:
                    db.info.update(owner)
                    result = operation(db, emit, stopped.is_set)
                    check_cancelled(stopped.is_set)
                    db.commit()
                emit("done", result)
            except StreamCancelled:
                pass
            except Exception as error:
                if not stopped.is_set():
                    message = (
                        str(error)
                        if isinstance(error, ProviderError)
                        else error.detail
                        if isinstance(error, HTTPException) and isinstance(error.detail, str)
                        else "The answer was interrupted. Please try again."
                    )
                    logging.getLogger("filinglens").warning(
                        "answer_stream_failed type=%s", type(error).__name__
                    )
                    emit("error", {"message": message})

        worker = asyncio.create_task(asyncio.to_thread(run))
        try:
            yield ": connected\n\n"
            while True:
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=10)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=True)}\n\n"
                if event in {"done", "error"}:
                    break
        finally:
            stopped.set()
            # Cancelling the await does not kill the thread; its cancellation flag
            # closes upstream streaming on the next chunk and rolls back the session.
            if not worker.done():
                worker.cancel()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
