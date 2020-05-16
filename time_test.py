from datetime import datetime

from .time import day_start_of


def test_day_of():
    today_start = datetime(year=2020, month=5, day=16, hour=4)
    yesterday_start = datetime(year=2020, month=5, day=15, hour=4)

    assert datetime.fromtimestamp(day_start_of(today_start)) == today_start

    slight_later_than_today_start = datetime(
        year=2020, month=5, day=16, hour=4, minute=1, second=1, microsecond=1, fold=1
    )
    assert (
        datetime.fromtimestamp(day_start_of(slight_later_than_today_start))
        == today_start
    )

    slight_earlier_than_today_start = datetime(
        year=2020,
        month=5,
        day=16,
        hour=3,
        minute=59,
        second=59,
        microsecond=999999,
        fold=1,
    )
    assert (
        datetime.fromtimestamp(day_start_of(slight_earlier_than_today_start))
        == yesterday_start
    )
