"""WebSocket broadcast — transport only, no business logic."""

from typing import List
from fastapi import WebSocket

active_connections: List[WebSocket] = []


async def broadcast(data: dict) -> None:
    dead = []
    for ws in active_connections:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in active_connections:
            active_connections.remove(ws)
