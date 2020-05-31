from .cache_updater import min_span, ActivityEdge
from .time import max_time


def add_activity(session, *times):
    session.add_all(activity_from_times(times))


def assert_activity(session, *times):
    pauses = session.query(ActivityEdge).order_by(ActivityEdge.end).all()
    assert pauses == [*activity_from_times(times)]


def activity_from_times(times):
    assert len(times) % 2 == 0
    times = [0, *times, max_time]
    for i in range(0, len(times), 2):
        start, end = times[i : i + 2]
        assert end - start >= min_span
        yield ActivityEdge(start=start, end=end)  # TODO: refactor pause to activity
