import struct
import sys
from collections import deque
from datetime import datetime
from threading import Event, Thread

from .data_processor import run_loop
from .database import EventType, connect, data_format
from .util import log


class Model:
    def __init__(self):
        self._exit_event = Event()
        self._local_events = deque()
        self.Session = connect("sqlite:///data.sqlite")
        self._cache = {}
        self.storage_root = "."
        self.cloud_broker_address = sys.argv[2]
        self._thread = Thread(target=run_loop, args=(self,))
        self._thread.start()

    def push_local_event(self, event):
        id, value, time = struct.unpack(data_format, event)
        type = EventType(id)
        dt = datetime.fromtimestamp(time).astimezone()
        log.debug(f"push_local_event {type.name} {value} {dt}")

        self._local_events.append(event)

    def pop_local_event(self):
        return self._local_events.popleft()

    def update_cache(self, delta):
        self._cache = {**self._cache, **delta}
        return self._cache

    def metrics_at(self, now):
        if not self._cache:
            return None
        m = {**self._cache}
        m["daily_value"] = m["daily_total"] if is_on_day(now, m["day_start"]) else 0
        m["rest_value"] = now - m["rest_start"]
        m["session_value"] = (
            now - m["session_start"] if m["rest_value"] < m["rest_target"] else 0
        )
        return m

    def activity_running_total(self, start, end):
        return

    @property
    def exiting(self):
        return self._exit_event.is_set()

    def exit(self):
        log.debug("data thread exiting")
        self._exit_event.set()
        self._thread.join()
        log.debug("data thread exited")
