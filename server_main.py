import asyncio
import sys

import websockets

from . import messages as m
from .data_processor import FileManager
from .util import async_log_exceptions, FatalError, init, log


# Handles "read" calls. Sends an unending stream of data to a client.
@async_log_exceptions
async def send_updates(file_manager, websocket, client_positions, exclude=None):
    async for host, pos, data in file_manager.subscribe(client_positions, exclude):
        msg = m.ReadResponse(None, host=host, pos=pos, data=data)
        await websocket.send(msg.encode())


def client_handler(file_manager):
    @async_log_exceptions
    async def handle_client(websocket, path):
        try:
            async for message in websocket:
                msg = m.Message.decode(message)
                log.debug(f"processing message {msg.type}")
                if msg.type == m.ReadRequest.TYPE:
                    asyncio.create_task(
                        send_updates(
                            file_manager, websocket, msg.positions, msg.exclude
                        )
                    )
                elif msg.type == m.WriteRequest.TYPE:
                    file_manager.write(msg.host, [msg.data], position=msg.pos)
                    resp = m.WriteResponse(None, pos=msg.pos + len(msg.data))
                    await websocket.send(resp.encode())

                elif msg.type == m.HostPositionRequest.TYPE:
                    pos = file_manager.positions.get(msg.host, 0)
                    resp = m.HostPositionResponse(None, pos=pos)
                    await websocket.send(resp.encode())
                else:
                    raise FatalError("Unknown action type in message: {message}")
        except websockets.exceptions.ConnectionClosedError:
            log.debug("connection closed")

    return handle_client


async def main():
    init()
    port = sys.argv[2]
    file_manager = FileManager("broker")
    """
    import ssl
    ssl=ssl.SSLContext()
    """
    server = await websockets.serve(client_handler(file_manager), port=port)
    await server.wait_closed()


asyncio.run(main())
