from .cache_updater import min_span, Pause
from .time import max_time


def add_pauses(session, *times):
    assert len(times) % 2 == 0
    times = [0, *times, max_time]
    for i in range(0, len(times), 2):
        start, end = times[i : i + 2]
        assert end - start >= min_span
        session.add(Pause(start=start, end=end))
