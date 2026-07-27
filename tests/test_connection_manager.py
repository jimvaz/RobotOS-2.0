"""Tests for the Brain connection manager."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from brain.connection_manager import ConnectionManager
from websockets.asyncio.server import ServerConnection


def fake_connection() -> ServerConnection:
    """Create a lightweight identity object for collection tests."""

    return cast(ServerConnection, cast(Any, object()))


def test_connect_registers_connection() -> None:
    manager = ConnectionManager()
    connection = fake_connection()

    asyncio.run(manager.connect(connection))

    assert connection in manager
    assert len(manager) == 1
    assert manager.connections == frozenset({connection})


def test_disconnect_removes_connection() -> None:
    manager = ConnectionManager()
    connection = fake_connection()

    asyncio.run(manager.connect(connection))
    asyncio.run(manager.disconnect(connection))

    assert connection not in manager
    assert len(manager) == 0


def test_disconnect_is_idempotent() -> None:
    manager = ConnectionManager()
    connection = fake_connection()

    asyncio.run(manager.disconnect(connection))
    asyncio.run(manager.disconnect(connection))

    assert len(manager) == 0


def test_iteration_uses_snapshot() -> None:
    manager = ConnectionManager()
    first = fake_connection()
    second = fake_connection()

    asyncio.run(manager.connect(first))
    iterator = iter(manager)
    asyncio.run(manager.connect(second))

    assert list(iterator) == [first]
    assert manager.connections == frozenset({first, second})
