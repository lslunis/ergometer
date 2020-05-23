import json
import base64
import asyncio
from data_processor import *
from util import die_unless, FatalError
import websockets

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
                msg = json.dumps(
                    {
                        "host": host_completed,
                        "pos": pos,
                        "data": base64.b64encode(data).decode("ascii"),
                    }
                )
                await websocket.send(msg)

            # If there's a new file reset everything. Otherwise keep
            # awaitng the next task.
            if do_break:
                break


def client_handler(file_manager):
    async def handle_client(websocket, path):
        try:
            async for message in websocket:
                msg = json.loads(message)
                if msg["action"] == "read":
                    asyncio.create_task(
                        send_updates(
                            file_manager,
                            websocket,
                            msg["positions"],
                            msg.get("exclude", None),
                        )
                    )
                elif msg["action"] == "write":
                    raw_data = base64.b64decode(msg["data"])
                    file_manager.write(
                        msg["host"], [raw_data], position=msg["pos"],
                    )
                    resp = json.dumps({"pos": msg["pos"] + len(raw_data)})
                    await websocket.send(resp)

                elif msg["action"] == "host_position":
                    pos = file_manager.positions.get(msg["host"], 0)
                    resp = json.dumps({"pos": pos})
                    await websocket.send(resp)
                else:
                    raise FatalError("Unknown action type in message: {msg}")
        except websockets.exceptions.ConnectionClosedError:
            pass

    return handle_client


async def main():
    storage_root = sys.argv[1]
    port = sys.argv[2]
    file_manager = FileManager("broker", storage_root, asyncio.Event())
    await websockets.serve(client_handler(file_manager), "localhost", port)


if __name__ == "__main__":
    if platform.system() == "Windows":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    asyncio.get_event_loop().run_until_complete(main())
    asyncio.get_event_loop().run_forever()
