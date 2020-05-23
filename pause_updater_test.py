from .cache_updater import connect, Pause, PauseUpdater
from .pause_test_util import add_pauses
from .time import max_time


def assert_pauses(session, *time_pairs):
    pauses = session.query(Pause).order_by(Pause.end).all()
    assert pauses == [Pause(start=start, end=end) for start, end in time_pairs]


def test_split_empty():
    with connect("sqlite://") as Session:
        session = Session()
        pause_updater = PauseUpdater(session)

        now = 1589137550
        pause_updater.update(now, 1)

        assert_pauses(session, (0, now), (now + 1, max_time))


def test_split_nonempty():
    with connect("sqlite://") as Session:
        session = Session()
        pause_updater = PauseUpdater(session)
        add_pauses(session, 15, 20)

        pause_updater.update(35, 1)

        assert_pauses(session, (0, 15), (20, 35), (36, max_time))


def test_minimum_possible_split():
    with connect("sqlite://") as Session:
        session = Session()
        pause_updater = PauseUpdater(session)
        add_pauses(session, 15, 27)

        pause_updater.update(42, 1)
        assert_pauses(session, (0, 15), (27, 42), (43, max_time))


def test_shrink_from_left():
    with connect("sqlite://") as Session:
        session = Session()
        pause_updater = PauseUpdater(session)
        add_pauses(session, 15, 20)

        pause_updater.update(25, 1)
        assert_pauses(session, (0, 15), (26, max_time))

        pause_updater.update(26, 1)
        assert_pauses(session, (0, 15), (27, max_time))


def test_shrink_from_right():
    with connect("sqlite://") as Session:
        session = Session()
        pause_updater = PauseUpdater(session)
        add_pauses(session, 35, 40)

        pause_updater.update(34, 1)
        assert_pauses(session, (0, 34), (40, max_time))

        # maximum possible shrink from right
        pause_updater.update(19, 1)
        assert_pauses(session, (0, 19), (40, max_time))


def test_shrink_from_both():
    with connect("sqlite://") as Session:
        session = Session()
        pause_updater = PauseUpdater(session)
        add_pauses(session, 25, 30, 59, 65)

        pause_updater.update(44, 1)
        assert_pauses(session, (0, 25), (65, max_time))


def test_time_falls_between_pauses():
    with connect("sqlite://") as Session:
        session = Session()
        pause_updater = PauseUpdater(session)
        add_pauses(session, 25, 30, 59, 65)

        pause_updater.update(29, 1)
        assert_pauses(session, (0, 25), (30, 59), (65, max_time))
        assert not pause_updater.updated


class SessionProxy:
    def __init__(self, session):
        self.session = session
        self.query_count = 0

    def __getattr__(self, name):
        if name == "query":
            self.query_count += 1
        if name not in ["add", "delete", "flush", "query"]:
            raise AttributeError
        return getattr(self.session, name)


def test_query_frequency():
    with connect("sqlite://") as Session:
        session = Session()
        proxy = SessionProxy(session)
        pause_updater = PauseUpdater(proxy)
        add_pauses(session, 25, 30, 70, 75)

        pause_updater.update(27, 1)
        assert proxy.query_count == 1

        pause_updater.update(29, 1)
        assert proxy.query_count == 1

        pause_updater.update(45, 1)
        assert proxy.query_count == 1

        pause_updater.update(40, 1)
        assert proxy.query_count == 2

        pause_updater.update(50, 1)
        assert proxy.query_count == 3

        pause_updater.update(60, 1)
        assert proxy.query_count == 3
