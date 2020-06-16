from .cache_updater import connect, ActivityUpdater
from .activity_test_util import add_activity, assert_activity


def test_split_empty():
    with connect("sqlite://") as Session:
        session = Session()
        activity_updater = ActivityUpdater(session)

        now = 1589137550
        assert activity_updater.update(now, 1) == 1

        assert_activity(session, now, now + 1)


def test_split_nonempty():
    with connect("sqlite://") as Session:
        session = Session()
        activity_updater = ActivityUpdater(session)
        add_activity(session, 15, 20)

        assert activity_updater.update(35, 1) == 1

        assert_activity(session, 15, 20, 35, 36)


def test_minimum_possible_split():
    with connect("sqlite://") as Session:
        session = Session()
        activity_updater = ActivityUpdater(session)
        add_activity(session, 15, 27)

        assert activity_updater.update(42, 1) == 1
        assert_activity(session, 15, 27, 42, 43)


def test_shrink_from_left():
    with connect("sqlite://") as Session:
        session = Session()
        activity_updater = ActivityUpdater(session)
        add_activity(session, 15, 20)

        assert activity_updater.update(25, 1) == 6
        assert_activity(session, 15, 26)

        assert activity_updater.update(26, 1) == 1
        assert_activity(session, 15, 27)


def test_shrink_from_right():
    with connect("sqlite://") as Session:
        session = Session()
        activity_updater = ActivityUpdater(session)
        add_activity(session, 35, 40)

        assert activity_updater.update(34, 1) == 1
        assert_activity(session, 34, 40)

        # maximum possible shrink from right
        assert activity_updater.update(19, 1) == 15
        assert_activity(session, 19, 40)


def test_shrink_from_both():
    with connect("sqlite://") as Session:
        session = Session()
        activity_updater = ActivityUpdater(session)
        add_activity(session, 25, 30, 59, 65)

        assert activity_updater.update(29, 1) == 0
        assert activity_updater.update(44, 1) == 29
        assert_activity(session, 25, 65)


def test_fill_after_shrinking():
    with connect("sqlite://") as Session:
        session = Session()
        activity_updater = ActivityUpdater(session)
        add_activity(session, 25, 30)

        assert activity_updater.update(31, 1) == 2
        assert activity_updater.update(30, 1) == 0
        assert_activity(session, 25, 32)


def test_time_falls_between_pauses():
    with connect("sqlite://") as Session:
        session = Session()
        activity_updater = ActivityUpdater(session)
        add_activity(session, 25, 30, 59, 65)

        assert activity_updater.update(25, 1) == 0
        assert activity_updater.update(26, 1) == 0
        assert activity_updater.update(29, 1) == 0
        assert_activity(session, 25, 30, 59, 65)


class QueryCounter:
    def __init__(self, session):
        self.session = session
        self.query_count = 0
        self.expected_query_count = 0

    def __getattr__(self, name):
        if name == "query":
            self.query_count += 1
        if name not in ["add", "delete", "flush", "query"]:
            raise AttributeError
        return getattr(self.session, name)

    def expect_queries(self):
        self.expected_query_count += 2
        self.check_count()

    def expect_no_queries(self):
        self.check_count()

    def check_count(self):
        assert self.query_count == self.expected_query_count


def test_query_frequency():
    with connect("sqlite://") as Session:
        session = Session()
        query_counter = QueryCounter(session)
        activity_updater = ActivityUpdater(query_counter)
        add_activity(session, 25, 30, 70, 75)

        activity_updater.update(27, 1)
        query_counter.expect_queries()

        activity_updater.update(29, 1)
        query_counter.expect_queries()

        activity_updater.update(45, 1)
        query_counter.expect_no_queries()

        activity_updater.update(40, 1)
        query_counter.expect_no_queries()

        activity_updater.update(50, 1)
        query_counter.expect_queries()

        activity_updater.update(60, 1)
        query_counter.expect_no_queries()
