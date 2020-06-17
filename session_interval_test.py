from .cache_updater import connect, ActivityEdge
from .activity_test_util import add_activity


def test_no_rest():
    with connect("sqlite://") as Session:
        session = Session()
        assert ActivityEdge.session_start(session) == 0
        assert ActivityEdge.rest_start(session) == 0


def test_one_rest():
    with connect("sqlite://") as Session:
        session = Session()
        add_activity(session, 15, 20)
        assert ActivityEdge.session_start(session) == 0
        assert ActivityEdge.rest_start(session) == 20


def test_many_rest():
    with connect("sqlite://") as Session:
        session = Session()
        add_activity(session, 1000, 1005, 1020, 1025, 1325, 1330, 1345, 1350)
        assert ActivityEdge.session_start(session) == 1325
        assert ActivityEdge.rest_start(session) == 1350
