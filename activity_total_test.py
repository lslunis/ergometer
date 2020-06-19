from datetime import datetime

from .activity_test_util import add_activity
from .cache_updater import ActivityEdge, connect
from .time import in_seconds


def iso(s):
    return datetime.fromisoformat(s).timestamp()


def test_empty():
    with connect("sqlite://") as Session:
        session = Session()
        total = ActivityEdge.activity_total(
            session, iso("2020-05-23 04"), iso("2020-05-24 04")
        )
        assert total == 0


def test_one_pause_in_a_day():
    with connect("sqlite://") as Session:
        session = Session()
        add_activity(
            session,
            iso("2020-05-23 03"),
            iso("2020-05-23 05"),
            iso("2020-05-24 03"),
            iso("2020-05-24 05"),
        )
        total = ActivityEdge.activity_total(
            session, iso("2020-05-23 04"), iso("2020-05-24 04")
        )
        assert total == in_seconds(hours=2)


def test_pauses_overlap_day_boundaries():
    with connect("sqlite://") as Session:
        session = Session()
        add_activity(session, iso("2020-05-23 05"), iso("2020-05-24 03"))
        total = ActivityEdge.activity_total(
            session, iso("2020-05-23 04"), iso("2020-05-24 04")
        )
        assert total == in_seconds(hours=22)
