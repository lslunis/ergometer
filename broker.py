import asyncio

import websockets

from . import messages as m
from .util import FatalError


# Handles "read" calls. Sends an unending stream of data to a client.
async def send_updates(file_manager, websocket, client_positions, exclude=None):
    for host, pos, data in file_manager.subscribe(client_positions, exclude):
        msg = m.ReadResponse(None, host=host, pos=pos, data=data)
        await websocket.send(msg.encode())


def client_handler(file_manager):
    async def handle_client(websocket, path):
        try:
            async for message in websocket:
                msg = m.Message.decode(message)
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
            pass

    return handle_client
