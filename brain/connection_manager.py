"""RobotOS Brain connection manager."""
from __future__ import annotations
from websockets.asyncio.server import ServerConnection

class ConnectionManager:
    def __init__(self)->None:
        self._connections:set[ServerConnection]=set()

    async def connect(self, websocket:ServerConnection)->None:
        self._connections.add(websocket)

    async def disconnect(self, websocket:ServerConnection)->None:
        self._connections.discard(websocket)

    @property
    def connections(self):
        return frozenset(self._connections)
