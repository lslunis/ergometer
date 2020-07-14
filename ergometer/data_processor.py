import asyncio
import asyncio.subprocess
import glob
import os
import struct
import sys
import uuid
from contextlib import asynccontextmanager
from os import path as path
from time import time_ns

import websockets
from ergometer import messages as m
from ergometer.database import EventType, data_format, database_updater
from ergometer.time import imprecise_clock
from ergometer.util import (
    async_log_exceptions,
    die_unless,
    log,
    retry_on,
    retry_on_iter,
)

min_sleep = 0.016 # on Windows, sleep below this value returns immediately

# trim at startup
# mark irrecoverable data


class IntegrityError(Exception):
    ...


# Read local events for "host", writing them to "broker".
@async_log_exceptions
async def local_event_publisher(host, broker, file_manager):
    log.debug("Starting local_event_publisher")
    position = await broker.host_position(host)
    while True:
        data = await file_manager.read(host, position, 100)
        # Handles reconnect internally.
        position = await broker.write(host, data, position)


@async_log_exceptions
async def local_event_writer(host, pop_local_event, file_manager):
    log.debug("Starting local_event_writer")
    while True:
        events = []
        try:
            while True:
                events.append(pop_local_event())
        except IndexError:
            ...
        if events:
            file_manager.write(host, events)
        await asyncio.sleep(min_sleep)


# Read all changes from "broker" for other hosts and write them using
# "file_manager".
@async_log_exceptions
async def change_subscriber(self_host, broker, file_manager):
    log.debug("Starting change_subscriber")
    # Initialize.
    positions = file_manager.positions

    # Read messages forever.
    async for data_host, data, position in broker.read(positions, exclude=self_host):
        file_manager.write(data_host, [data], position=position)


# A single file. Does error handling around reads and writes as well as
# tracking the position. Writes are synchronous and reads are asynchronous.
class HostFile:
    def __init__(self, host_path):
        self.path = host_path
        self.data_available = asyncio.Event()
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
            log.error(f"Corruption in file {self.path}: '{corruption}'")
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

            start = time_ns()
            bytes_written = f.write(to_write)
            elapsed = time_ns() - start
            log.debug(f"wrote {bytes_written}B in {elapsed/1e9:.3f}s")
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
            start = time_ns()
            data = f.read(min(desired_bytes, available_bytes))
            elapsed = time_ns() - start
            log.debug(f"read {len(data)}B in {elapsed/1e9:.3f}s")
        return data


# Reads and writes data for particular hosts.
class FileManager:
    def __init__(self, host):
        self.host = host
        self.hosts = {}
        self.new_file = asyncio.Event()
        for host_path in glob.glob(self.host_path("*")):
            host, _, _ = path.basename(host_path).rpartition(".hostlog")
            self.add_file(host, host_path)

    def add_file(self, host, host_path):
        self.hosts[host] = HostFile(host_path)
        self.new_file.set()
        self.new_file = asyncio.Event()

    def host_path(self, host):
        return f"{host}.hostlog"

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

    async def subscribe(self, client_positions, exclude=None):
        while True:
            pending = set(
                [
                    read_with_host(self, host, pos, BATCH_SIZE)
                    for host, pos in merge_positions(
                        client_positions, self.positions
                    ).items()
                    if host != exclude
                ]
            )
            pending.add(self.new_file.wait())
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
                            self, host_completed, pos + len(data), BATCH_SIZE
                        )
                    )
                    client_positions[host_completed] = pos + len(data)
                    yield host_completed, pos, data

                # If there's a new file reset everything. Otherwise keep
                # awaitng the next task.
                if do_break:
                    break


class BrokerClient:
    def __init__(self, address):
        self.address = address
        self.queue = asyncio.Queue(maxsize=1000)

    @retry_on_iter(OSError, retry_delay=5)
    async def read(self, positions, exclude=None):
        async with websockets.connect(self.address) as websocket:
            msg = m.ReadRequest(None, positions=positions, exclude=exclude)
            await websocket.send(msg.encode())
            while True:
                msg = await websocket.recv()
                resp = m.Message.decode(msg)
                yield (resp.host, resp.data, resp.pos)

    @retry_on(OSError, return_on_success=True, retry_delay=5)
    async def write(self, host, data, position):
        async with websockets.connect(self.address) as websocket:
            msg = m.WriteRequest(None, data=data, pos=position, host=host)
            await websocket.send(msg.encode())
            resp = m.Message.decode(await websocket.recv())
            return resp.pos

    @retry_on(OSError, return_on_success=True, retry_delay=5)
    async def host_position(self, host):
        async with websockets.connect(self.address) as websocket:
            await websocket.send(m.HostPositionRequest(None, host=host).encode())
            resp = m.Message.decode(await websocket.recv())
            return resp.pos


def get_current_host():
    host_path = "self.host"
    if path.exists(host_path):
        with open(host_path) as f:
            return f.read()
    host = str(uuid.uuid4())
    with open(host_path, "w") as f:
        f.write(host)
    return host


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


@async_log_exceptions
async def activity_monitor(push_local_event, generate_activity, *args):
    log.debug("Starting activity_monitor")
    if generate_activity:
        while True:
            push_local_event(make_action(int(imprecise_clock().timestamp())))
            await asyncio.sleep(1)
    elif os.name == "nt":
        async with exec(args) as out:
            while True:
                time = int(await out.readuntil())
                push_local_event(make_action(time))


@asynccontextmanager
async def exec(args):
    subprocess = None
    try:
        subprocess = await asyncio.create_subprocess_exec(
            *map(str, args), stdout=asyncio.subprocess.PIPE
        )
        yield subprocess.stdout
    finally:
        if subprocess:
            log.debug("closing subprocess")
            subprocess.terminate()
            await subprocess.wait()
            log.debug("closed subprocess")


def make_action(time):
    return struct.pack(data_format, EventType.action.value, 1, time - 1)


@async_log_exceptions
async def data_worker(model):
    log.debug("Starting data_worker")
    host = get_current_host()
    die_unless(len(host) > 0, "host is empty")
    file_manager = FileManager(host)
    broker = BrokerClient(model.config["server"])

    tasks = [
        asyncio.create_task(coro)
        for coro in [
            change_subscriber(host, broker, file_manager),
            local_event_publisher(host, broker, file_manager),
            activity_monitor(
                model.push_local_event,
                model.config["generate_activity"],
                os.path.join(model.config["source_root"], "activity_monitor.exe"),
                *model.config["button_count_ignore_list"],
            ),
            local_event_writer(host, model.pop_local_event, file_manager),
            database_updater(model.Session, model.update_cache, file_manager.subscribe),
        ]
    ]

    while not model.exiting:
        await asyncio.sleep(min_sleep)
    log.debug("canceling data tasks")
    for task in tasks:
        task.cancel()
    await asyncio.wait(tasks)
    log.debug("canceled data tasks")


def run_loop(model):
    asyncio.run(data_worker(model), debug=model.config["verbose"])
