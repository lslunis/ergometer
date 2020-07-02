from collections import deque
from threading import Event, Thread

from .data_worker import run_loop
from .database import connect


class Model:
    def __init__(self):
        self._exit_event = Event()
        self._local_events = deque()
        self.Session = connect("sqlite:///data.sqlite")
        self._cache = {}
        self._thread = Thread(target=run_loop, args=(self,))
        self._thread.start()

    def push_local_event(self, event):
        self._local_events.append(event)

    def pop_local_event(self):
        return self._local_events.popleft()

    def update_cache(self, delta):
        self._cache = {**self._cache, **delta}
        return self._cache

    def metrics_at(self, now):
        m = dict(
            daily_value=daily_total if is_on_day(now, day_start) else 0,
            rest_value=now - rest_start,
            **self._cache,
        )
        m["session_value"] = (
            now - m["session_start"] if m["rest_value"] < m["rest_target"] else 0
        )
        return m

    def activity_running_total(self, start, end):
        return

    def is_exiting(self):
        return self._exit_event.is_set()

    def exit(self):
        self._exit_event.set()
        self._thread.join()
