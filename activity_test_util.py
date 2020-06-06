from .cache_updater import min_pause, ActivityEdge
from .time import max_time


def add_activity(session, *times):
    session.add_all(activity_from_times(times))


def assert_activity(session, *times):
    pauses = session.query(ActivityEdge).order_by(ActivityEdge.time).all()
    assert pauses == [*activity_from_times(times)]


def activity_from_times(times):
    assert len(times) % 2 == 0
    times = [0, *times, max_time]
    for i in range(0, len(times), 2):
        pause_start, pause_end = times[i : i + 2]
        assert pause_end - pause_start >= min_pause
        if pause_start != 0:
            yield ActivityEdge(time=pause_start, rising=False)
        if pause_end != max_time:
            yield ActivityEdge(time=pause_end, rising=True)
