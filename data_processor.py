import base64
import json
import websockets
import platform
import asyncio
import asyncio.subprocess
import glob
import os
import os.path as path
import sys
import uuid
from util import FatalError, die_unless, retry_on

# trim at startup
# mark irrecoverable data


class IntegrityError(Exception):
    pass


# Read local events for "host", writing them to "broker".
async def publish_local_events(host, broker, file_manager):
    position = await broker.host_position(host)
    while True:
        data = await file_manager.read(host, position, 100)
        # Handles reconnect internally.
        position = await broker.write(host, data, position)


# Read local events from "event_queue" in groups of "batch_size"
# and write them using "file_manager".
@retry_on(Exception)
async def local_event_handler(host, event_queue, file_manager, batch_size):
    to_write = [await event_queue.get()]
    for _ in range(batch_size - 1):
        if event_queue.empty():
            break
        # Make this a list
        to_write.append(event_queue.get_nowait())
    file_manager.write(host, to_write)


# Read all changes from "broker" for other hosts and write them using
# "file_manager".
@retry_on(Exception)
async def change_subscriber(self_host, broker, file_manager):
    # Initialize.
    positions = file_manager.positions
    try:
        # Read messages forever.
        async for data_host, data, position in broker.read(
            positions, exclude=self_host
        ):
            file_manager.write(data_host, [data], position=position)
    except FatalError as fe:
        raise fe
    except Exception as e:
        file_manager.log(str(e))


# A single file. Does error handling around reads and writes as well as
# tracking the position. Writes are synchronous and reads are asynchronous.
class HostFile:
    def __init__(self, host_path, error_event):
        self.path = host_path
        self.data_available = asyncio.Event()
        self.error_event = error_event
        if not path.exists(host_path):
            with open(host_path, "w"):
                pass

    @property
    def size(self):
        return os.stat(self.path).st_size

    # REQUIRES: f is a file opened in "r+" mode
    def safe_seek(self, f):
        file_position = self.size
        mod = file_position % 16
        if file_position % 16 != 0:
            file_position -= file_position % 16
            f.seek(file_position)
            corruption = f.read(16)
            self.log(f"Corruption in file {self.path}: '{corruption}'")
        f.seek(file_position)
        return file_position

    # data is an iterable of bytes objects.
    def write(self, data, position=None):
        for d in data:
            die_unless(type(d) == bytes, f"Got {d} of non-bytes data to write")
        # Open for reading and writing without truncating.
        with open(self.path, "rb+") as f:
            file_position = self.safe_seek(f)
            to_write = b"".join(data)
            to_write_len = len(to_write)
            if position != file_position and position is not None:
                raise IntegrityError(
                    f"Tried to write at position {position} but the latest safe position is {file_position}"
                )
            if to_write_len % 16 != 0:
                raise IntegrityError(
                    f"Tried to write {to_write_len} bytes to {self.path}, which is not divisible by 16"
                )
            bytes_written = f.write(to_write)
            die_unless(
                bytes_written == len(to_write), f"Failed to write to file {self.path}"
            )
            self.data_available.set()
            self.data_available = asyncio.Event()

    async def read(self, position, batch_size):
        die_unless(
            position % 16 == 0,
            f"Tried to read file {self.path} at position {position} which is not divisible by 16",
        )
        file_size = self.size
        die_unless(
            position <= file_size,
            f"Tried to read file {self.path} at position {position} which > {file_size}",
        )

        # Wait if there is no new data.
        if file_size == position:
            await self.data_available.wait()

        data = ""

        # Only read up to the file size, and do
        # not include the last entry if it is corrupt.
        # The corruption will be reported on the next
        # write so this code does not do so.
        file_size = self.size
        if file_size % 16 != 0:
            file_size -= file_size % 16
        with open(self.path, "rb") as f:
            f.seek(position)
            desired_bytes = batch_size * 16
            available_bytes = file_size - position
            data = f.read(min(desired_bytes, available_bytes))
        return data


# Reads and writes data for particular hosts.
class FileManager:
    def __init__(self, host, storage_root, error_event):
        self.storage_root = storage_root
        self.host = host
        self.error_event = error_event
        self.hosts = {}
        self.new_file = asyncio.Event()
        for host_path in glob.glob(self.host_path("*")):
            host, _, _ = path.basename(host_path).rpartition(".hostlog")
            self.add_file(host, host_path)

    def add_file(self, host, host_path):
        self.hosts[host] = HostFile(host_path, self.error_event)
        self.new_file.set()
        self.new_file = asyncio.Event()

    def host_path(self, host):
        return os.path.join(self.storage_root, f"{host}.hostlog")

    # Log an error message. A newline is automatically appended.
    def log(self, msg):
        error_path = os.path.join(self.storage_root, "error.log")
        with open(error_path, "a") as f:
            full_message = msg + "\n"
            bytes_written = f.write(full_message)
            die_unless(
                bytes_written == len(full_message),
                f"Failed to write to error log {error_path}",
            )
        self.error_event.set()

    @property
    def positions(self):
        positions = {name: host.size for name, host in self.hosts.items()}
        # If any files have an integrity error ignore the corrupt part. It
        # will be logged later.
        return {name: pos - (pos % 16) for name, pos in positions.items()}

    def write(self, host, data, position=None):
        if host not in self.hosts:
            self.add_file(host, self.host_path(host))
        self.hosts[host].write(data, position)

    async def read(self, host, position, batch_size):
        if host not in self.hosts:
            self.add_file(host, self.host_path(host))
        return await self.hosts[host].read(position, batch_size)


class BrokerClient:
    def __init__(self, address):
        self.address = address
        self.queue = asyncio.Queue(maxsize=1000)

    async def read(self, positions, exclude=None):
        async with websockets.connect(self.address) as websocket:
            await websocket.send(json.dumps({"action": "read", "positions": positions}))
            while True:
                msg = await websocket.recv()
                resp = json.loads(msg)
                yield (
                    resp["host"],
                    base64.b64decode(resp["data"]),
                    resp["pos"],
                )

    async def write(self, host, data, position):
        # returns the position of the broker for this host.
        await asyncio.sleep(1)
        return position + len(data)

    async def host_position(self, host):
        return 0


def get_current_host(storage_root):
    host_path = os.path.join(storage_root, "self.host")
    if path.exists(host_path):
        with open(host_path) as f:
            return f.read()
    host = str(uuid.uuid4())
    with open(host_path, "w") as f:
        f.write(host)
    return host


async def run_subprocess(queue, command, args):
    subprocess = await asyncio.create_subprocess_exec(
        command, *args, stdout=asyncio.subprocess.PIPE
    )
    while True:
        data = await subprocess.stdout.read(16)
        die_unless(
            len(data) == 16,
            f"Did not get 16 bytes from subprocess {command}. Got: '{data}'",
        )
        await asyncio.sleep(0.5)
        await queue.put(data)
