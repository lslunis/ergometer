import asyncio

import websockets

from . import messages as m
from .util import FatalError

BATCH_SIZE = 100


def merge_positions(client, server):
    positions = {k: v for k, v in client.items()}
    for k, v in server.items():
        if k not in positions:
            positions[k] = 0
    return positions


async def read_with_host(file_manager, host, position, batch_size):
    data = await file_manager.read(host, position, batch_size)
    return (host, position, data)


# Handles "read" calls. Sends an unending stream of data to a client.
async def send_updates(file_manager, websocket, client_positions, exclude=None):
    for host, pos, data in subscribe(file_manager, client_positions, exclude):
        msg = m.ReadResponse(None, host=host, pos=pos, data=data)
        await websocket.send(msg.encode())


async def subscribe(file_manager, client_positions, exclude=None):
    while True:
        pending = set(
            [
                read_with_host(file_manager, host, pos, BATCH_SIZE)
                for host, pos in merge_positions(
                    client_positions, file_manager.positions
                ).items()
                if host != exclude
            ]
        )
        pending.add(file_manager.new_file.wait())
        while True:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            do_break = False
            for task in done:
                value = await task

                # The completed task is waiting on a new file. When we've
                # sent all of the data from this iteratio we should
                # get a new set of positions.
                if value is True:
                    do_break = True
                    continue

                # The completed task is a read. Update client_positions,
                # send the data back, and enqueue the next read from that
                # file.
                host_completed, pos, data = await task
                pending.add(
                    read_with_host(
                        file_manager, host_completed, pos + len(data), BATCH_SIZE
                    )
                )
                client_positions[host_completed] = pos + len(data)
                yield host_completed, pos, data

            # If there's a new file reset everything. Otherwise keep
            # awaitng the next task.
            if do_break:
                break


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
