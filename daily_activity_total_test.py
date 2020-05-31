from datetime import datetime, timedelta

from .cache_updater import connect, ActivityEdge
from .activity_test_util import add_activity


def iso(s):
    return datetime.fromisoformat(s).timestamp()


# TODO: get this test to pass
# def test_one_pause_in_a_day():
#     with connect("sqlite://") as Session:
#         session = Session()
#         add_pauses(session,
#                    iso("2020-05-23 03"),
#                    iso("2020-05-23 05"),
#                    iso("2020-05-24 03"),
#                    iso("2020-05-24 05"))
#         total = Pause.daily_activity_total(session, iso("2020-05-23 04"))
#         assert total == timedelta(hours=2).total_seconds()


def test_empty():
    with connect("sqlite://") as Session:
        session = Session()
        total = ActivityEdge.daily_activity_total(session, iso("2020-05-23 04"))
        assert total == 0


def test_pauses_overlap_day_boundaries():
    with connect("sqlite://") as Session:
        session = Session()
        add_activity(session, iso("2020-05-23 05"), iso("2020-05-24 03"))
        total = ActivityEdge.daily_activity_total(session, iso("2020-05-23 04"))
        assert total == timedelta(hours=22).total_seconds()
