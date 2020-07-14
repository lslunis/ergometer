from datetime import datetime, timedelta
from math import inf


def day_start_of(dt):
    start_hour = 4
    if dt.hour < start_hour:
        dt -= timedelta(days=1)
    return int(
        dt.replace(
            hour=start_hour, minute=0, second=0, microsecond=0, fold=0
        ).timestamp()
    )


def is_on_day(time, day_start):
    return day_start <= time < day_start + in_seconds(days=1)


def imprecise_clock():
    return precise_clock().replace(microsecond=0)


def precise_clock():
    return datetime.now().astimezone()


min_time = -inf
max_time = inf


def in_seconds(**kw):
    return timedelta(**kw).total_seconds()
