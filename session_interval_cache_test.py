from .cache_updater import connect, ActivityEdge
from .activity_test_util import add_activity


def test_no_rest():
    with connect("sqlite://") as Session:
        session = Session()
        assert ActivityEdge.session_interval_cache(session) == dict(
            session_start=0, session_end=0
        )


def test_one_rest():
    with connect("sqlite://") as Session:
        session = Session()
        add_activity(session, 15, 20)
        assert ActivityEdge.session_interval_cache(session) == dict(
            session_start=0, session_end=20
        )


def test_many_rest():
    with connect("sqlite://") as Session:
        session = Session()
        add_activity(session, 1000, 1005, 1020, 1025, 1325, 1330, 1345, 1350)
        assert ActivityEdge.session_interval_cache(session) == dict(
            session_start=1325, session_end=1350
        )
