from .cache_updater import connect, PauseUpdater
from .activity_test_util import add_activity, assert_activity


def test_split_empty():
    with connect("sqlite://") as Session:
        session = Session()
        pause_updater = PauseUpdater(session)

        now = 1589137550
        pause_updater.update(now, 1)

        assert_activity(session, now, now + 1)


def test_split_nonempty():
    with connect("sqlite://") as Session:
        session = Session()
        pause_updater = PauseUpdater(session)
        add_activity(session, 15, 20)

        pause_updater.update(35, 1)

        assert_activity(session, 15, 20, 35, 36)


def test_minimum_possible_split():
    with connect("sqlite://") as Session:
        session = Session()
        pause_updater = PauseUpdater(session)
        add_activity(session, 15, 27)

        pause_updater.update(42, 1)
        assert_activity(session, 15, 27, 42, 43)


def test_shrink_from_left():
    with connect("sqlite://") as Session:
        session = Session()
        pause_updater = PauseUpdater(session)
        add_activity(session, 15, 20)

        pause_updater.update(25, 1)
        assert_activity(session, 15, 26)

        pause_updater.update(26, 1)
        assert_activity(session, 15, 27)


def test_shrink_from_right():
    with connect("sqlite://") as Session:
        session = Session()
        pause_updater = PauseUpdater(session)
        add_activity(session, 35, 40)

        pause_updater.update(34, 1)
        assert_activity(session, 34, 40)

        # maximum possible shrink from right
        pause_updater.update(19, 1)
        assert_activity(session, 19, 40)


def test_shrink_from_both():
    with connect("sqlite://") as Session:
        session = Session()
        pause_updater = PauseUpdater(session)
        add_activity(session, 25, 30, 59, 65)

        pause_updater.update(44, 1)
        assert_activity(session, 25, 65)


def test_time_falls_between_pauses():
    with connect("sqlite://") as Session:
        session = Session()
        pause_updater = PauseUpdater(session)
        add_activity(session, 25, 30, 59, 65)

        pause_updater.update(29, 1)
        assert_activity(session, 25, 30, 59, 65)
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
        add_activity(session, 25, 30, 70, 75)

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
