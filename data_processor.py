import asyncio
import glob
import os.path as path
import os
import sys

# trim at startup
# mark irrecoverable data


class IntegrityError(Exception):
    pass


# Read local events for "host", writing them to "broker"
async def publish_local_events(host, file_manager, broker):
    position = await broker.host_position(host)
    while True:
        data = await file_manager.read(position)
        # Handles reconnect internally.
        position = await broker.write(host, data, position)


def die(check, msg):
    if not check:
        return
    print(msg, file=sys.stderr)
    os.exit(1)


# Read local events from "event_queue" in groups of "batch_size"
# and write them using "file_manager"
async def local_event_handler(host, event_queue, file_manager, batch_size):
    while True:
        to_write = [event_queue.get()]
        for _ in range(batch_size - 1):
            if event_queue.empty():
                break
            # Make this a list
            to_write.append(event_queue.get_nowait())
        file_manager.write(host, data)


# Read all changes from "broker" for other hosts and write them using
# "file_manager"
async def change_subscriber(broker, file_manager):
    while True:
        # Initialize.
        positions = await file_manager.positions()
        try:
            # Read messages forever.
            async for host, data, position in broker.read(positions, exclude=host):
                file_manager.write(host, data, position=position)
        except Exception as e:
            file_manager.log(e)


# A single file. Does error handling around reads and writes as well as
# tracking the position. Writes are synchronous and reads are asynchronous.
class HostFile:
    def __init__(self, host_path, error_event):
        self.path = host_path
        self.data_available = asyncio.Event()
        self.error_event = error_event

    @property
    def size(self):
        return os.stat(host_path).st_size

    # REQUIRES: f is a file opened in "r+" mode
    def safe_seek(self, f):
        file_position = self.size
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
            die(type(d) == bytes, "Got non-bytes data to write: {d}")
        # Open for reading and writing without truncating.
        with open(self.path, "rb+") as f:
            file_position = self.safe_seek(f)
            to_write = b"".join(data)
            to_write_len = len(to_write)
            if position != file_position:
                raise IntegrityError(
                    f"Tried to write at position {position} but the latest safe position is {file_position}"
                )
            if to_write_len % 16 != 0:
                raise IntegrityError(
                    f"Tried to write {to_write_len} bytes to {self.path}, which is not divisible by 16"
                )
            bytes_written = f.write(to_write)
            die(bytes_written == len(data), f"Failed to write to file {self.path}")
            self.data_available.set()
            self.data_available = asyncio.Event()

    # Log an error message. A newline is automatically appended.
    def log(self, msg):
        error_path = os.path.join(self.storage_root, "error.log")
        with open(error_path, "a") as f:
            full_message = msg + "\n"
            byte_written = f.write(full_message)
            die(
                bytes_written == len(full_message),
                f"Failed to write to error log {error_path}",
            )
        self.error_event.set()

    async def read(self, position, batch_size):
        die(
            position % 16 == 0,
            f"Tried to read file {self.path} at position {position} which is not divisible by 16",
        )
        file_size = self.size
        die(
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
    def __init__(self, host, storage_root):
        self.storage_root = storage_root
        self.host = host
        for host_path in glob.glob(self.host_path("*")):
            host, _, _ = host_path.rpartition(".hostlog")
            self.hosts[host] = HostFile(host_path)

    def host_path(self, host):
        return os.path.join(self.storage_root, f"{host}.hostlog")

    @property
    def positions(self):
        positions = {name: host.size for name, host in self.hosts.items()}
        # If any files have an integrity error ignore the corrupt part. It
        # will be logged later.
        return {name: pos - (pos % 16) for name, pos in positions}

    def write(self, host, data, position=None):
        die(data[-1] == "\n", "TODO")
        if host not in self.hosts:
            self.hosts[host] = HostFile(self.host_path(host))
        self.hosts[host].write(data, position)

    async def read(self, host, position, batch_size):
        if host not in self.hosts:
            self.hosts[host] = HostFile(self.host_path(host))
        return self.hosts[host].read(position, batch_size)
