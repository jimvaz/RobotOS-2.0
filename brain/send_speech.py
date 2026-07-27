"""Send a manual speech command to a connected RobotOS Node."""

from __future__ import annotations

import asyncio

from loguru import logger
from websockets.asyncio.client import connect

from shared.models import Message
from shared.protocol import MessageType


async def main() -> None:
    text = input("Κείμενο για ομιλία: ").strip()

    if not text:
        print("Δεν δόθηκε κείμενο.")
        return

    message = Message(
        type=MessageType.SPEECH,
        payload={"text": text},
    )

    async with connect("ws://127.0.0.1:8765") as websocket:
        await websocket.send(message.to_json())
        logger.info("Speech message sent")


if __name__ == "__main__":
    asyncio.run(main())