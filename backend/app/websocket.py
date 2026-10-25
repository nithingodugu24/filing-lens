"""Durable database outbox bridges the separate worker and API processes."""

import asyncio
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select

from .config import get_settings
from .db import session_scope
from .models import Document, StatusEvent

router = APIRouter(tags=["Events"])


class ConnectionManager:
    def __init__(self):
        self.groups = defaultdict(set)

    async def connect(self, socket, group):
        await socket.accept()
        self.groups[group].add(socket)

    def disconnect(self, socket, group):
        self.groups[group].discard(socket)
        if not self.groups[group]:
            del self.groups[group]

    async def broadcast(self, payload, group):
        for socket in list(self.groups.get(group, [])):
            try:
                await socket.send_json(payload)
            except (WebSocketDisconnect, RuntimeError):
                self.disconnect(socket, group)


manager = ConnectionManager()


def events_after(cursor, user=None):
    with session_scope() as db:
        query = (
            select(StatusEvent)
            .join(Document, Document.id == StatusEvent.document_id)
            .where(StatusEvent.id > cursor)
            .order_by(StatusEvent.id)
            .limit(100)
        )
        if user and user["role"] != "admin":
            query = query.where(Document.user_id == user["id"])
        events = db.scalars(query).all()
        return [(e.id, e.payload) for e in events]


def socket_user(token):
    from .auth import current_user

    with session_scope() as db:
        user = current_user(db, token)
        return {"id": user.id, "role": user.role}


@router.websocket("/api/ws")
async def status_socket(socket: WebSocket):
    # Authenticate in the first frame, never put bearer tokens in URLs or request logs.
    origin = socket.headers.get("origin")
    if origin and origin not in get_settings().cors_origins.split(","):
        await socket.close(code=1008)
        return
    await socket.accept()
    user = None
    auth_token = ""
    group = "local"
    try:
        if get_settings().jwt_secret_key:
            payload = await asyncio.wait_for(socket.receive_json(), timeout=10)
            auth_token = payload.get("token", "")
            user = await asyncio.to_thread(socket_user, auth_token)
            group = user["id"]
        manager.groups[group].add(socket)
        with session_scope() as db:
            cursor = db.scalar(select(func.max(StatusEvent.id))) or 0
        await socket.send_json({"type": "connected", "cursor": cursor})
        ticks = 0
        while True:
            # An interrupted connection is detected by send/receive on the next tick.
            batch = await asyncio.to_thread(events_after, cursor, user)
            for event_id, payload in batch:
                await socket.send_json({**payload, "event_id": event_id})
                cursor = event_id
            ticks += 1
            if ticks % 15 == 0:
                if user:
                    user = await asyncio.to_thread(socket_user, auth_token)
                await socket.send_json({"type": "ping"})
            try:
                message = await asyncio.wait_for(socket.receive_text(), timeout=1)
                if message == "pong":
                    continue
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await socket.close(code=1008)
        except RuntimeError:
            pass
    finally:
        if socket in manager.groups.get(group, set()):
            manager.disconnect(socket, group)
