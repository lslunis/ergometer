import asyncio
import sys

import websockets

from .broker import client_handler
from .data_processor import FileManager


async def main():
    storage_root = sys.argv[1]
    port = sys.argv[2]
    file_manager = FileManager("broker", storage_root, asyncio.Event())
    await websockets.serve(client_handler(file_manager), "localhost", port)


asyncio.get_event_loop().run_until_complete(main())
asyncio.get_event_loop().run_forever()
