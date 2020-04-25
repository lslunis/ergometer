import asyncio
import glob
import os.path as path
import os

# Read local events for "host", writing them to "broker"
async def publish_local_events(host, file_manager, broker):
    position = await broker.host_position(host)
    while True:
        data = await file_manager.read(position)
        try:
            position = await broker.write(host, position, data)
        except Exception as e:
            file_manager.log(e)
            position = await broker.host_position(host)


# Read local events from "event_queue" in groups of "batch_size"
# and write them using "file_manager"
async def local_event_handler(host, event_queue, file_manager, batch_size):
    while True:
        to_write = b""
        for _ in range(0, batch_size):
            if event_queue.empty():
                break
            to_write += event_queue.get_nowait()
        try:
            file_manager.write(host, data)
        except Exception as e:
            file_manager.log(e)


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
    def __init__(self, host_path):
        self.path = host_path
        self.position = os.stat(host_path).st_size
        self.data_available = asyncio.Event()
        with open(host_path) as f:
            # Check that the last character is a newline. Otherwise
            # there was a partial write.
            f.seek(-1, 2)
            if f.read(1) != "\n":
                raise Exception(
                    "Integrity error. File '{}' does not end with a newline"
                )

    def write(self, data, position=None):
        with open(self.path, "a") as f:
            if position is not None and position != f.tell():
                raise Exception(
                    "Reqested write position {} does not match the file "
                    "position {}".format(position, f.tell())
                )
            bytes_written = f.write(data)
            if bytes_written != len(data):
                raise Exception("")
            self.position += bytes_written
            self.data_available.set(True)
            self.data_available = asyncio.Event()

    # Log an error message. A newline is automatically appended.
    def log(self, msg):
        with open(os.path.join(self.storage_root, "error.log"), "a") as f:
            f.write(msg + "\n")

    async def read(self, position, batch_size):
        assert position <= self.position

        # Wait if there is no new data.
        if self.position == position:
            await self.data_available.wait()

        # Read and return at most batch_size lines.
        data = ""
        for _ in range(0, batch_size):
            with open(self.path, "r") as f:
                # Confirm this read is for a valid location.
                if position != 0:
                    f.seek(position - 1)
                    if f.read(1) != "\n":
                        raise Exception(
                            "Tried to read at invalid offset {} "
                            "in file {}".format(position, self.path)
                        )
                for _ in range(batch_size):
                    data += f.readline()
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
        return os.path.join(self.storage_root, "{}.hostlog".format(host))

    @property
    def positions(self):
        return {name: host.position for name, host in self.hosts.items()}

    def write(self, host, data, position=None):
        assert data[-1] == "\n"
        if host not in self.hosts:
            self.hosts[host] = HostFile(self.host_path(host))
        self.hosts[host].write(data, position)

    async def read(self, host, position, batch_size):
        if host not in self.hosts:
            self.hosts[host] = HostFile(self.host_path(host))
        return self.hosts[host].read(position, batch_size)
