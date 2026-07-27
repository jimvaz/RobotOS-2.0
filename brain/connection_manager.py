"""Connection lifecycle management for RobotOS Brain nodes."""

from __future__ import annotations

from collections.abc import Iterator

from websockets.asyncio.server import ServerConnection


class ConnectionManager:
    """Track currently connected RobotOS node WebSocket connections.

    The manager owns the connection collection so the Brain server doesn't
    need to manipulate its internal storage directly.  This keeps connection
    lifecycle concerns isolated and prepares the server for future routing and
    broadcast features.
    """

    def __init__(self) -> None:
        self._connections: set[ServerConnection] = set()

    async def connect(self, websocket: ServerConnection) -> None:
        """Register a newly connected node."""

        self._connections.add(websocket)

    async def disconnect(self, websocket: ServerConnection) -> None:
        """Remove a node connection if it is currently registered."""

        self._connections.discard(websocket)

    def __contains__(self, websocket: object) -> bool:
        """Return whether a connection is currently registered."""

        return websocket in self._connections

    def __iter__(self) -> Iterator[ServerConnection]:
        """Iterate over a stable snapshot of active connections."""

        return iter(self.connections)

    def __len__(self) -> int:
        """Return the number of active connections."""

        return len(self._connections)

    @property
    def connections(self) -> frozenset[ServerConnection]:
        """Return an immutable snapshot of active connections."""

        return frozenset(self._connections)
