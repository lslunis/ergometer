from ergometer.database import ActivityEdge, min_pause
from ergometer.time import max_time


def add_activity(session, *times):
    session.add_all([*activity_from_times(times)][1:-1])


def assert_activity(session, *times):
    edges = session.query(ActivityEdge).order_by(ActivityEdge.time).all()
    assert edges == [*activity_from_times(times)]


def activity_from_times(times):
    assert len(times) % 2 == 0
    times = [0, *times, max_time]
    for i in range(0, len(times), 2):
        pause_start, pause_end = times[i : i + 2]
        assert pause_end - pause_start >= min_pause
        yield ActivityEdge(time=pause_start, rising=False)
        yield ActivityEdge(time=pause_end, rising=True)
