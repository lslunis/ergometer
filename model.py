import struct
import sys
from collections import deque
from datetime import datetime
from threading import Thread

from .data_processor import run_loop
from .database import EventType, connect, data_format
from .time import is_on_day
from .util import log


class Model:
    def __init__(self, config, threaded=False):
        self.config = config
        self.exiting = False
        self._local_events = deque()
        self.Session = connect("sqlite:///data.sqlite")
        self._cache = {}
        if threaded:
            self._thread = Thread(target=run_loop, args=(self,))
            self._thread.start()
        else:
            self._thread = None
            run_loop(self)

    def push_local_event(self, event):
        id, value, time = struct.unpack(data_format, event)
        type = EventType(id)
        dt = datetime.fromtimestamp(time).astimezone()
        log.debug(f"push_local_event {type.name} {value} {dt}")

        self._local_events.append(event)

    def pop_local_event(self):
        return self._local_events.popleft()

    def update_cache(self, delta):
        log.info(f"update_cache {delta}")
        self._cache = {**self._cache, **delta}
        return self._cache

    def metrics_at(self, time):
        if not self._cache:
            return None
        m = {**self._cache}
        m["daily_value"] = m["daily_total"] if is_on_day(time, m["day_start"]) else 0
        m["rest_value"] = time - m["rest_start"]
        m["session_value"] = (
            time - m["session_start"] if m["rest_value"] < m["rest_target"] else 0
        )
        return m

    def activity_running_total(self, start, end):
        return

    def exit(self):
        log.debug("data loop exiting")
        self.exiting = True
        if self._thread:
            self._thread.join()
        log.debug("data loop exited")
